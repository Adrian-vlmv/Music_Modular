import json
import os

## --------------------------------------------------------------------------------------------------------------------
##                        CONFIG
## --------------------------------------------------------------------------------------------------------------------

# Carpeta donde se almacenarán los voicings
VOICINGS_DIR = os.path.join(os.path.dirname(__file__), "data")

# Archivo final dentro de la carpeta
ARCHIVO_VOICINGS = os.path.join(VOICINGS_DIR, "voicings.json")


## --------------------------------------------------------------------------------------------------------------------
##                       FUNCTIONS
## --------------------------------------------------------------------------------------------------------------------


## -----------------------------
## function: ensure_directory
## description: Asegura que la carpeta de voicings exista.
## -----------------------------
def ensure_directory():
    """Crea la carpeta de voicings si no existe."""
    if not os.path.exists(VOICINGS_DIR):
        os.makedirs(VOICINGS_DIR)

## -----------------------------
## function: load_voicings
## description: Carga la lista de voicings desde un archivo JSON.
## \return: Lista de voicings (cada uno es lista de notas)
## -----------------------------
def load_voicings():
    ensure_directory()

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
    ensure_directory()
    data = {"voicings": voicings_list}

    with open(ARCHIVO_VOICINGS, "w") as f:
        json.dump(data, f, indent=4)

