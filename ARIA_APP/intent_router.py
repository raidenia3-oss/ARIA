# -*- coding: utf-8 -*-
"""ARIA - Router de intenciones básico."""
INTENTS = {
    "social": ["cita", "ligar", "charlar", "social"],
    "reel": ["reel", "instagram", "video"],
    "conocimiento": ["grafo", "aprende", "explica"],
    "mejora": ["mejora", "propón", "aprueba"],
}

def detectar(texto):
    t = (texto or "").lower()
    for intent, keys in INTENTS.items():
        if any(k in t for k in keys):
            return intent
    return "general"
