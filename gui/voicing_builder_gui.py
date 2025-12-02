# gui/voicing_builder_gui.py


## --------------------------------------------------------------------------------------------------------------------
##                                           IMPORTS
## --------------------------------------------------------------------------------------------------------------------

import re
import os
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

from midi_engine.chords import (
    reproducir_acorde_threaded,
    reproducir_acorde_mientras,
    detener_acorde,
    reproducir_notas_secuenciales_threaded,
    reproducir_notas_ordenadas_threaded
)
from midi_engine.notes_db import BD_Notas_Midi
from storage_engine.voicing_storage import load_voicings, save_voicings





## --------------------------------------------------------------------------------------------------------------------
## Class: VoicingBuilderGUI
## Description: Clase principal para la GUI del Voicing Builder.
## --------------------------------------------------------------------------------------------------------------------
class VoicingBuilderGUI:


    ## ------------------------------
    ## Function: __init__
    ## Description: Inicializa la GUI del Voicing Builder.
    ## ------------------------------
    def __init__(self, root, player):
        self.root = root
        self.player = player
        root.title("Voicing Builder")

        # -------------------------------------------------------
        #                     MENU SUPERIOR
        # -------------------------------------------------------
        menubar = tk.Menu(root)
        root.config(menu=menubar)

        menu_file = tk.Menu(menubar, tearoff=False)
        menubar.add_cascade(label="File", menu=menu_file)

        menu_file.add_command(label="Load", command=self.load_other_json)



        self.root.bind("<KeyPress>", self.on_hotkey_press)
        self.root.bind("<KeyRelease>", self.on_hotkey_release)

        self.active_hotkeys = set()


        # Datos
        # load_voicings() debe devolver lista de dicts con keys: name, root, notes
        self.voicings = load_voicings()
        self.current_voicing_name = None  # nombre del voicing que estamos editando
        self.current_voicing_index = None
        self.preview_enabled = tk.BooleanVar(value=True)

        # ------------------------------
        #   NOTAS DISPONIBLES
        # ------------------------------
        frame_notas = ttk.LabelFrame(root, text="Notas disponibles")
        frame_notas.grid(row=0, column=0, padx=10, pady=10, sticky="nw")

        # Notas base (usadas para seleccionar nota sin octava)
        self.notas_base = ["C", "C#", "Db", "D", "D#", "Eb", "E", "F",
                           "F#", "Gb", "G", "G#", "Ab", "A", "A#", "Bb", "B"]
        # Unique (por si hay duplicados)
        notas_base_unique = []
        for n in self.notas_base:
            if n not in notas_base_unique:
                notas_base_unique.append(n)
        self.notas_base = notas_base_unique

        # Combobox para elegir nota (para agregar a voicing)
        self.combo_nota = ttk.Combobox(frame_notas, values=self.notas_base, width=6)
        self.combo_nota.grid(row=0, column=0, padx=5, pady=5)

        # Combobox para elegir octava (para agregar a voicing)
        self.octavas = [str(i) for i in range(0, 9)]
        self.combo_octava = ttk.Combobox(frame_notas, values=self.octavas, width=4)
        self.combo_octava.grid(row=0, column=1, padx=5, pady=5)

        btn_add_note = ttk.Button(frame_notas, text="Add Note", command=self.add_note)
        btn_add_note.grid(row=0, column=2, padx=5, pady=5)

        # ------------------------------
        #   VOICING ACTUAL (incluye selección de ROOT manual)
        # ------------------------------
        frame_voicing = ttk.LabelFrame(root, text="Voicing actual")
        frame_voicing.grid(row=1, column=0, padx=10, pady=10, sticky="nw")

        # Listbox de notas del voicing actual
        self.voicing_listbox = tk.Listbox(frame_voicing, width=25, height=8)
        self.voicing_listbox.grid(row=0, column=0, columnspan=3, padx=5, pady=5)
        self.voicing_listbox.bind("<<ListboxSelect>>", self.on_note_select)

        # Nombre actual (label)
        self.lbl_current_name = ttk.Label(frame_voicing, text="Current voicing: (none)")
        self.lbl_current_name.grid(row=1, column=0, columnspan=3, pady=4)

        # Selección manual de ROOT (nota + octava)
        ttk.Label(frame_voicing, text="Root:").grid(row=2, column=0, sticky="e")
        self.combo_root_nota = ttk.Combobox(frame_voicing, values=self.notas_base, width=6)
        self.combo_root_nota.grid(row=2, column=1, sticky="w", padx=2)
        self.combo_root_octava = ttk.Combobox(frame_voicing, values=self.octavas, width=4)
        self.combo_root_octava.grid(row=2, column=2, sticky="w", padx=2)

        # Botón eliminar nota seleccionada
        self.btn_delete_note = ttk.Button(frame_voicing, text="Delete Note",
                                          command=self.delete_selected_note)
        self.btn_delete_note.grid(row=3, column=0, padx=5, pady=5)
        self.btn_delete_note.state(["disabled"])

        # Botón Clear (limpia voicing actual)
        btn_clear = ttk.Button(frame_voicing, text="Clear", command=self.clear_notes)
        btn_clear.grid(row=3, column=1, padx=5, pady=5)

        # Save / Save As
        self.btn_save = ttk.Button(frame_voicing, text="Save",
                                   command=self.save_existing_voicing)
        self.btn_save.grid(row=4, column=0, padx=5, pady=5)
        self.btn_save.state(["disabled"])

        self.btn_save_as = ttk.Button(frame_voicing, text="Save As",
                                      command=self.save_voicing_as)
        self.btn_save_as.grid(row=4, column=1, padx=5, pady=5)

        # ------------------------------
        #   VOICINGS GUARDADOS (Treeview con 3 columnas: Root, Voicing, Notes)
        # ------------------------------
        frame_saved = ttk.LabelFrame(root, text="Voicings guardados")
        frame_saved.grid(row=0, column=1, rowspan=3, padx=10, pady=10, sticky="n")

        # Definimos las columnas en el orden que mostraremos values
        self.tree = ttk.Treeview(
            frame_saved,
            columns=("Root", "Nombre", "Notas", "Hotkey"),
            show="headings",
            height=14
        )
        
        self.tree.heading("Root", text="Root")
        self.tree.heading("Nombre", text="Voicing")
        self.tree.heading("Notas", text="Notes")
        self.tree.heading("Hotkey", text="Hotkey")
        
        self.tree.column("Root", width=70, anchor="center")
        self.tree.column("Nombre", width=140, anchor="w")
        self.tree.column("Notas", width=260, anchor="w")
        self.tree.column("Hotkey", width=50, anchor="center")
        

        self.tree.grid(row=0, column=0, padx=5, pady=5)
        self.tree.bind("<<TreeviewSelect>>", self.on_voicing_click)

        # Botones extra: eliminar, renombrar, mover
        btn_delete_voicing = ttk.Button(frame_saved, text="Delete Voicing",
                                        command=self.delete_voicing)
        btn_delete_voicing.grid(row=1, column=0, pady=3, sticky="ew")

        btn_rename_voicing = ttk.Button(frame_saved, text="Rename Voicing",
                                        command=self.rename_voicing)
        btn_rename_voicing.grid(row=2, column=0, pady=3, sticky="ew")

        btn_move_up = ttk.Button(frame_saved, text="Move Up",
                                 command=self.move_voicing_up)
        btn_move_up.grid(row=3, column=0, pady=3, sticky="ew")

        btn_move_down = ttk.Button(frame_saved, text="Move Down",
                                   command=self.move_voicing_down)
        btn_move_down.grid(row=4, column=0, pady=3, sticky="ew")

        btn_hotkey = ttk.Button(frame_saved, text="Set Hotkey",
                        command=self.assign_hotkey)
        btn_hotkey.grid(row=5, column=0, pady=3, sticky="ew")


        self.update_tree()

        # Preview checkbox
        chk_preview = ttk.Checkbutton(root, text="Preview when clicked",
                                      variable=self.preview_enabled)
        chk_preview.grid(row=3, column=0, padx=5, pady=5, sticky="w")


    ## ----------------------------------------------------------------------------------------------------------------
    ##               MÉTODOS DE LA CLASE
    ## ----------------------------------------------------------------------------------------------------------------

    ## ------------------------------
    ## Function: assign_hotkey
    ## Description: Asigna un hotkey al voicing seleccionado.
    ## ------------------------------
    def assign_hotkey(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Nada seleccionado", "Selecciona un voicing.")
            return

        item = sel[0]
        nombre = self.tree.item(item, "values")[1]

        hk = simpledialog.askstring("Hotkey", "Teclea 1 carácter para el hotkey:")

        if not hk:
            return

        hk = hk.lower()

        # evitar duplicados
        for v in self.voicings:
            if v.get("hotkey") == hk:
                v["hotkey"] = ""   # quitarlo del anterior

        # asignar al actual
        for v in self.voicings:
            if v["name"] == nombre:
                v["hotkey"] = hk

        save_voicings(self.voicings)
        messagebox.showinfo("Hotkey", f"Hotkey '{hk}' asignado al voicing '{nombre}'.")


    ## ------------------------------
    ## Function: on_voicing_click
    ## Description: Maneja el click en un voicing del treeview.
    ## ------------------------------
    def on_voicing_click(self, event):
        sel = self.tree.selection()
        if not sel:
            return

        item = sel[0]
        values = self.tree.item(item, "values")
        if not values:
            return

        # values = (root, name, notes)
        root_note = values[0]
        nombre = values[1]
        notas_str = values[2]

        # Normalizar notas_str -> lista
        notas = [n.strip() for n in notas_str.split(",") if n.strip()]

        # Guardar referencia
        idx = next((i for i, v in enumerate(self.voicings) if v["name"] == nombre), None)
        self.current_voicing_index = idx
        self.current_voicing_name = nombre

        # Actualizar etiqueta y listbox
        self.lbl_current_name.config(text=f"Current voicing: {nombre}")
        self.voicing_listbox.delete(0, tk.END)
        for n in notas:
            self.voicing_listbox.insert(tk.END, n)

        # Cargar root en comboboxes si está bien formado
        if root_note:
            m = re.match(r'^([A-G][#b]?)(-?\d+)$', root_note)
            if m:
                note_part = m.group(1)
                octave_part = m.group(2)
                # Ajustar nombre a la lista (usar # o b tal cual)
                if note_part in self.notas_base:
                    self.combo_root_nota.set(note_part)
                else:
                    # intentar alternativas (p. ej. 'Db'/'C#')
                    alt = note_part.upper()
                    if alt in self.notas_base:
                        self.combo_root_nota.set(alt)
                if octave_part in self.octavas:
                    self.combo_root_octava.set(octave_part)

        # Deshabilitar delete note hasta que seleccionen una nota
        self.btn_delete_note.state(["disabled"])

        # Habilitar Save (estás editando un voicing existente)
        self.btn_save.state(["!disabled"])

        # Reproducir preview si está habilitado
        if self.preview_enabled.get():
            reproducir_acorde_threaded(self.player, notas, duracion=1.0)


    ## ------------------------------
    ## Function: add_note
    ## Description: Agrega la nota seleccionada al voicing actual.
    ## ------------------------------
    def add_note(self):
        nota = self.combo_nota.get()
        octava = self.combo_octava.get()
        if nota == "" or octava == "":
            return

        nota_final = f"{nota}{octava}"
        if nota_final not in BD_Notas_Midi:
            messagebox.showerror("Nota inválida", f"La nota {nota_final} no existe.")
            return

        self.voicing_listbox.insert(tk.END, nota_final)

        # Si estás editando un voicing existente, permitir guardar
        if self.current_voicing_name:
            self.btn_save.state(["!disabled"])
        else:
            # Si es un voicing nuevo (no guardado), solo Save As estará disponible
            self.btn_save.state(["disabled"])


    ## ------------------------------
    ## Function: delete_selected_note
    ## Description: Elimina la nota seleccionada del voicing actual.
    ## ------------------------------
    def delete_selected_note(self):
        sel = self.voicing_listbox.curselection()
        if not sel:
            return
        self.voicing_listbox.delete(sel[0])
        self.btn_delete_note.state(["disabled"])

        # Permitir guardar cambios si viniste de un voicing existente
        if self.current_voicing_name:
            self.btn_save.state(["!disabled"])


    ## ------------------------------
    ## Function: on_note_select
    ## Description: Maneja la selección de una nota en el listbox del voicing actual.
    ## ------------------------------
    def on_note_select(self, event):
        sel = self.voicing_listbox.curselection()
        if not sel:
            self.btn_delete_note.state(["disabled"])
            return

        # Habilitar boton borrar nota
        self.btn_delete_note.state(["!disabled"])

        # Actualizar los combobox de nota y octava con la nota seleccionada
        nota_sel = self.voicing_listbox.get(sel[0])

        # Extraer nombre de nota y octava usando regex (soporta # y b y octavas de 1+ dígitos)
        m = re.match(r'^([A-Ga-g][#b]?)(-?\d+)$', nota_sel)
        if m:
            base_raw = m.group(1)
            base = base_raw[0].upper() + (base_raw[1] if len(base_raw) > 1 else "")
            octave = m.group(2)

            if base in self.notas_base:
                self.combo_nota.set(base)

            if octave in self.octavas:
                self.combo_octava.set(octave)


    ## ------------------------------
    ## Function: clear_notes
    ## Description: Limpia el voicing actual.
    ## ------------------------------
    def clear_notes(self):
        self.voicing_listbox.delete(0, tk.END)

        # Limpiar relación con voicing previo
        self.current_voicing_name = None
        self.current_voicing_index = None
        self.lbl_current_name.config(text="Current voicing: (none)")

        self.btn_save.state(["disabled"])
        self.btn_delete_note.state(["disabled"])
        # quitar selección del tree
        try:
            self.tree.selection_remove(self.tree.selection())
        except Exception:
            pass


    ## ------------------------------
    ## Function: save_voicing_as
    ## Description: Guarda el voicing actual con un nuevo nombre.
    ## ------------------------------
    def save_voicing_as(self):
        notas = list(self.voicing_listbox.get(0, tk.END))
        if not notas:
            messagebox.showwarning("Vacío", "No hay notas en el voicing.")
            return

        # Obtener root elegido por el usuario
        root_note = self.combo_root_nota.get()
        root_oct = self.combo_root_octava.get()
        if not root_note or not root_oct:
            messagebox.showwarning("Root faltante", "Selecciona la root (nota + octava) antes de guardar.")
            return
        root_full = f"{root_note}{root_oct}"

        nombre = simpledialog.askstring("Save As", "Nombre del voicing:")
        if not nombre:
            return

        # Remover si ya existía con ese nombre
        self.voicings = [v for v in self.voicings if v["name"] != nombre]

        # Agregar nuevo voicing con root
        self.voicings.append({"name": nombre, "root": root_full, "notes": notas})
        self.current_voicing_name = nombre
        self.current_voicing_index = next((i for i, v in enumerate(self.voicings) if v["name"] == nombre), None)
        self.lbl_current_name.config(text=f"Current voicing: {nombre}")

        save_voicings(self.voicings)
        self.update_tree()

        # Seleccionar el nuevo voicing en el tree
        for item in self.tree.get_children():
            vals = self.tree.item(item, "values")
            if vals and vals[1] == nombre:
                self.tree.selection_set(item)
                break

        self.btn_save.state(["!disabled"])


    ## ------------------------------
    ## Function: save_existing_voicing
    ## Description: Guarda los cambios en el voicing actualmente seleccionado.
    ## ------------------------------
    def save_existing_voicing(self):
        if not self.current_voicing_name:
            return  # nada que guardar

        notas = list(self.voicing_listbox.get(0, tk.END))

        # Leer root actual de comboboxes (el usuario puede haberlo cambiado)
        root_note = self.combo_root_nota.get()
        root_oct = self.combo_root_octava.get()
        if not root_note or not root_oct:
            messagebox.showwarning("Root faltante", "Selecciona la root (nota + octava) antes de guardar.")
            return
        root_full = f"{root_note}{root_oct}"

        for v in self.voicings:
            if v["name"] == self.current_voicing_name:
                v["notes"] = notas
                v["root"] = root_full
                break

        save_voicings(self.voicings)
        self.update_tree()
        messagebox.showinfo("Guardado", f"Voicing '{self.current_voicing_name}' actualizado.")

        # volver a seleccionar en tree para mantener consistencia visual
        for item in self.tree.get_children():
            vals = self.tree.item(item, "values")
            if vals and vals[1] == self.current_voicing_name:
                self.tree.selection_set(item)
                break


    ## ------------------------------
    ## Function: update_tree
    ## Description: Actualiza el contenido del treeview con los voicings actuales.
    ## ------------------------------
    def update_tree(self):
        self.tree.delete(*self.tree.get_children())
        for v in self.voicings:
            notas_str = ", ".join(v.get("notes", []))
            root_val = v.get("root", "?")
            name = v.get("name", "(unnamed)")
            hotkey = v.get("hotkey", "")
            self.tree.insert("", tk.END, values=(root_val, name, notas_str, hotkey))


    ## ------------------------------
    ## Function: delete_voicing
    ## Description: Elimina el voicing seleccionado.
    ## ------------------------------
    def delete_voicing(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Nada seleccionado", "Selecciona un voicing.")
            return

        item = sel[0]
        nombre = self.tree.item(item, "values")[1]  # (root, name, notes)

        if messagebox.askyesno("Eliminar", f"¿Eliminar voicing '{nombre}'?"):
            self.voicings = [v for v in self.voicings if v["name"] != nombre]
            save_voicings(self.voicings)
            self.update_tree()

            if nombre == self.current_voicing_name:
                self.clear_notes()


    ## ------------------------------
    ## Function: rename_voicing
    ## Description: Renombra el voicing seleccionado.
    ## ------------------------------
    def rename_voicing(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Nada seleccionado", "Selecciona un voicing.")
            return

        item = sel[0]
        old_name = self.tree.item(item, "values")[1]

        new_name = simpledialog.askstring("Rename", "Nuevo nombre:", initialvalue=old_name)
        if not new_name or new_name == old_name:
            return

        # Verificar duplicados
        if any(v["name"] == new_name for v in self.voicings):
            messagebox.showerror("Error", "Ya existe un voicing con ese nombre.")
            return

        for v in self.voicings:
            if v["name"] == old_name:
                v["name"] = new_name
                break

        # Actualizar estado actual si era el seleccionado
        if self.current_voicing_name == old_name:
            self.current_voicing_name = new_name
            self.lbl_current_name.config(text=f"Current voicing: {new_name}")

        save_voicings(self.voicings)
        self.update_tree()

        # re-seleccionar el item renombrado
        for item in self.tree.get_children():
            vals = self.tree.item(item, "values")
            if vals and vals[1] == new_name:
                self.tree.selection_set(item)
                break


    ## ------------------------------
    ## Function: move_voicing_up
    ## Description: Mueve el voicing seleccionado hacia arriba en la lista.
    ## ------------------------------
    def move_voicing_up(self):
        sel = self.tree.selection()
        if not sel:
            return

        item = sel[0]
        nombre = self.tree.item(item, "values")[1]

        idx = next((i for i, v in enumerate(self.voicings) if v["name"] == nombre), None)
        if idx is None or idx == 0:
            return

        self.voicings[idx - 1], self.voicings[idx] = self.voicings[idx], self.voicings[idx - 1]

        save_voicings(self.voicings)
        self.update_tree()

        # re-seleccionar la nueva posición
        children = self.tree.get_children()
        if idx - 1 < len(children):
            self.tree.selection_set(children[idx - 1])


    ## ------------------------------
    ## Function: move_voicing_down
    ## Description: Mueve el voicing seleccionado hacia abajo en la lista.
    ## ------------------------------
    def move_voicing_down(self):
        sel = self.tree.selection()
        if not sel:
            return

        item = sel[0]
        nombre = self.tree.item(item, "values")[1]

        idx = next((i for i, v in enumerate(self.voicings) if v["name"] == nombre), None)
        if idx is None or idx >= len(self.voicings) - 1:
            return

        self.voicings[idx + 1], self.voicings[idx] = self.voicings[idx], self.voicings[idx + 1]

        save_voicings(self.voicings)
        self.update_tree()

        children = self.tree.get_children()
        if idx + 1 < len(children):
            self.tree.selection_set(children[idx + 1])


    ## ------------------------------
    ## Function: on_key_press
    ## Description: Maneja la pulsación de teclas para hotkeys.
    ## \param event: evento de teclado.
    ## ------------------------------
    def on_key_press(self, event):
        key = event.char.lower()

        if not key:
            return

        # Buscar si algún voicing tiene asignado este hotkey
        for i, v in enumerate(self.voicings):
            if v.get("hotkey", "").lower() == key:
                # Lo encontramos → cargarlo igual que si lo hubieras cliqueado
                self.select_voicing_by_index(i)
                return


    ## ------------------------------
    ## Function: select_voicing_by_index
    ## Description: Selecciona un voicing en el treeview por su índice.
    ## \param index: índice del voicing en la lista.
    ## ------------------------------
    def select_voicing_by_index(self, index):
        children = self.tree.get_children()
        if index >= len(children):
            return

        item = children[index]
        self.tree.selection_set(item)
        self.tree.focus(item)
        self.on_voicing_click(None)


    ## ------------------------------
    ## Function: on_hotkey_press
    ## Description: Maneja la pulsación de hotkeys para reproducir acordes.
    ## \param event: evento de teclado.
    ## ------------------------------
    def on_hotkey_press(self, event):
        hk = event.keysym.lower()
        if not hk:
            return

        # evitar repetición por autorepeat
        if hk in self.active_hotkeys:
            return

        self.active_hotkeys.add(hk)

        # buscar voicing
        for v in self.voicings:
            if v.get("hotkey") == hk:
                notas = v.get("notes", [])
                if notas:
                    reproducir_acorde_mientras(self.player, notas, hk)
                return


    ## ------------------------------
    ## Function: on_hotkey_release
    ## Description: Maneja la liberación de hotkeys para detener acordes.
    ## \param event: evento de teclado.
    ## ------------------------------
    def on_hotkey_release(self, event):
        hk = event.keysym.lower()
        if not hk:
            return

        # si no estaba activado, ignorar release falso
        if hk not in self.active_hotkeys:
            return

        self.active_hotkeys.remove(hk)

        # buscar voicing y apagar
        for v in self.voicings:
            if v.get("hotkey") == hk:
                notas = v.get("notes", [])
                if notas:
                    detener_acorde(hk)
                return


    ## ------------------------------
    ## Function: load_other_json
    ## Description: Carga voicings desde otro archivo JSON.
    ## ------------------------------
    def load_other_json(self):
        # Ruta absoluta a la carpeta 'data' dentro de 'storage_engine'
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_dir = os.path.join(base_dir, "storage_engine", "data")

        ruta = filedialog.askopenfilename(
            initialdir=data_dir,
            title="Seleccionar archivo JSON",
            filetypes=[("JSON Files", "*.json")]
        )
        if not ruta:
            return

        # Abrir archivo seleccionado
        import json
        with open(ruta, "r") as f:
            data = json.load(f)

        voicings = data.get("voicings", [])

        save_voicings(voicings)

        self.voicings = voicings
        self.update_tree()
