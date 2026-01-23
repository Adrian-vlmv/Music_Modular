import threading
import time
import copy
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

from storage_engine.voicing_storage import load_voicings
from storage_engine.rhythm_storage import load_patterns
from rhythm_engine.patterns import DURACIONES
from midi_engine.chords import reproducir_acorde_threaded, detener_acorde

# Helpers for note<->midi conversion and transposition
_NOTE_TO_SEMITONE = {
    'C': 0, 'C#': 1, 'Db': 1,
    'D': 2, 'D#': 3, 'Eb': 3,
    'E': 4,
    'F': 5, 'F#': 6, 'Gb': 6,
    'G': 7, 'G#': 8, 'Ab': 8,
    'A': 9, 'A#': 10, 'Bb': 10,
    'B': 11
}
_SEMITONE_TO_NAME_SHARP = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']


def _note_to_midi(note):
    m = re.match(r'^([A-G][#b]?)(-?\d+)$', note)
    if not m:
        raise ValueError(f'Invalid note: {note}')
    name = m.group(1)
    octave = int(m.group(2))
    name = name[0].upper() + (name[1] if len(name) > 1 else '')
    if name not in _NOTE_TO_SEMITONE:
        raise ValueError(f'Unknown note name: {name}')
    sem = _NOTE_TO_SEMITONE[name]
    midi = (octave + 1) * 12 + sem
    return midi


def _midi_to_note(midi):
    octave = midi // 12 - 1
    sem = midi % 12
    name = _SEMITONE_TO_NAME_SHARP[sem]
    return f"{name}{octave}"


def transpose_notes(notes, orig_root, target_root):
    """Transpose list of note strings (e.g. ['C3','E3']) so that orig_root -> target_root.
    target_root may be 'C' (no octave) or 'C4'. If no octave provided, use octave of orig_root.
    """
    try:
        m_orig = _note_to_midi(orig_root)
    except Exception:
        # can't parse orig_root, return original
        return notes[:]

    # prepare target root with octave if missing
    m_target = None
    try:
        # if target_root already has octave
        if re.match(r'^([A-G][#b]?)-?\d+$', target_root):
            m_target = _note_to_midi(target_root)
        else:
            # append octave from orig_root
            mo = re.match(r'^([A-G][#b]?)(-?\d+)$', orig_root)
            if mo:
                octo = mo.group(2)
                m_target = _note_to_midi(f"{target_root}{octo}")
            else:
                # fallback: use same midi as orig
                m_target = m_orig
    except Exception:
        m_target = m_orig

    delta = m_target - m_orig

    out = []
    for n in notes:
        try:
            m = _note_to_midi(n)
            m2 = m + delta
            # clamp
            if m2 < 0:
                m2 = 0
            if m2 > 127:
                m2 = 127
            out.append(_midi_to_note(m2))
        except Exception:
            out.append(n)
    return out


