# -*- coding: utf-8 -*-
"""ARIA - Motor emocional básico."""
EMOCIONES = {
    "triste": "tristeza",
    "feliz": "alegria",
    "enojado": "ira",
    "ansioso": "ansiedad",
}

def detectar(texto):
    t = (texto or "").lower()
    for k, v in EMOCIONES.items():
        if k in t:
            return v
    return "neutral"

def estrategia(emocion):
    return {
        "tristeza": "validar y acompañar",
        "alegria": "celebrar y profundizar",
        "ira": "calmar y no contradecir",
        "ansiedad": "pasos concretos y calma",
        "neutral": "conversar fluido",
    }.get(emocion, "conversar fluido")
