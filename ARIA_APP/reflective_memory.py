# -*- coding: utf-8 -*-
"""ARIA - Memoria reflectiva: prospectiva y retrospectiva para mejorar respuestas."""
def prospectiva(contexto):
    return ["Anticipar: %s" % str(contexto)[:80], "Preparar respuesta útil y breve"]

def retrospectiva(respuesta, resultado):
    return "Lección: %s -> %s" % (str(respuesta)[:60], resultado)
