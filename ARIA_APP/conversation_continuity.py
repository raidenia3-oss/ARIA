# -*- coding: utf-8 -*-
"""ARIA - Continuidad conversacional entre sesiones."""
import json, os, time
_P = os.path.join(os.path.dirname(__file__), "data", "continuidad.json")

def guardar(tema, contexto=""):
    os.makedirs(os.path.dirname(_P), exist_ok=True)
    with open(_P, "w", encoding="utf-8") as f:
        json.dump({"tema": tema, "contexto": contexto[:300], "ts": time.time()}, f, ensure_ascii=False)

def cargar():
    if not os.path.isfile(_P):
        return None
    try:
        return json.load(open(_P, encoding="utf-8"))
    except Exception:
        return None
