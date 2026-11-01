# -*- coding: utf-8 -*-
"""ARIA - Starters personalizados e iniciativa conversacional (inspirado en IceBreaker/Topic-Initiator)."""
import time, random

def starters_para(usuario="", memoria=None):
    base = [
        "Hola %s, ¿qué quieres lograr hoy?" % (usuario or "Daniel"),
        "¿Seguimos con lo pendiente o quieres algo nuevo?",
        "Puedo ayudarte a analizar un reel, practicar una cita o estudiar un tema.",
    ]
    if memoria:
        try:
            base.insert(0, "Recordé esto: %s" % str(memoria)[:120])
        except Exception:
            pass
    return base

def elegir_starter(usuario="", memoria=None):
    return random.choice(starters_para(usuario, memoria))

def checkin_pendiente(temas=None):
    temas = temas or []
    if not temas:
        return "¿Tienes algún tema pendiente para hoy?"
    return "¿Quieres retomar %s?" % temas[0]
