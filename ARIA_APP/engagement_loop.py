# -*- coding: utf-8 -*-
"""ARIA - Bucle de engagement proactivo."""
def ciclo(ultimo_ts=None, temas=None, memoria=None):
    import proactive_nudges as pn
    nudge = pn.nudge_si_aplica(ultimo_ts, temas or [])
    if nudge:
        return nudge
    return "Escucho; ¿en qué te ayudo?"
