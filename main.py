import tkinter as tk

from midi_engine.midi_setup import iniciar_sistema_midi
from gui.voicing_builder_gui import VoicingBuilderGUI

def main():
    root = tk.Tk()

    player = iniciar_sistema_midi()

    gui = VoicingBuilderGUI(root, player)

    root.mainloop()

if __name__ == "__main__":
    main()
