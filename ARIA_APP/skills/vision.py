# -*- coding: utf-8 -*-
"""Skill ARIA: Ojos de Dios - vision local (ver ambiente, reconocer a Daniel, vigilar)."""
import re

SKILL_ENABLED = True

try:
    import vision_eye as _v
except Exception:
    _v = None


def match(msg):
    low = msg.lower()
    return any(k in low for k in [
        "que ves", "qué ves", "ver ambiente", "mira la camara", "mira la cámara",
        "camara", "cámara", "reconoce", "reconóceme", "soy yo", "quien soy", "quién soy",
        "aprende mi cara", "enrola", "enrolar", "vigila", "vigilancia", "ojos de dios", "vision"])


def _r(d):
    return (d.get("resumen") or d.get("error") or "Sin resultado.") if isinstance(d, dict) else str(d)


def run(msg):
    if _v is None or not _v.disponible():
        return "Vision no disponible: instala opencv-contrib-python en el entorno de ARIA."
    low = msg.lower()
    if any(k in low for k in ["aprende mi cara", "enrola", "enrolar"]):
        return _r(_v.enrolar())
    if any(k in low for k in ["reconoce", "reconóceme", "soy yo", "quien soy", "quién soy"]):
        return _r(_v.reconocer())
    if any(k in low for k in ["vigila", "vigilancia"]):
        return _r(_v.vigilar())
    return _r(_v.ver_ambiente())
