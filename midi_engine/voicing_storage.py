import json
import os

ARCHIVO_VOICINGS = "voicings.json"

## -----------------------------
## function: load_voicings
## description: Carga la lista de voicings desde un archivo JSON.
## \return: Lista de voicings (cada uno es lista de notas)
## -----------------------------
def load_voicings():
    if not os.path.exists(ARCHIVO_VOICINGS):
        save_voicings([])  # crea archivo inicial

    try:
        with open(ARCHIVO_VOICINGS, "r") as f:
            data = json.load(f)
            return data.get("voicings", [])
    except:
        return []

## -----------------------------
## function: save_voicings
## description: Guarda la lista de voicings en un archivo JSON.
## \param voicings_list: Lista de voicings (cada uno es lista de notas)
## \return: None
## -----------------------------
def save_voicings(voicings_list):
    data = {"voicings": voicings_list}
    with open(ARCHIVO_VOICINGS, "w") as f:
        json.dump(data, f, indent=4)