class ProgressionsGUI:
    """GUI to create progressions combining rhythm patterns and voicings.

    A progression is a list of blocks. Each block selects a rhythm pattern and
    maps each note/event in the pattern to a voicing (from saved voicings).

    Playback is done in a background thread. Playback timing uses DURACIONES
    from rhythm_engine.patterns and the BPM set in the GUI.
    """

    def __init__(self, root, player=None):
        self.root = root
        self.player = player
        root.title("Progressions")

        # load resources
        self.voicings = load_voicings()
        self.patterns = load_patterns()

        # state
        self.blocks = []  # list of dicts: {"pattern": pattern_obj, "voicing_map": [voicing_name_or_none]}
        self._play_thread = None
        self._stop_event = threading.Event()

        # layout
        top_frame = ttk.Frame(root)
        top_frame.pack(fill="x", padx=8, pady=8)

        ttk.Label(top_frame, text="Progression length (bars):").grid(row=0, column=0, sticky="w")
        self.bars_var = tk.IntVar(value=4)
        ttk.Spinbox(top_frame, from_=1, to_=128, textvariable=self.bars_var, width=6).grid(row=0, column=1, padx=6)

        self.loop_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top_frame, text="Loop", variable=self.loop_var).grid(row=0, column=2, padx=6)

        ttk.Label(top_frame, text="Tempo (BPM):").grid(row=0, column=3, sticky="e")
        self.tempo_var = tk.IntVar(value=120)
        ttk.Spinbox(top_frame, from_=30, to_=300, textvariable=self.tempo_var, width=6).grid(row=0, column=4, padx=6)

        btn_frame = ttk.Frame(top_frame)
        btn_frame.grid(row=0, column=5, sticky="e")
        ttk.Button(btn_frame, text="Add Block", command=self.add_block).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Play", command=self.play).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Stop", command=self.stop).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Open", command=self.open_progression).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Save", command=self.save_progression).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Save As", command=self.save_progression_as).pack(side="left", padx=4)

        # current progression file path (None until saved/loaded)
        self.prog_path = None

        # area for blocks
        self.blocks_canvas = tk.Canvas(root)
        self.blocks_canvas.pack(fill="both", expand=True, padx=8, pady=(0,8))

        self.blocks_frame = ttk.Frame(self.blocks_canvas)
        self.blocks_canvas.create_window((0, 0), window=self.blocks_frame, anchor="nw")
        self.blocks_frame.bind("<Configure>", lambda e: self.blocks_canvas.configure(scrollregion=self.blocks_canvas.bbox("all")))

        # right-click context: list of available voicings
        self.voicing_names = [v.get("name", "(unnamed)") for v in self.voicings]

        # initial empty block
        if not self.blocks:
            self.add_block()

    def add_block(self):
        block = {"pattern": None, "voicing_map": []}
        self.blocks.append(block)
        self._render_blocks()

    def remove_block(self, index):
        try:
            del self.blocks[index]
        except Exception:
            return
        self._render_blocks()

    def _render_blocks(self):
        # clear
        for w in self.blocks_frame.winfo_children():
            w.destroy()

        for i, block in enumerate(self.blocks):
            # DEBUG: log block state before normalizing
            try:
                print(f"[DEBUG] _render_blocks: block {i} pattern raw=<{type(block.get('pattern'))}> {repr(block.get('pattern'))} voicing_map_len={len(block.get('voicing_map') or [])}")
            except Exception:
                print(f"[DEBUG] _render_blocks: block {i} (unable to stringify pattern)")

            # Normalize stored pattern (could be a name/string or a lightweight dict) into the actual pattern object
            pat_val = block.get('pattern')
            # Only map when pattern is a string (name) or a dict coming from JSON —
            # avoid overwriting valid pattern objects that may not expose the 'compases' attribute.
            if isinstance(pat_val, str):
                p_obj = next((x for x in self.patterns if x.name == pat_val), None)
                if p_obj is not None:
                    block['pattern'] = p_obj
            elif isinstance(pat_val, dict):
                nm = pat_val.get('name')
                if nm:
                    p_obj = next((x for x in self.patterns if x.name == nm), None)
                    if p_obj is not None:
                        block['pattern'] = p_obj

            # DEBUG: after normalization, show event count
            try:
                ev_count = len(self._get_pattern_events(block.get('pattern')))
            except Exception:
                ev_count = 'ERR'
            print(f"[DEBUG] _render_blocks: block {i} after normalize pattern_type=<{type(block.get('pattern'))}> events={ev_count}")

            frm = ttk.LabelFrame(self.blocks_frame, text=f"Block {i+1}")
            frm.pack(fill="x", padx=4, pady=6)

            left = ttk.Frame(frm)
            left.pack(side="left", fill="y", padx=6, pady=6)

            # Root (tonality) selection for this block (single note name without octave)
            ttk.Label(left, text="Root:").grid(row=0, column=0, sticky="w")
            notas_base = ["C","C#","Db","D","D#","Eb","E","F","F#","Gb","G","G#","Ab","A","A#","Bb","B"]
            root_cb = ttk.Combobox(left, values=notas_base, width=6, state='readonly')
            root_cb.grid(row=0, column=1, padx=6)
            # set saved value if present
            if block.get("root"):
                try:
                    root_cb.set(block.get("root"))
                except Exception:
                    pass

            def on_root_select(event, bi=i, cb=root_cb):
                val = cb.get() or None
                try:
                    print(f"[DEBUG] on_root_select: block {bi} set root -> {val!r} (before pattern={type(self.blocks[bi].get('pattern'))} {getattr(self.blocks[bi].get('pattern'), 'name', repr(self.blocks[bi].get('pattern')))})")
                except Exception:
                    print(f"[DEBUG] on_root_select: block {bi} set root -> {val!r}")
                self.blocks[bi]["root"] = val
                # re-render to apply filtered voicing lists
                self._render_blocks()

            # bind selection and common ways the user may change the combobox
            root_cb.bind("<<ComboboxSelected>>", on_root_select)
            root_cb.bind("<Return>", on_root_select)
            root_cb.bind("<FocusOut>", on_root_select)

            # Pattern selection below the root (separate row to avoid overlap)
            ttk.Label(left, text="Pattern:").grid(row=1, column=0, sticky="w", pady=(6,0))
            pat_names = [p.name for p in self.patterns]
            pat_cb = ttk.Combobox(left, values=pat_names, width=30, state='readonly')
            pat_cb.grid(row=1, column=1, padx=6, pady=(6,0))
            if block.get("pattern"):
                try:
                    pat_cb.set(block["pattern"].name)
                except Exception:
                    pass

            def on_pattern_select(event=None, bi=i, cb=pat_cb):
                name = cb.get()
                p = next((x for x in self.patterns if x.name == name), None)
                self.blocks[bi]["pattern"] = p
                # build default voicing map length according to pattern events
                events = self._get_pattern_events(p)
                vm = self.blocks[bi].get("voicing_map") or []
                if len(vm) < len(events):
                    vm = vm + [None] * (len(events) - len(vm))
                self.blocks[bi]["voicing_map"] = vm
                # re-render so the voicing selectors appear
                self._render_blocks()

            # bind selection and also Enter/FocusOut for safety
            pat_cb.bind("<<ComboboxSelected>>", on_pattern_select)
            pat_cb.bind("<Return>", on_pattern_select)
            pat_cb.bind("<FocusOut>", on_pattern_select)

            # Add an explicit Apply button in case the event wasn't fired
            ttk.Button(left, text="Apply", command=lambda cb=pat_cb: on_pattern_select(None, i, cb)).grid(row=1, column=2, padx=6, pady=(6,0))

            # If block already had a pattern but voicing_map missing/short, ensure it's prepared
            if block.get("pattern") and (not block.get("voicing_map") or len(block.get("voicing_map")) < len(self._get_pattern_events(block.get("pattern")))):
                p = block.get("pattern")
                events = self._get_pattern_events(p)
                vm = block.get("voicing_map") or []
                if len(vm) < len(events):
                    vm = vm + [None] * (len(events) - len(vm))
                block["voicing_map"] = vm

             # Remove button placed to the right and spanning both rows
            ttk.Button(left, text="Remove", command=lambda idx=i: self.remove_block(idx)).grid(row=0, column=2, rowspan=2, padx=6, sticky="ns")

            # area to map events -> voicings
            right = ttk.Frame(frm)
            right.pack(side="left", fill="both", expand=True, padx=6, pady=6)

            events = self._get_pattern_events(block.get("pattern"))
            if not events:
                ttk.Label(right, text="No pattern selected").pack(anchor="w")
            else:
                # ensure voicing_map length
                vm = block.get("voicing_map") or []
                if len(vm) < len(events):
                    vm = vm + [None] * (len(events) - len(vm))
                    block["voicing_map"] = vm

                for ei, ev in enumerate(events):
                    sub = ttk.Frame(right)
                    sub.pack(fill="x", pady=2)
                    # display event info (try to show duration key)
                    label_text = f"Event {ei+1}"
                    try:
                        if isinstance(ev, dict):
                            if "dur" in ev:
                                label_text += f" ({ev['dur']})"
                            elif "duration" in ev:
                                label_text += f" ({ev['duration']})"
                        else:
                            # try attribute
                            d = getattr(ev, 'dur', None) or getattr(ev, 'duration', None)
                            if d:
                                label_text += f" ({d})"
                    except Exception:
                        pass

                    ttk.Label(sub, text=label_text, width=24).pack(side="left")

                    # prepare voicing choices sorted with matches first
                    block_root = block.get("root")
                    choices = ["(none)"] + self._sorted_voicing_names(block_root)
                    cb = ttk.Combobox(sub, values=choices, width=36)
                    sel_name = vm[ei] if vm[ei] is not None else "(none)"
                    cb.set(sel_name)
                    

                    

                    def on_voicing_change(event, bi=i, ei_local=ei, cb_local=cb):
                        val = cb_local.get()
                        if val == "(none)":
                            self.blocks[bi]["voicing_map"][ei_local] = None
                        else:
                            self.blocks[bi]["voicing_map"][ei_local] = val

                    cb.bind("<<ComboboxSelected>>", on_voicing_change)
                    cb.pack(side="left", padx=6)
        # end for blocks

    def _sorted_voicing_names(self, root_name):
        """Return voicing names with those matching root_name first, then the rest."""
        all_names = [v.get('name', '(unnamed)') for v in self.voicings]
        if not root_name:
            return all_names
        matches = self._voicing_names_for_root(root_name)
        # ensure preserving order and uniqueness
        rest = [n for n in all_names if n not in matches]
        return matches + rest

    def play(self):
        if self._play_thread and self._play_thread.is_alive():
            return
        self._stop_event.clear()
        self._play_thread = threading.Thread(target=self._play_thread_fn, daemon=True)
        self._play_thread.start()

    def stop(self):
        self._stop_event.set()
        # try to stop any sounding chords
        try:
            detener_acorde(None)
        except Exception:
            pass

    def _duration_to_seconds(self, dur_key):
        # DURACIONES likely maps names to fraction of whole note (e.g. 'negra': 0.25)
        # seconds = (60 / bpm) * 4 * fraction
        bpm = max(1, self.tempo_var.get() or 120)
        try:
            frac = 1.0
            if isinstance(dur_key, (int, float)):
                # treat as seconds
                return float(dur_key)
            if dur_key is None:
                frac = 0.25
            else:
                # try to find mapping
                if isinstance(dur_key, str) and dur_key in DURACIONES:
                    frac = DURACIONES[dur_key]
                elif isinstance(dur_key, dict) and 'dur' in dur_key:
                    key = dur_key['dur']
                    frac = DURACIONES.get(key, 0.25)
                else:
                    # try attribute
                    key = getattr(dur_key, 'dur', None) or getattr(dur_key, 'duration', None)
                    frac = DURACIONES.get(key, 0.25) if key else 0.25
            seconds = (60.0 / bpm) * 4.0 * float(frac)
            return seconds
        except Exception:
            return 0.5

    def _play_thread_fn(self):
        # Play the progression once, or loop if requested
        try:
            repeat = self.bars_var.get() or 1
        except Exception:
            repeat = 1

        while True:
            for block in self.blocks:
                if self._stop_event.is_set():
                    return
                pattern = block.get('pattern')
                vm = block.get('voicing_map') or []
                events = self._get_pattern_events(pattern)
                # play events sequentially
                for ei, ev in enumerate(events):
                    if self._stop_event.is_set():
                        return
                    # determine duration
                    dur = None
                    try:
                        if isinstance(ev, dict):
                            dur = ev.get('dur') or ev.get('duration')
                        else:
                            dur = getattr(ev, 'dur', None) or getattr(ev, 'duration', None)
                    except Exception:
                        dur = None
                    secs = self._duration_to_seconds(dur)

                    # determine voicing notes
                    voicing_name = vm[ei] if ei < len(vm) else None
                    notes = None
                    if voicing_name:
                        vobj = next((x for x in self.voicings if x.get('name') == voicing_name), None)
                        if vobj:
                            notes = vobj.get('notes', [])
                    if notes:
                        # if block has a root, transpose voicing from its original root to block root
                        try:
                            vroot = vobj.get('root')
                            block_root = block.get('root')
                            if vroot and block_root:
                                notes_to_play = transpose_notes(notes, vroot, block_root)
                            else:
                                notes_to_play = notes
                        except Exception:
                            notes_to_play = notes
                        reproducir_acorde_threaded(self.player, notes_to_play, duracion=secs)
                    # wait for duration
                    time.sleep(secs)
            # after going through all blocks, check loop
            if not self.loop_var.get():
                break
            if self._stop_event.is_set():
                break
        # finished

    def save_progression(self):
        """Save to current path or ask for one."""
        if not self.prog_path:
            return self.save_progression_as()
        try:
            data = {
                'blocks': [
                    {
                        'pattern': b.get('pattern').name if b.get('pattern') else None,
                        'root': b.get('root'),
                        'voicing_map': b.get('voicing_map', [])
                    } for b in self.blocks
                ],
                'bars': self.bars_var.get(),
                'loop': bool(self.loop_var.get()),
                'tempo': int(self.tempo_var.get())
            }
            import json
            with open(self.prog_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            messagebox.showinfo('Saved', f'Progression saved to {self.prog_path}')
        except Exception as e:
            messagebox.showerror('Error', f'Error saving progression:\n{e}')

    def save_progression_as(self):
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'storage_engine', 'data')
        os.makedirs(data_dir, exist_ok=True)
        path = filedialog.asksaveasfilename(initialdir=data_dir, defaultextension='.json', filetypes=[('JSON','*.json')])
        if not path:
            return
        self.prog_path = path
        return self.save_progression()

    def open_progression(self):
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'storage_engine', 'data')
        path = filedialog.askopenfilename(initialdir=data_dir, filetypes=[('JSON','*.json')])
        if not path:
            return
        try:
            import json
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # restore blocks
            blocks = []
            for b in data.get('blocks', []):
                pat_name = b.get('pattern')
                p = next((x for x in self.patterns if x.name == pat_name), None) if pat_name else None
                blocks.append({'pattern': p, 'root': b.get('root'), 'voicing_map': b.get('voicing_map', [])})
            self.blocks = blocks
            # restore controls
            try:
                self.bars_var.set(int(data.get('bars', self.bars_var.get())))
            except Exception:
                pass
            try:
                self.loop_var.set(bool(data.get('loop', self.loop_var.get())))
            except Exception:
                pass
            try:
                self.tempo_var.set(int(data.get('tempo', self.tempo_var.get())))
            except Exception:
                pass
            self.prog_path = path
            self._render_blocks()
            messagebox.showinfo('Loaded', f'Progression loaded from {path}')
        except Exception as e:
            messagebox.showerror('Error', f'Error loading progression:\n{e}')

    def _get_pattern_events(self, pattern):
        # pattern is expected to have .compases as list of compases, each compas is a list of events
        if not pattern:
            return []

        def is_event_like(it):
            try:
                if isinstance(it, dict):
                    return 'dur' in it or 'duration' in it or 'note' in it or 'pitch' in it
                # object with attributes
                if hasattr(it, 'dur') or hasattr(it, 'duration') or hasattr(it, 'note') or hasattr(it, 'pitch'):
                    return True
            except Exception:
                pass
            return False

        # try multiple possible shapes
        events = []
        try:
            # common case: pattern.compases is iterable of lists
            compases = getattr(pattern, 'compases', None)
            if compases is None:
                # maybe pattern has 'bars' or 'measures'
                compases = getattr(pattern, 'bars', None) or getattr(pattern, 'measures', None)
            if compases is not None:
                for comp in compases:
                    # comp may be a list of events
                    if isinstance(comp, (list, tuple)):
                        for ev in comp:
                            events.append(ev)
                    else:
                        # comp may be dict with 'events' or 'notes'
                        if isinstance(comp, dict):
                            if 'events' in comp and isinstance(comp['events'], (list, tuple)):
                                events.extend(comp['events'])
                            elif 'notes' in comp and isinstance(comp['notes'], (list, tuple)):
                                events.extend(comp['notes'])
                            else:
                                events.append(comp)
                        else:
                            # object with attribute 'events'?
                            evs = getattr(comp, 'events', None) or getattr(comp, 'notes', None)
                            if evs and isinstance(evs, (list, tuple)):
                                events.extend(evs)
                            else:
                                events.append(comp)
                return events
        except Exception:
            pass

        # if pattern itself is a dict, try common keys and also first list-like value
        try:
            if isinstance(pattern, dict):
                for key in ('compases', 'bars', 'measures', 'events', 'events_list', 'notes'):
                    val = pattern.get(key)
                    if isinstance(val, (list, tuple)):
                        return list(val)
                # fallback: find first list-like value
                for val in pattern.values():
                    if isinstance(val, (list, tuple)):
                        return list(val)
        except Exception:
            pass

        # fallback: if pattern stores events in a flat attribute 'events' or 'events_list'
        try:
            evs = getattr(pattern, 'events', None) or getattr(pattern, 'events_list', None)
            if evs and isinstance(evs, (list, tuple)):
                return list(evs)
        except Exception:
            pass

        # Try inspecting object attributes to find a list-like attribute that looks like events
        try:
            attrs = [a for a in dir(pattern) if not a.startswith('_')]
            for a in attrs:
                try:
                    val = getattr(pattern, a)
                    if isinstance(val, (list, tuple)) and val:
                        # if items look like events, accept
                        if any(is_event_like(it) for it in val):
                            return list(val)
                except Exception:
                    continue
        except Exception:
            pass

        # as last resort, try iterating pattern if it's iterable
        try:
            return list(pattern)
        except Exception:
            return []


# simple helper to open the GUI standalone
if __name__ == '__main__':
    root = tk.Tk()
    from midi_engine.midi_setup import iniciar_sistema_midi
    player = iniciar_sistema_midi()
    ProgressionsGUI(root, player)
    root.mainloop()
