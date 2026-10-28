# -*- coding: utf-8 -*-
"""Skill ARIA: recuerdo semantico ('que recuerdas sobre...', 'que hablamos de...')."""
import os

SKILL_ENABLED = True
try:
    import memory_semantic as _ms
except Exception:
    _ms = None
_MEM = None


def _mem():
    global _MEM
    if _MEM is None and _ms is not None and _ms.disponible():
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # ARIA_APP
        _MEM = _ms.MemoriaSemantica(os.path.join(here, "data", "semantica.db"))
    return _MEM


def match(msg):
    low = msg.lower()
    return any(k in low for k in ["recuerdas", "recuerda cuando", "que hablamos", "qué hablamos",
                                   "que sabes de", "qué sabes de", "recuerdo sobre", "en tu memoria",
                                   "que recuerdas", "qué recuerdas"])


def run(msg):
    m = _mem()
    if m is None:
        return "Memoria semantica no disponible: instala sqlite-vec y fastembed."
    res = m.buscar(msg, k=3)
    if not res:
        return "No encuentro nada relacionado en mi memoria todavia, Daniel."
    out = ["Esto recuerdo:"]
    for r in res:
        out.append("- " + r["texto"].replace("\n", " / "))
    return "\n".join(out)
