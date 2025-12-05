## ======================================================
## File: midi_engine/playback.py
## ======================================================

import time
from .notes_db import BD_Notas_Midi

## -----------------------------
## Function: reproducir_nota
## Description: Reproduce una nota dada su representación en texto y duración.
## \param player: Objeto del reproductor MIDI.
## \param nota: Nota en formato texto (ej. "C4", "D#5", "-").
## \param duracion: Duración en segundos.
## \return: None
## -----------------------------
def reproducir_nota(player, nota, duracion):
    if nota in BD_Notas_Midi:
        midi_num = BD_Notas_Midi[nota]
        player.note_on(midi_num, 127)
        time.sleep(duracion)
        player.note_off(midi_num, 127)
    elif nota == "-":
        time.sleep(duracion)
    elif nota != "L":
        print(f"Nota '{nota}' no encontrada.")
