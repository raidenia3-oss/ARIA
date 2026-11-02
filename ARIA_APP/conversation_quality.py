# -*- coding: utf-8 -*-
"""ARIA - Evaluador simple de calidad conversacional."""
def evaluar(respuesta):
    r = (respuesta or "").strip()
    score = 0.0
    if len(r) >= 20:
        score += 0.4
    if "?" in r:
        score += 0.3
    if any(w in r.lower() for w in ("entiendo", "valido", "ayudo")):
        score += 0.3
    return round(min(1.0, score), 2)
