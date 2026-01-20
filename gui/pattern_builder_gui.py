# ======================================================
# FILE: gui/rhythm_builder_gui.py
# ======================================================
"""
GUI en Tkinter para crear, editar y combinar patrones de ritmo.
"""
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

from rhythm_engine.patterns import DURACIONES, RitmoPattern
from storage_engine.rhythm_storage import load_patterns, save_patterns

# --- NUEVO: importamos voicings y funciones para reproducir acordes
from storage_engine.voicing_storage import load_voicings
from midi_engine.chords import reproducir_acorde_threaded
from midi_engine.playback import reproducir_nota

import threading
import copy
import re

# ---------- Helpers para notas / transposición ----------
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

_note_regex = re.compile(r'^([A-Ga-g][#b]?)(-?\d+)$')

def note_to_midi(note):
    """Convierte 'C4' o 'C#3' a número MIDI (C4=60). Lanza ValueError si formato inválido."""
    m = _note_regex.match(note)
    if not m:
        raise ValueError(f"Nota inválida: {note}")
    name = m.group(1)
    octave = int(m.group(2))
    name = name[0].upper() + (name[1] if len(name) > 1 else "")
    if name not in _NOTE_TO_SEMITONE:
        raise ValueError(f"Nombre de nota desconocido: {name}")
    sem = _NOTE_TO_SEMITONE[name]
    midi = (octave + 1) * 12 + sem
    return midi

def midi_to_note(midi):
    """Convierte número MIDI a 'C4' usando sostenidos (ej. 60 -> C4)."""
    octave = midi // 12 - 1
    sem = midi % 12
    name = _SEMITONE_TO_NAME_SHARP[sem]
    return f"{name}{octave}"

def transpose_notes(orig_notes, orig_root, target_root):
    """
    Transpone lista de notas 'orig_notes' (ej. ["C3","D#3",...]) desde orig_root hacia target_root.
    Devuelve lista de notas nuevas.
    """
    try:
        m_orig = note_to_midi(orig_root)
        m_target = note_to_midi(target_root)
    except ValueError:
        # si root inválida, devolver original sin cambios
        return orig_notes[:]
    delta = m_target - m_orig
    result = []
    for n in orig_notes:
        try:
            m = note_to_midi(n)
            mn = m + delta
            result.append(midi_to_note(mn))
        except Exception:
            # si alguna nota no parseable, dejarla tal cual
            result.append(n)
    return result

