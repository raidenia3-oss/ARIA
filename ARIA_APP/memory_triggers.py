# -*- coding: utf-8 -*-
"""ARIA - Triggers de recuperación de memoria."""
def trigger_para(texto):
    t = (texto or "").lower()
    if "reel" in t or "instagram" in t:
        return "reel"
    if "cita" in t or "ligar" in t:
        return "social"
    if "memoria" in t or "recuerda" in t:
        return "memoria"
    return "general"
