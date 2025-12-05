# ======================================================
# FILE: storage_engine/rhythm_storage.py
# ======================================================
"""
Funciones para guardar/cargar patrones (JSON) en storage_engine/data
"""
import os
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "storage_engine" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_FILE = DATA_DIR / "rhythms.json"


def save_patterns(patterns, filepath=None):
    filepath = Path(filepath) if filepath else DEFAULT_FILE
    data = [p.to_dict() for p in patterns]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_patterns(filepath=None):
    filepath = Path(filepath) if filepath else DEFAULT_FILE
    if not filepath.exists():
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        raw = json.load(f)
    from rhythm_engine.patterns import RitmoPattern
    return [RitmoPattern.from_dict(x) for x in raw]