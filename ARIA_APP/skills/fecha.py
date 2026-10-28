# -*- coding: utf-8 -*-
"""Skill ARIA: fecha y hora local, en espanol, sin depender del locale."""
from datetime import datetime

SKILL_ENABLED = True

_DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def match(msg):
    low = msg.lower()
    return any(k in low for k in ["que hora", "qué hora", "hora es", "que dia", "qué día",
                                   "dia es hoy", "día es hoy", "fecha de hoy", "que fecha",
                                   "qué fecha"])


def run(msg):
    now = datetime.now()
    low = msg.lower()
    if "hora" in low:
        return now.strftime("Son las %H:%M, Daniel.")
    dia = _DIAS[now.weekday()]
    return "Hoy es %s %d de %s de %d." % (dia, now.day, _MESES[now.month - 1], now.year)
