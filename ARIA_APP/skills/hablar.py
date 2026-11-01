# -*- coding: utf-8 -*-
"""Skill ARIA: decir algo en voz alta con la voz local (Piper)."""
import re

SKILL_ENABLED = True
try:
    import voz_piper as _v
except Exception:
    _v = None


def match(msg):
    low = msg.lower()
    return any(k in low for k in ["lee esto", "lee:", "di en voz alta", "dilo en voz alta",
                                   "habla:", "di:", "en voz alta"])


def run(msg):
    if _v is None or not _v.disponible():
        return "Voz no disponible: instala piper-tts en el entorno de ARIA."
    m = re.search(r"(?:lee esto|lee|di en voz alta|dilo en voz alta|habla|di|en voz alta)\s*:?\s*(.+)$",
                  msg, re.I | re.S)
    texto = (m.group(1).strip() if m else msg).strip()
    r = _v.hablar(texto)
    return r.get("resumen") or r.get("error") or "Listo."
