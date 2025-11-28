from mido import MidiFile, MidiTrack, Message
from .notes_db import BD_Notas_Midi

## -----------------------------
## Function: crear_midi
## Description: Crea un archivo MIDI a partir de una lista de notas MIDI y duraciones.
##
## \param nombre_archivo: Nombre del archivo MIDI a crear.
## \param midi_numeros: Lista de números MIDI de las notas.
## \param duraciones: Lista de duraciones en segundos para cada nota.
## \param tempo: Tempo en microsegundos por negra (default 500000 = 120 BPM).
## \param ticks_per_beat: Ticks por negra (default 480).
##
## \return: None
## -----------------------------
def crear_midi(nombre_archivo, midi_numeros, duraciones, tempo=500000, ticks_per_beat=480):
    midi = MidiFile(ticks_per_beat=ticks_per_beat)
    track = MidiTrack()
    midi.tracks.append(track)
    us_per_tick = tempo / ticks_per_beat

    for num, dur in zip(midi_numeros, duraciones):
        ticks = int(dur * 1_000_000 / us_per_tick)
        if num != -1:
            track.append(Message('note_on', note=num, velocity=64, time=0))
            track.append(Message('note_off', note=num, velocity=64, time=ticks))
        else:
            track.append(Message('note_off', note=0, velocity=0, time=ticks))

    midi.save(nombre_archivo)
