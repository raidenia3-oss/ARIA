# -*- coding: utf-8 -*-
"""ARIA - Inner thoughts: razonamiento covert y momento adecuado para intervenir."""
import time

def pensar(contexto="", memoria=None):
    pensamientos = []
    if memoria:
        pensamientos.append("Recuerdo: %s" % str(memoria)[:100])
    if contexto:
        pensamientos.append("Contexto actual: %s" % str(contexto)[:100])
    pensamientos.append("Objetivo: ayudar sin abrumar, validar y guiar.")
    return pensamientos

def momento_de_intervenir(ultimo_mensaje_ts=None, silencio_seg=120):
    if ultimo_mensaje_ts is None:
        return False
    return (time.time() - ultimo_mensaje_ts) >= silencio_seg
