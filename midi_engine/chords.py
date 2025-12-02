## --------------------------------------------------------------------------------------------------------------------
##                                           IMPORTS
## --------------------------------------------------------------------------------------------------------------------

import time
from .notes_db import BD_Notas_Midi
import threading


## --------------------------------------------------------------------------------------------------------------------
##                                           GLOBAL VARIABLES
## --------------------------------------------------------------------------------------------------------------------
holding_flags = {}   # estado por hotkey → True/False


## --------------------------------------------------------------------------------------------------------------------
##                                            FUNCTIONS
## --------------------------------------------------------------------------------------------------------------------

## -----------------------------
## Function: reproducir_acorde
##
## Description: Reproduce un acorde dado una lista de notas y duracion.
##
## \param player: Objeto del reproductor MIDI.
## \param notas: Lista de notas (ej. ["C4", "E4", "G4"]).
## \param duracion: Duraciรณn en segundos.
##
## \return: None
## -----------------------------
def reproducir_acorde(player, notas, duracion):
    midi_nums = [BD_Notas_Midi[n] for n in notas if n in BD_Notas_Midi]
    for m in midi_nums:
        player.note_on(m, 127)
    time.sleep(duracion)
    for m in midi_nums:
        player.note_off(m, 127)


## -----------------------------
## Function: reproducir_acorde_threaded
##
## Description: Reproduce un acorde en un hilo independiente.
##
## \param player: Objeto del reproductor MIDI.
## \param notas: Lista de notas (ej. ["C4", "E4", "G4"]).
## \param duracion: Duracion en segundos.
##
## \return: None
## -----------------------------
def reproducir_acorde_threaded(player, notas, duracion):
    # Apagar notas previas en un thread
    threading.Thread(
        # Cortar notas previas antes de iniciar el nuevo hilo
        apagar_todas_las_notas(player)
    ).start()

    # Reproducir acorde en un thread
    threading.Thread(
        target=reproducir_acorde,
        args=(player, notas, duracion),
        daemon=True
    ).start()


## -----------------------------
## Function: apagar_todas_las_notas
## Description: Apaga todas las notas MIDI.
## \param player: Objeto del reproductor MIDI.
## \return: None
## -----------------------------
def apagar_todas_las_notas(player):
    for note in range(128):
        player.note_off(note, 0)



## -----------------------------
## Function: reproducir_notas_secuenciales
##
## Description: Reproduce una lista de notas una por una.
## Cada nota se enciende, espera 'duracion', y se apaga
##
## \param player: reproductor MIDI
## \param notas: lista ["C4", "E4", ...]
## \param duracion: duración de cada nota en segundos
## -----------------------------
def reproducir_notas_secuenciales(player, notas, duracion):
    # Convertir notas a números MIDI
    midi_nums = [BD_Notas_Midi[n] for n in notas if n in BD_Notas_Midi]

    for m in midi_nums:
        player.note_on(m, 120)
        time.sleep(duracion)
        player.note_off(m, 120)


## -----------------------------
## Function: reproducir_notas_secuenciales_threaded
##
## Description: Versión en hilo independiente.
## Apaga notas previas antes de iniciar la ejecución.
## -----------------------------
def reproducir_notas_secuenciales_threaded(player, notas, duracion):
    # Apaga notas anteriores
    apagar_todas_las_notas(player)

    threading.Thread(
        target=reproducir_notas_secuenciales,
        args=(player, notas, duracion),
        daemon=True
    ).start()


## -----------------------------
## Function: reproducir_notas_ordenadas
##
## Description:
##   Toca las notas en orden de tono:
##   primero las graves, luego las agudas.
##
## \param player: reproductor MIDI
## \param notas: lista ["G4", "C3", "E4", ...]
## \param duracion: duración de cada nota
## -----------------------------
def reproducir_notas_ordenadas(player, notas, duracion):
    # Convertir notas a números MIDI válidos
    midi_nums = [BD_Notas_Midi[n] for n in notas if n in BD_Notas_Midi]

    # Ordenar por gravedad (menor = más grave)
    midi_nums.sort()

    # Reproducir secuencialmente
    for m in midi_nums:
        player.note_on(m, 120)
        time.sleep(duracion)
        player.note_off(m, 120)


## -----------------------------
## Function: reproducir_notas_ordenadas_threaded
##
## Description: Versión con hilo independiente.
## Apaga notas previas antes de reproducir.
## -----------------------------
def reproducir_notas_ordenadas_threaded(player, notas, duracion):
    # Cortar cualquier nota activa antes de iniciar
    apagar_todas_las_notas(player)

    threading.Thread(
        target=reproducir_notas_ordenadas,
        args=(player, notas, duracion),
        daemon=True
    ).start()


def reproducir_acorde_mientras(player, notas, hotkey):
    midi_nums = [BD_Notas_Midi[n] for n in notas if n in BD_Notas_Midi]

    # Marcar que esta hotkey está activa
    holding_flags[hotkey] = True

    def hold():
        # ENCENDER una sola vez
        for m in midi_nums:
            player.note_on(m, 127)

        # Esperar mientras la tecla está presionada
        while holding_flags.get(hotkey, False):
            time.sleep(0.01)

        # Cuando se suelta → apagar notas
        for m in midi_nums:
            player.note_off(m, 0)

    threading.Thread(target=hold, daemon=True).start()


def detener_acorde(player, notas, hotkey):
    holding_flags[hotkey] = False
