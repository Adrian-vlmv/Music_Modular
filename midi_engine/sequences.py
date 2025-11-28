import time
from .playback import reproducir_nota, reproducir_midi

## -----------------------------
## Function: reproducir_notas_secuenciales
## Description: Reproduce una secuencia de notas, manejando las notas ligadas ("L").
## \param player: Objeto del reproductor MIDI.
## \param notas: Lista de notas (ej. ["C4", "D4", "L", "E4"]).
## \param duraciones: Lista de duraciones en segundos para cada nota.
## \return: None
## -----------------------------
def reproducir_notas_secuenciales(player, notas, duraciones):
    i = 0
    while i < len(notas):
        if i + 1 < len(notas) and notas[i + 1] == "L":
            nota_inicial = notas[i]
            duracion_combinada = duraciones[i]
            while i + 1 < len(notas) and notas[i + 1] == "L":
                duracion_combinada += duraciones[i + 1]
                i += 1
            reproducir_nota(player, nota_inicial, duracion_combinada)
            i += 1
        else:
            reproducir_nota(player, notas[i], duraciones[i])
            i += 1
