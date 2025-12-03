import tkinter as tk
from midi_engine.midi_setup import iniciar_sistema_midi
from gui.voicing_builder_gui import VoicingBuilderGUI


## -----------------------------
## Function: main
## Description: Inicia la aplicacion principal con un menú que permite abrir el Voicing Builder en una ventana independiente.
## -----------------------------
def main():
    root = tk.Tk()
    root.title("Music Modular")

    # iniciar sistema MIDI una vez y compartir player con ventanas
    player = iniciar_sistema_midi()

    # Menú superior
    menubar = tk.Menu(root)
    root.config(menu=menubar)

    file_menu = tk.Menu(menubar, tearoff=False)
    menubar.add_cascade(label="File", menu=file_menu)

    # holder para mantener la referencia a la ventana Voicing Builder (una sola instancia)
    voicing_win = {"win": None}

    def open_voicing_builder():
        # Si ya existe y no fue destruida, llevar al frente
        if voicing_win["win"] and tk.Toplevel.winfo_exists(voicing_win["win"]):
            voicing_win["win"].lift()
            return

        # crear nueva ventana Toplevel para el Voicing Builder
        top = tk.Toplevel(root)
        top.title("Voicing Builder")
        voicing_win["win"] = top

        # instanciar la GUI dentro del Toplevel
        VoicingBuilderGUI(top, player)

        # cuando se cierre, limpiar la referencia
        def _on_close():
            try:
                voicing_win["win"] = None
                top.destroy()
            except Exception:
                pass

        top.protocol("WM_DELETE_WINDOW", _on_close)

    file_menu.add_command(label="Open Voicing Builder", command=open_voicing_builder)
    file_menu.add_separator()
    file_menu.add_command(label="Exit", command=root.quit)

    # Contenido sencillo de la ventana principal
    lbl = tk.Label(root, text="Music Modular — Main Window", padx=20, pady=20)
    lbl.pack()

    root.mainloop()


## -----------------------------
## Main execution
##
## Description: Ejecuta la función main si el script es el principal.
## -----------------------------
if __name__ == "__main__":
    main()
