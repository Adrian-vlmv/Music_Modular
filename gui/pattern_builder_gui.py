# ======================================================
# FILE: gui/rhythm_builder_gui.py
# ======================================================
"""
GUI en Tkinter para crear, editar y combinar patrones de ritmo.
"""
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from midi_engine.playback import reproducir_nota

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

from rhythm_engine.patterns import DURACIONES, RitmoPattern
from storage_engine.rhythm_storage import load_patterns, save_patterns

import threading
import copy


## ----------------------------------------------------------------
## Class: RhythmBuilderGUI
## Description: Interfaz gráfica para crear y editar patrones de ritmo.
## ----------------------------------------------------------------
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

        # Layout
        frame_editor = ttk.LabelFrame(root, text="Editor de patrón")
        frame_editor.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        frame_saved = ttk.LabelFrame(root, text="Patrones guardados")
        frame_saved.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=0)
        root.rowconfigure(0, weight=1)

        # ----- Editor -----
        lbl_name = ttk.Label(frame_editor, text="Nombre:")
        lbl_name.grid(row=0, column=0, sticky="w")
        self.entry_name = ttk.Entry(frame_editor)
        self.entry_name.grid(row=0, column=1, sticky="ew", padx=5)
        frame_editor.columnconfigure(1, weight=1)

        self.lbl_compas = ttk.Label(frame_editor, text="Compás: 0/0")
        self.lbl_compas.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6,0))

        self.list_compas = tk.Listbox(
            frame_editor,
            height=6,
            selectmode=tk.EXTENDED
        )
        self.list_compas.grid(row=2, column=0, columnspan=2, sticky="ew", pady=6)

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
            selectmode="extended"   # <--- ESTA LÍNEA
        )
        self.tree.heading("Name", text="Name")
        self.tree.heading("Compases", text="#Compases")
        self.tree.column("Name", width=160)
        self.tree.column("Compases", width=80, anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<Delete>", self._on_delete_key)
        frame_saved.rowconfigure(0, weight=1)
        frame_saved.columnconfigure(0, weight=1)

        # Atajos de teclado
        root.bind("<Insert>", self.insert_tiempo)
        self.list_compas.bind("<Delete>", self.delete_tiempo)

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
            # No hay patrones: dejar editor vacío (no crear automáticamente)
            self.current_index = None
            self.current_compas = 0
            self.list_compas.delete(0, tk.END)
            self.lbl_compas.config(text="Compás: -")


        
        # ---------------- Tempo y loop ----------------
        tempo_frame = ttk.Frame(frame_editor)
        tempo_frame.grid(row=6, column=0, columnspan=2, sticky="w", pady=(6,0))
        
        ttk.Label(tempo_frame, text="Tempo (BPM):").grid(row=0, column=0, sticky="w")
        
        self.tempo_var = tk.IntVar(value=120)
        
        # Entry para BPM
        self.tempo_entry = ttk.Entry(tempo_frame, width=6, textvariable=self.tempo_var)
        self.tempo_entry.grid(row=0, column=1, sticky="w", padx=(2,10))
        
        # Slider debajo de la Entry
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
        
        # Sincronizar Entry y Slider
        def entry_updated(*args):
            v = self.tempo_var.get()
            if self.tempo_slider.get() != v:
                self.tempo_slider.set(v)
        
        self.tempo_var.trace_add('write', entry_updated)
        
        # Cambiar BPM con la rueda del mouse sobre Entry o Slider
        def on_scroll(event):
            v = self.tempo_var.get()
            if event.delta > 0 or event.num == 4:  # scroll arriba
                v += 1
            else:  # scroll abajo
                v -= 1
            v = max(30, min(300, v))
            self.tempo_var.set(v)
        
        self.tempo_entry.bind("<MouseWheel>", on_scroll)  # Windows
        self.tempo_entry.bind("<Button-4>", on_scroll)    # Linux scroll up
        self.tempo_entry.bind("<Button-5>", on_scroll)    # Linux scroll down
        self.tempo_slider.bind("<MouseWheel>", on_scroll)
        self.tempo_slider.bind("<Button-4>", on_scroll)
        self.tempo_slider.bind("<Button-5>", on_scroll)
        
        # Checkbox Loop
        self.loop_var = tk.BooleanVar(value=False)
        self.loop_check = ttk.Checkbutton(tempo_frame, text="Loop", variable=self.loop_var)
        self.loop_check.grid(row=0, column=2, sticky="w", padx=(10,0))

        # ---------------- Swing ----------------
        self.swing_var = tk.BooleanVar(value=False)
        self.swing_value = tk.IntVar(value=66)

        # Checkbox Swing en nueva fila
        self.swing_check = ttk.Checkbutton(tempo_frame, text="Swing", variable=self.swing_var)
        self.swing_check.grid(row=2, column=2, sticky="w", padx=(10,0))

        # Slider Swing
        self.swing_slider = ttk.Scale(
            tempo_frame,
            from_=50,
            to=99,
            orient=tk.HORIZONTAL,
            variable=self.swing_value
        )
        self.swing_slider.grid(row=2, column=3, sticky="ew", padx=(2,10))

        # Label Swing actual
        self.lbl_swing = ttk.Label(tempo_frame, text="66%")
        self.lbl_swing.grid(row=2, column=4, sticky="w")


        # Actualizar label cuando cambia slider
        def swing_updated(*args):
            self.lbl_swing.config(text=f"{self.swing_value.get()}%")
        self.swing_value.trace_add('write', swing_updated)

        
        # Botón Stop
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

        # Eliminar múltiples → bajar de atrás hacia adelante
        for index in reversed(sel):
            if 0 <= index < len(compas):
                del compas[index]

        self.refresh_editor()

        # Seleccionar algo válido (último índice posible)
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
            return  # nada seleccionado

        index = sel[0]
        compas = p.compases[self.current_compas]

        # Copiar el tiempo seleccionado
        compas.insert(index + 1, compas[index])

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
            # Ya se está reproduciendo
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

                        bpm = max(1, self.tempo_var.get())
                        beat_sec = 60 / bpm  # 1 negra = 1 beat

                        # Duración base
                        dur = DURACIONES.get(e, 1) / 4 * beat_sec

                        # Aplicar Swing solo si está activado y es corchea
                        if self.swing_var.get() and e in ["corchea", "silencio_corchea"]:
                            swing_pct = self.swing_value.get() / 100  # 50-99%
                            nota_fuerte = "-" if e.startswith("silencio") else "C4"

                            # Primera corchea (fuerte)
                            dur_fuerte = dur * 2 * swing_pct  # se multiplica por 2 porque un par de corcheas = 2 * dur
                            reproducir_nota(self.player, nota_fuerte, dur_fuerte)

                            # Segunda corchea (débil)
                            if i + 1 < len(compas) and compas[i + 1] in ["corchea", "silencio_corchea"]:
                                next_e = compas[i + 1]
                                dur_debil = dur * 2 * (1 - swing_pct)
                                nota_debil = "-" if next_e.startswith("silencio") else "C4"
                                reproducir_nota(self.player, nota_debil, dur_debil)
                                i += 1  # saltar la siguiente corchea, ya reproducida
                            i += 1
                            continue  # pasar al siguiente evento
                        

                        # Para todas las demás notas
                        nota = "-" if e.startswith("silencio") else "C4"
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

        if not messagebox.askyesno("Eliminar", f"Eliminar {len(indices)} patrón(es)?\n" +
                                                "\n".join(names)):
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
            self.lbl_compas.config(text="Compás: -")
            return
        n = len(p.compases)
        if n == 0:
            self.lbl_compas.config(text="Compás: (vacío)")
            return
        if self.current_compas < 0:
            self.current_compas = 0
        if self.current_compas >= n:
            self.current_compas = n-1
        total, full = p.compas_estado(self.current_compas)
        self.lbl_compas.config(text=f"Compás: {self.current_compas+1}/{n} ( {total}/{full} )")
        self.list_compas.delete(0, tk.END)
        for e in p.compases[self.current_compas]:
            self.list_compas.insert(tk.END, e)

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
        """
        Si hay un tiempo seleccionado → modificarlo (solo si cabe)
        Si no hay selección → agregar al final (solo si cabe)
        """
        p = self.get_current_pattern()
        if not p:
            return

        compas = p.compases[self.current_compas]
        sel = self.list_compas.curselection()

        dur_nueva = DURACIONES[d]

        if sel:
            # Modificar tiempo existente
            index = sel[0]
            dur_actual = DURACIONES[compas[index]]

            total_sin_actual = sum(DURACIONES[e] for i, e in enumerate(compas) if i != index)

            # Validación
            if total_sin_actual + dur_nueva > 16:
                print("❌ No cabe el cambio en el compás (excede 16).")
                return

            compas[index] = d  # Modificar
        else:
            # Agregar nueva duración al final
            total = sum(DURACIONES[e] for e in compas)
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


