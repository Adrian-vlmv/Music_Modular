from midi_engine.midi_setup import iniciar_sistema_midi, listar_dispositivos_midi
from midi_engine.playback import reproducir_nota
from midi_engine.sequences import reproducir_notas_secuenciales
from midi_engine.chords import reproducir_acorde

player = iniciar_sistema_midi()
listar_dispositivos_midi()




reproducir_nota(player, "C4", 5)
