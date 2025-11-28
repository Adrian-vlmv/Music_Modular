import pygame.midi
import sys

## -----------------------------
## Function: iniciar_sistema_midi
## Description: Inicializa el sistema MIDI y abre el puerto de salida.
## \return: Objeto del reproductor MIDI.
## -----------------------------
def iniciar_sistema_midi():
    pygame.midi.init()
    try:
        player = pygame.midi.Output(1)
    except Exception as e:
        print(f"Error al abrir el puerto MIDI: {e}")
        sys.exit(1)
    return player

## -----------------------------
## Function: listar_dispositivos_midi
## Description: Lista los dispositivos MIDI disponibles.
## \return: None
## -----------------------------
def listar_dispositivos_midi():
    print("Dispositivos MIDI disponibles:")
    for i in range(pygame.midi.get_count()):
        info = pygame.midi.get_device_info(i)
        nombre = info[1].decode()
        tipo = "Salida" if info[3] else "Entrada"
        print(f"ID: {i}, Nombre: {nombre}, Tipo: {tipo}")
