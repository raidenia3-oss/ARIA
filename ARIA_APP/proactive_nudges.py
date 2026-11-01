# -*- coding: utf-8 -*-
"""ARIA - Nudges proactivos basados en memoria y tiempo."""
import time

def nudge_si_aplica(ultimo_ts=None, temas=None):
    temas = temas or []
    if ultimo_ts is not None and time.time() - ultimo_ts < 300:
        return None
    if temas:
        return "¿Quieres retomar %s?" % temas[0]
    return "¿Te ayudo con algo pendiente?"