# ----------------------------------------------------------------
# Class: RhythmBuilderGUI
# ----------------------------------------------------------------
class RhythmBuilderGUI:

    ## ------------------------------------------------------------
    ## Function: __init__
    ## Description: Inicializa la GUI del Rhythm Builder.
    ## param root: Ventana raíz o Toplevel de Tkinter.
    ## param player: Objeto de reproducción MIDI compartido.
    ## ------------------------------------------------------------    
    def __init__(self, root, player=None):
        self.root = root
        self.player = player
        root.title("Rhythm Builder")

        # Datos
        self.patterns = load_patterns()
        self.current_index = None
        self.current_compas = 0
        self.edit_buffer = None

        # Cargamos voicings disponibles
        self.voicings = load_voicings()  # lista de dicts con keys: name, root, notes, hotkey

        # Layout
        frame_editor = ttk.LabelFrame(root, text="Editor de patrón")
        frame_editor.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        frame_saved = ttk.LabelFrame(root, text="Patrones guardados")
        frame_saved.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=0)
        root.rowconfigure(0, weight=1)

        # ----- Editor ----- (nombre / compás)
        lbl_name = ttk.Label(frame_editor, text="Nombre:")
        lbl_name.grid(row=0, column=0, sticky="w")
        self.entry_name = ttk.Entry(frame_editor)
        self.entry_name.grid(row=0, column=1, sticky="ew", padx=5)
        frame_editor.columnconfigure(1, weight=1)

        self.lbl_compas = ttk.Label(frame_editor, text="Compás: 0/0")
        self.lbl_compas.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6,0))

        # -------------------------------------------------------
        # Lista de tiempos (Listbox) y panel de botones a la derecha
        # -------------------------------------------------------
        self.list_compas = tk.Listbox(
            frame_editor,
            height=6,
            selectmode=tk.EXTENDED
        )
        # ahora lo colocamos en columna 0
        self.list_compas.grid(row=2, column=0, sticky="nsew", pady=6)
        frame_editor.rowconfigure(2, weight=1)

        # Panel para los botones "Add Voicing" alineados a la derecha de cada tiempo
        self.buttons_frame = ttk.Frame(frame_editor)
        self.buttons_frame.grid(row=2, column=1, sticky="ns", padx=(6,0), pady=6)
        # necesitaremos repoblar buttons_frame en refresh_editor

        # Bindings
        self.list_compas.bind("<<ListboxSelect>>", lambda e: None)
        root.bind("<Insert>", self.insert_tiempo)
        self.list_compas.bind("<Delete>", self.delete_tiempo)

        # ... botones de duración (igual que antes)
        btn_frame = ttk.Frame(frame_editor)
        btn_frame.grid(row=3, column=0, columnspan=2, sticky="ew")
        for i, d in enumerate(["redonda","blanca","negra","corchea","semicorchea"]):
            ttk.Button(btn_frame, text=d, command=lambda x=d: self.add_event(x)).grid(row=0, column=i, padx=2)
            ttk.Button(btn_frame, text=f"sil-{d}", command=lambda x="silencio_"+d: self.add_event(x)).grid(row=1, column=i, padx=2)

        controls = ttk.Frame(frame_editor)
        controls.grid(row=4, column=0, columnspan=2, sticky="ew", pady=6)
        ttk.Button(controls, text="Nuevo Compás", command=self.add_compas).grid(row=0, column=0, padx=3)
        ttk.Button(controls, text="Eliminar Compás", command=self.delete_compas).grid(row=0, column=1, padx=3)
        ttk.Button(controls, text="Prev", command=self.prev_compas).grid(row=0, column=2, padx=3)
        ttk.Button(controls, text="Next", command=self.next_compas).grid(row=0, column=3, padx=3)

        act = ttk.Frame(frame_editor)
        act.grid(row=5, column=0, columnspan=2, sticky="e", pady=6)
        ttk.Button(act, text="Save As", command=self.save_as).grid(row=0, column=0, padx=3)
        ttk.Button(act, text="Save", command=self.save).grid(row=0, column=1, padx=3)
        ttk.Button(act, text="Play (preview)", command=self.play_preview).grid(row=0, column=2, padx=3)

        # ----- Patrones guardados -----
        self.tree = ttk.Treeview(
            frame_saved,
            columns=("Name","Compases"),
            show="headings",
            height=18,
            selectmode="extended"
        )
        self.tree.heading("Name", text="Name")
        self.tree.heading("Compases", text="#Compases")
        self.tree.column("Name", width=160)
        self.tree.column("Compases", width=80, anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<Delete>", self._on_delete_key)
        frame_saved.rowconfigure(0, weight=1)
        frame_saved.columnconfigure(0, weight=1)

        rb = ttk.Frame(frame_saved)
        rb.grid(row=1, column=0, sticky="ew", pady=6)
        ttk.Button(rb, text="New", command=self.new_pattern).grid(row=0, column=0, padx=3)
        ttk.Button(rb, text="Load", command=self.load_pattern).grid(row=0, column=1, padx=3)
        ttk.Button(rb, text="Delete", command=self.delete_pattern).grid(row=0, column=2, padx=3)
        ttk.Button(rb, text="Combine", command=self.combine_patterns).grid(row=0, column=3, padx=3)
        ttk.Button(rb, text="Export JSON", command=self.export_json).grid(row=0, column=4, padx=3)

        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        # rellenar lista y seleccionar primer patrón si existe
        self.update_tree()

        # Si ya hay patrones guardados, seleccionamos el primero
        if self.patterns:
            self.current_index = 0
            p = self.patterns[0]
            self.entry_name.delete(0, tk.END)
            self.entry_name.insert(0, p.name)
            self.current_compas = 0 if p.compases else -1
            self.refresh_editor()
        else:
            self.current_index = None
            self.current_compas = 0
            self.list_compas.delete(0, tk.END)
            self.lbl_compas.config(text="Compás: -")

        # ---------------- Tempo y loop ----------------
        tempo_frame = ttk.Frame(frame_editor)
        tempo_frame.grid(row=6, column=0, columnspan=2, sticky="w", pady=(6,0))

        ttk.Label(tempo_frame, text="Tempo (BPM):").grid(row=0, column=0, sticky="w")
        self.tempo_var = tk.IntVar(value=120)
        self.tempo_entry = ttk.Entry(tempo_frame, width=6, textvariable=self.tempo_var)
        self.tempo_entry.grid(row=0, column=1, sticky="w", padx=(2,10))

        self.tempo_slider = ttk.Scale(
            tempo_frame,
            from_=30,
            to=300,
            orient=tk.HORIZONTAL,
            command=lambda v: self.tempo_var.set(int(float(v)))
        )
        self.tempo_slider.set(self.tempo_var.get())
        self.tempo_slider.grid(row=1, column=0, columnspan=2, sticky="ew", padx=2, pady=(2,4))
        tempo_frame.columnconfigure(1, weight=1)

        def entry_updated(*args):
            v = self.tempo_var.get()
            if self.tempo_slider.get() != v:
                self.tempo_slider.set(v)
        self.tempo_var.trace_add('write', entry_updated)

        def on_scroll(event):
            v = self.tempo_var.get()
            if event.delta > 0 or getattr(event, "num", None) == 4:
                v += 1
            else:
                v -= 1
            v = max(30, min(300, v))
            self.tempo_var.set(v)

        self.tempo_entry.bind("<MouseWheel>", on_scroll)
        self.tempo_entry.bind("<Button-4>", on_scroll)
        self.tempo_entry.bind("<Button-5>", on_scroll)
        self.tempo_slider.bind("<MouseWheel>", on_scroll)
        self.tempo_slider.bind("<Button-4>", on_scroll)
        self.tempo_slider.bind("<Button-5>", on_scroll)

        self.loop_var = tk.BooleanVar(value=False)
        self.loop_check = ttk.Checkbutton(tempo_frame, text="Loop", variable=self.loop_var)
        self.loop_check.grid(row=0, column=2, sticky="w", padx=(10,0))

        # ---------------- Swing ----------------
        self.swing_var = tk.BooleanVar(value=False)
        self.swing_value = tk.IntVar(value=66)
        self.swing_check = ttk.Checkbutton(tempo_frame, text="Swing", variable=self.swing_var)
        self.swing_check.grid(row=2, column=2, sticky="w", padx=(10,0))
        self.swing_slider = ttk.Scale(
            tempo_frame,
            from_=50,
            to=99,
            orient=tk.HORIZONTAL,
            variable=self.swing_value
        )
        self.swing_slider.grid(row=2, column=3, sticky="ew", padx=(2,10))
        self.lbl_swing = ttk.Label(tempo_frame, text="66%")
        self.lbl_swing.grid(row=2, column=4, sticky="w")
        def swing_updated(*args):
            self.lbl_swing.config(text=f"{self.swing_value.get()}%")
        self.swing_value.trace_add('write', swing_updated)

        ttk.Button(tempo_frame, text="Stop", command=self.stop_preview).grid(row=0, column=3, padx=6)

        # Thread control
        self._play_thread = None
        self._stop_playback = threading.Event()



    ## ----------------------------------------------------------------------------------------------------------------
    ##               MÉTODOS DE LA CLASE
    ## ----------------------------------------------------------------------------------------------------------------

    ## ------------------------------------------------------------
    ## Function: delete_tiempo
    ## Description: Elimina el/los tiempo(s) seleccionado(s) en el compás actual.
    ## param event: Evento de Tkinter (opcional).
    ## ------------------------------------------------------------
    def delete_tiempo(self, event=None):
        p = self.get_current_pattern()
        if not p:
            return
        sel = self.list_compas.curselection()
        if not sel:
            return
        compas = p.compases[self.current_compas]
        for index in reversed(sel):
            if 0 <= index < len(compas):
                del compas[index]
        self.refresh_editor()
        if len(compas) > 0:
            self.list_compas.selection_set(min(sel[0], len(compas)-1))

    ## ------------------------------------------------------------
    ## Function: insert_tiempo
    ## Description: Inserta una copia del tiempo seleccionado justo después.
    ## param event: Evento de Tkinter (opcional).
    ## ------------------------------------------------------------
    def insert_tiempo(self, event=None):
        p = self.get_current_pattern()
        if not p:
            return
        sel = self.list_compas.curselection()
        if not sel:
            return
        index = sel[0]
        compas = p.compases[self.current_compas]
        compas.insert(index + 1, copy.deepcopy(compas[index]))
        self.refresh_editor()
        self.list_compas.selection_set(index + 1)

    ## ------------------------------------------------------------
    ## Function: _on_delete_key
    ## Description: Manejador de evento para la tecla Delete en el Treeview.
    ## param event: Evento de Tkinter.
    ## ------------------------------------------------------------
    def _on_delete_key(self, event):
        self.delete_pattern()

    ## ------------------------------------------------------------
    ## Function: play_preview
    ## Description: Reproduce una vista previa del patrón actual en un hilo separado.
    ## ------------------------------------------------------------
    def play_preview(self):
        if self._play_thread and self._play_thread.is_alive():
            return
        self._stop_playback.clear()
        self._play_thread = threading.Thread(target=self._play_pattern_thread, daemon=True)
        self._play_thread.start()

    ## ------------------------------------------------------------
    ## Function: _play_pattern_thread
    ## Description: Hilo que maneja la reproducción del patrón actual.
    ## ------------------------------------------------------------
    def _play_pattern_thread(self):
        p = self.get_current_pattern()
        if not p or not self.player:
            return
        try:
            while True:
                for compas in p.compases:
                    i = 0
                    while i < len(compas):
                        e = compas[i]

                        # manejar si e es dict (voicing) o string (duración)
                        dur_key = e['dur'] if isinstance(e, dict) else e

                        bpm = max(1, self.tempo_var.get())
                        beat_sec = 60 / bpm  # 1 negra = 1 beat

                        # Duración base (DURACIONES usa las claves como 'corchea' etc.)
                        dur = DURACIONES.get(dur_key, 1) / 4 * beat_sec

                        # Aplicar Swing si corresponde (solo cuando la duración es 'corchea' o 'silencio_corchea')
                        if self.swing_var.get() and dur_key in ["corchea", "silencio_corchea"]:
                            swing_pct = self.swing_value.get() / 100
                            # Primera corchea (fuerte)
                            dur_fuerte = dur * 2 * swing_pct
                            # segunda corchea (débil)
                            dur_debil = dur * 2 * (1 - swing_pct)

                            # Fuerte
                            if isinstance(e, dict) and e.get("type") == "voicing":
                                reproducir_acorde_threaded(self.player, e.get("notes", []), dur_fuerte)
                            else:
                                nota_fuerte = "-" if dur_key.startswith("silencio") else "C4"
                                reproducir_nota(self.player, nota_fuerte, dur_fuerte)

                            # Débil (si siguiente es corchea)
                            if i + 1 < len(compas):
                                next_e = compas[i + 1]
                                next_dur_key = next_e['dur'] if isinstance(next_e, dict) else next_e
                                if next_dur_key in ["corchea", "silencio_corchea"]:
                                    if isinstance(next_e, dict) and next_e.get("type") == "voicing":
                                        reproducir_acorde_threaded(self.player, next_e.get("notes", []), dur_debil)
                                    else:
                                        nota_debil = "-" if next_dur_key.startswith("silencio") else "C4"
                                        reproducir_nota(self.player, nota_debil, dur_debil)
                                    i += 1  # saltar la siguiente corchea
                            i += 1
                            continue

                        # Para eventos sin swing / normales
                        if isinstance(e, dict) and e.get("type") == "voicing":
                            reproducir_acorde_threaded(self.player, e.get("notes", []), dur)
                        else:
                            nota = "-" if dur_key.startswith("silencio") else "C4"
                            reproducir_nota(self.player, nota, dur)

                        if self._stop_playback.is_set():
                            return
                        i += 1

                if not self.loop_var.get():
                    break
        except Exception as exc:
            print("Error en reproducción:", exc)

    ## ------------------------------------------------------------
    ## Function: stop_preview
    ## Description: Detiene la reproducción del patrón actual.
    ## ------------------------------------------------------------    
    def stop_preview(self):
        self._stop_playback.set()
        if self._play_thread:
            self._play_thread.join()
            self._play_thread = None

    ## ------------------------------------------------------------
    ## Function: new_pattern
    ## Description: Crea un nuevo patrón con un nombre único y lo selecciona para edición.
    ## ------------------------------------------------------------
    def new_pattern(self):
        # Generar nombre base
        base = "Pattern"
        used = {p.name for p in self.patterns}

        # Buscar primer número libre
        n = 1
        while True:
            candidate = f"{base}_{n:03d}"
            if candidate not in used:
                break
            n += 1

        # Crear y agregar nuevo patrón
        p = RitmoPattern(candidate)
        self.patterns.append(p)
        self.current_index = len(self.patterns) - 1
        self.current_compas = 0

        # Crear buffer editable
        self.edit_buffer = copy.deepcopy(p)
        self.entry_name.delete(0, tk.END)
        self.entry_name.insert(0, p.name)
        self.update_tree()
        self.refresh_editor()

    ## ------------------------------------------------------------
    ## Function: load_pattern
    ## Description: Carga el patrón seleccionado en el editor para su edición.
    ## ------------------------------------------------------------
    def load_pattern(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Nada seleccionado","Selecciona un patrón")
            return
        i = list(self.tree.get_children()).index(sel[0])
        self.current_index = i

        # ⚠️ EN VEZ DE EDITAR EL ORIGINAL, HACEMOS COPIA
        self.edit_buffer = copy.deepcopy(self.patterns[i])
        self.entry_name.delete(0, tk.END)
        self.entry_name.insert(0, self.edit_buffer.name)
        self.current_compas = 0 if self.edit_buffer.compases else -1
        self.refresh_editor()

    ## ------------------------------------------------------------
    ## Function: delete_pattern
    ## Description: Elimina el/los patrón(es) seleccionado(s) después de confirmar.
    ## ------------------------------------------------------------
    def delete_pattern(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Nada seleccionado", "Selecciona uno o más patrones")
            return

        # Obtener los índices reales según el orden del Treeview
        indices = sorted(
            [list(self.tree.get_children()).index(item) for item in sel],
            reverse=True
        )
        names = [self.patterns[i].name for i in indices]
        if not messagebox.askyesno("Eliminar", f"Eliminar {len(indices)} patrón(es)?\n" + "\n".join(names)):
            return

        # Eliminar desde los índices más altos hacia los más bajos
        for i in indices:
            del self.patterns[i]
        save_patterns(self.patterns)
        self.current_index = None
        self.update_tree()
        if self.patterns:
            self.current_index = 0
            self.current_compas = 0
            self.refresh_editor()
        else:
            self.list_compas.delete(0, tk.END)
            self.lbl_compas.config(text="Compás: -")

    ## ------------------------------------------------------------
    ## Function: save_as
    ## Description: Guarda el patrón actual con un nuevo nombre.
    ## ------------------------------------------------------------
    def save_as(self):
        name = simpledialog.askstring("Save As","Nombre del patrón:")
        if not name:
            return
        p = self.get_current_pattern()
        p.name = name
        self.entry_name.delete(0, tk.END)
        self.entry_name.insert(0, name)
        save_patterns(self.patterns)
        self.update_tree()
        messagebox.showinfo("Guardado","Patrón guardado")

    ## ------------------------------------------------------------
    ## Function: save
    ## Description: Guarda los cambios realizados en el patrón actual.
    ## ------------------------------------------------------------
    def save(self):
        if self.edit_buffer is None:
            return

        # Actualizar nombre
        self.edit_buffer.name = self.entry_name.get() or self.edit_buffer.name

        # Guardar cambios en la lista real
        self.patterns[self.current_index] = copy.deepcopy(self.edit_buffer)
        save_patterns(self.patterns)
        self.update_tree()
        messagebox.showinfo("Guardado", "Patrones guardados")

    ## ------------------------------------------------------------
    ## Function: export_json
    ## Description: Exporta los patrones actuales a un archivo JSON seleccionado por el usuario.
    ## ------------------------------------------------------------
    def export_json(self):
        path = filedialog.asksaveasfilename(defaultextension='.json', filetypes=[('JSON','*.json')])
        if not path:
            return
        from storage_engine.rhythm_storage import save_patterns as sp
        sp(self.patterns, path)
        messagebox.showinfo("Export","Exportado")

    ## ------------------------------------------------------------
    ## Function: combine_patterns
    ## Description: Combina dos patrones seleccionados en uno nuevo.
    ## ------------------------------------------------------------
    def combine_patterns(self):
        if len(self.patterns) < 2:
            messagebox.showwarning("Insuficiente","Necesitas al menos 2 patrones para combinar")
            return
        sel_a = simpledialog.askinteger("Combine","Patrón A index:", minvalue=0, maxvalue=len(self.patterns)-1)
        if sel_a is None:
            return
        sel_b = simpledialog.askinteger("Combine","Patrón B index:", minvalue=0, maxvalue=len(self.patterns)-1)
        if sel_b is None:
            return
        name = simpledialog.askstring("Combine","Nombre del nuevo patrón:") or f"merge_{sel_a}_{sel_b}"
        new = self.patterns[sel_a].merge(self.patterns[sel_b], name)
        self.patterns.append(new)
        save_patterns(self.patterns)
        self.update_tree()
        messagebox.showinfo("Combine","Patrón combinado creado")

    ## ------------------------------------------------------------
    ## Function: on_tree_select
    ## Description: Manejador de evento cuando se selecciona un patrón en el Treeview.
    ## param event: Evento de Tkinter.
    ## ------------------------------------------------------------
    def on_tree_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        i = list(self.tree.get_children()).index(sel[0])
        self.current_index = i
        self.edit_buffer = copy.deepcopy(self.patterns[i])
        self.entry_name.delete(0, tk.END)
        self.entry_name.insert(0, self.edit_buffer.name)
        self.current_compas = 0
        self.refresh_editor()

    ## ------------------------------------------------------------
    ## Function: get_current_pattern
    ## Description: Devuelve el patrón actualmente en edición.
    ## ------------------------------------------------------------
    def get_current_pattern(self):
        return self.edit_buffer

    ## ------------------------------------------------------------
    ## Function: refresh_editor
    ## Description: Actualiza la vista del editor según el patrón y compás actuales.
    ## ------------------------------------------------------------
    def refresh_editor(self):
        p = self.get_current_pattern()
        if not p:
            self.list_compas.delete(0, tk.END)
            # limpiar botones
            for w in self.buttons_frame.winfo_children():
                w.destroy()
            self.lbl_compas.config(text="Compás: -")
            return
        n = len(p.compases)
        if n == 0:
            self.lbl_compas.config(text="Compás: (vacío)")
            # limpiar botones y listbox
            self.list_compas.delete(0, tk.END)
            for w in self.buttons_frame.winfo_children():
                w.destroy()
            return
        if self.current_compas < 0:
            self.current_compas = 0
        if self.current_compas >= n:
            self.current_compas = n-1
        total, full = p.compas_estado(self.current_compas)
        self.lbl_compas.config(text=f"Compás: {self.current_compas+1}/{n} ( {total}/{full} )")

        # rellenar listbox con representación amigable de cada evento
        self.list_compas.delete(0, tk.END)
        for e in p.compases[self.current_compas]:
            if isinstance(e, dict) and e.get("type") == "voicing":
                dur = e.get("dur", "?")
                name = e.get("name", "(voicing)")
                root = e.get("root", "?")
                self.list_compas.insert(tk.END, f"{dur} ({name} @ {root})")
            else:
                self.list_compas.insert(tk.END, str(e))

        # actualizar panel de botones (uno por cada evento, salvo silencios)
        for w in self.buttons_frame.winfo_children():
            w.destroy()
        compas = p.compases[self.current_compas]
        for i, e in enumerate(compas):
            # determinar si es silencio
            dur_key = e['dur'] if isinstance(e, dict) else e
            if str(dur_key).startswith("silencio"):
                btn = ttk.Label(self.buttons_frame, text="")  # espacio vacío
                btn.grid(row=i, column=0, pady=2, sticky="w")
            else:
                btn = ttk.Button(self.buttons_frame, text="Add Voicing",
                                 command=lambda idx=i: self.open_voicing_dialog(idx))
                btn.grid(row=i, column=0, pady=2, sticky="w")

    ## ------------------------------------------------------------
    ## Function: add_compas
    ## Description: Agrega un nuevo compás al patrón actual.
    ## ------------------------------------------------------------
    def add_compas(self):
        p = self.get_current_pattern()
        if not p:
            return
        p.add_compas()
        self.current_compas = len(p.compases)-1
        self.refresh_editor()

    ## ------------------------------------------------------------
    ## Function: delete_compas
    ## Description: Elimina el compás actual del patrón después de confirmar.
    ## ------------------------------------------------------------
    def delete_compas(self):
        p = self.get_current_pattern()
        if not p or len(p.compases) == 0:
            return
        if messagebox.askyesno("Eliminar compás","¿Eliminar compás actual?"):
            p.delete_compas(self.current_compas)
            if self.current_compas >= len(p.compases):
                self.current_compas = max(0, len(p.compases)-1)
            self.refresh_editor()

    ## ------------------------------------------------------------
    ## Function: prev_compas
    ## Description: Navega al compás anterior en el patrón.
    ## ------------------------------------------------------------
    def prev_compas(self):
        p = self.get_current_pattern()
        if not p:
            return
        if self.current_compas > 0:
            self.current_compas -= 1
            self.refresh_editor()

    ## ------------------------------------------------------------
    ## Function: next_compas
    ## Description: Navega al siguiente compás en el patrón.
    ## ------------------------------------------------------------
    def next_compas(self):
        p = self.get_current_pattern()
        if not p:
            return
        if self.current_compas < len(p.compases)-1:
            self.current_compas += 1
            self.refresh_editor()

    ## ------------------------------------------------------------
    ## Function: add_event
    ## Description: Agrega o modifica un evento en el compás actual.
    ## param d: Duración del evento a agregar/modificar.
    ## ------------------------------------------------------------
    def add_event(self, d):
        p = self.get_current_pattern()
        if not p:
            return
        compas = p.compases[self.current_compas]
        sel = self.list_compas.curselection()
        dur_nueva = DURACIONES[d]
        if sel:
            index = sel[0]
            dur_actual = DURACIONES[compas[index]] if not isinstance(compas[index], dict) else DURACIONES.get(compas[index].get("dur"), 1)
            total_sin_actual = sum(DURACIONES[e] if not isinstance(e, dict) else DURACIONES.get(e.get("dur"),1) for i, e in enumerate(compas) if i != index)
            if total_sin_actual + dur_nueva > 16:
                print("❌ No cabe el cambio en el compás (excede 16).")
                return
            compas[index] = d
        else:
            total = sum(DURACIONES[e] if not isinstance(e, dict) else DURACIONES.get(e.get("dur"),1) for e in compas)
            if total + dur_nueva > 16:
                print("❌ No cabe este evento (excede 16).")
                return
            compas.append(d)
        self.refresh_editor()

    ## ------------------------------------------------------------
    ## Function: update_tree
    ## Description: Actualiza el Treeview con la lista actual de patrones.
    ## ------------------------------------------------------------
    def update_tree(self):
        self.tree.delete(*self.tree.get_children())
        for p in self.patterns:
            self.tree.insert("", tk.END, values=(p.name, len(p.compases)))

    # ---------- NUEVO: diálogo Add Voicing ----------
    def open_voicing_dialog(self, index):
        """
        Abre ventana para seleccionar Root y voicing guardado.
        index: índice del tiempo en el compás actual que será reemplazado.
        """
        p = self.get_current_pattern()
        if not p:
            return
        compas = p.compases[self.current_compas]
        if index < 0 or index >= len(compas):
            return

        # ventana
        dlg = tk.Toplevel(self.root)
        dlg.title("Select Voicing")
        dlg.transient(self.root)
        dlg.grab_set()

        ttk.Label(dlg, text="Root (ej. C3, D#4):").grid(row=0, column=0, sticky="w", padx=6, pady=(6,2))
        entry_root = ttk.Entry(dlg)
        entry_root.grid(row=0, column=1, sticky="ew", padx=6, pady=(6,2))
        entry_root.insert(0, "C4")
        dlg.columnconfigure(1, weight=1)

        # lista de voicings (nombres)
        lb = tk.Listbox(dlg, height=8, exportselection=False)
        lb.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=6)
        dlg.rowconfigure(1, weight=1)

        # rellenar con nombres y mostrar root original en el label
        voicings = self.voicings or []
        for v in voicings:
            nm = v.get("name", "(unnamed)")
            rt = v.get("root", "?")
            lb.insert(tk.END, f"{nm}  @ {rt}")

        # botones
        btn_frame = ttk.Frame(dlg)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=6)
        def ok_action():
            sel = lb.curselection()
            if not sel:
                messagebox.showwarning("Selecciona", "Selecciona un voicing")
                return
            chosen = voicings[sel[0]]
            target_root = entry_root.get().strip()
            if not target_root:
                messagebox.showwarning("Root faltante", "Teclea una root válida (ej. D3)")
                return

            # Adaptar (transponer) las notas del voicing desde su root original hacia target_root
            orig_root = chosen.get("root", None)
            orig_notes = chosen.get("notes", [])
            if not orig_root:
                # si no tiene root en el voicing guardado, asumimos que notas ya están correctas (no transponemos)
                adapted = orig_notes[:]
            else:
                adapted = transpose_notes(orig_notes, orig_root, target_root)

            # Reemplazar el evento en el compás. Conservamos la duración previa.
            prev = compas[index]
            dur_key = prev['dur'] if isinstance(prev, dict) else prev
            compas[index] = {
                "type": "voicing",
                "dur": dur_key,
                "name": chosen.get("name", "(voicing)"),
                "root": target_root,
                "notes": adapted
            }

            # refrescar editor y cerrar
            self.refresh_editor()
            dlg.destroy()

        def cancel_action():
            dlg.destroy()

        ttk.Button(btn_frame, text="OK", command=ok_action).grid(row=0, column=0, padx=6)
        ttk.Button(btn_frame, text="Cancel", command=cancel_action).grid(row=0, column=1, padx=6)

    # fin de clase

# EOF
