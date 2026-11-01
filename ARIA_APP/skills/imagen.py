# -*- coding: utf-8 -*-
"""Skill ARIA: generar una imagen desde texto."""
import re

SKILL_ENABLED = True
try:
    import gen_imagen as _g
except Exception:
    _g = None


def match(msg):
    low = msg.lower()
    return any(k in low for k in ["genera una imagen", "genera imagen", "generar imagen",
                                   "crea una imagen", "dibuja una imagen", "dibujame",
                                   "imagen de", "imagina "])


def run(msg):
    if _g is None or not _g.disponible():
        return "Generador de imagen no disponible."
    m = re.search(r"(?:imagen de|genera una imagen de|genera una imagen|crea una imagen de|"
                  r"crea una imagen|dibuja una imagen de|dibuja una imagen|dibujame|imagina)\s*:?\s*(.+)$",
                  msg, re.I | re.S)
    prompt = (m.group(1).strip() if m else msg).strip()
    r = _g.generar(prompt)
    return r.get("resumen") or r.get("error") or "Sin resultado."
