# ======================================================
# FILE: rhythm_engine/patterns.py
# ======================================================

import sys
import os
# agregamos la carpeta raíz (Music_Modular) al sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))



# Duraciones en "subdivisiones" (1 compás 4/4 = 16 semicorcheas)
DURACIONES = {
    "redonda": 16,
    "blanca": 8,
    "negra": 4,
    "corchea": 2,
    "semicorchea": 1,

    "silencio_redonda": 16,
    "silencio_blanca": 8,
    "silencio_negra": 4,
    "silencio_corchea": 2,
    "silencio_semicorchea": 1,
}

class RitmoPattern:
    """Representa un patrón de ritmos compuesto por compases.
    Cada compás es una lista de eventos; un evento es una cadena que
    coincide con una key de DURACIONES.
    """

    def __init__(self, name="new_pattern", compases=None, tempo=120):
        self.name = name
        self.tempo = tempo  # BPM
        if compases is None:
            self.compases = [[]]
        else:
            self.compases = compases

    def add_compas(self):
        self.compases.append([])

    def insert_compas(self, idx):
        self.compases.insert(idx, [])

    def delete_compas(self, idx):
        del self.compases[idx]

    def add_evento(self, compas_index, tipo):
        """Agrega un evento (nota o silencio) a un compás.
        Lanza ValueError si no cabe o si tipo inválido.
        """
        if tipo not in DURACIONES:
            raise ValueError(f"Tipo '{tipo}' no válido")

        if compas_index < 0 or compas_index >= len(self.compases):
            raise ValueError("Compás inexistente")

        actual = sum(DURACIONES[e] for e in self.compases[compas_index])
        dur = DURACIONES[tipo]

        if actual + dur > 16:
            raise ValueError("Este evento excede el compás (4/4)")

        self.compases[compas_index].append(tipo)

    def compas_estado(self, compas_index):
        total = sum(DURACIONES[e] for e in self.compases[compas_index])
        return total, 16

    def is_complete(self, compas_index):
        total, full = self.compas_estado(compas_index)
        return total == full

    def can_add(self, compas_index, tipo):
        if tipo not in DURACIONES:
            return False
        total = sum(DURACIONES[e] for e in self.compases[compas_index])
        return (total + DURACIONES[tipo]) <= 16

    def merge(self, other, merged_name):
        nuevo = RitmoPattern(merged_name)
        nuevo.compases = [list(c) for c in self.compases] + [list(c) for c in other.compases]
        return nuevo

    def to_dict(self):
        return {"name": self.name, "compases": self.compases, "tempo": self.tempo}

    @staticmethod
    def from_dict(d):
        return RitmoPattern(
            name=d.get("name", "new_pattern"),
            compases=d.get("compases", [[]]),
            tempo=d.get("tempo", 120)
        )
    
    def duracion_segundos(self, tipo):
        """
        Convierte la duración en subdivisiones (1=semicorchea) a segundos según tempo.
        """
        if tipo not in DURACIONES:
            raise ValueError(f"Tipo '{tipo}' no válido")
        semicorcheas = DURACIONES[tipo]
        # 1 negra = 1 beat, 1 beat = 4 semicorcheas
        beat = 60 / self.tempo  # duración de una negra en segundos
        return (semicorcheas / 4) * beat
    