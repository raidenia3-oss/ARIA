# -*- coding: utf-8 -*-
"""ARIA - Compositor de respuestas con contexto social/emocional/memoria."""
def componer(texto, emocion="neutral", lecciones=None, estilo="amable"):
    lecciones = lecciones or []
    partes = ["Validación: entiendo lo que dices.", "Emoción: %s." % emocion]
    if lecciones:
        partes.append("Lección relevante: %s" % lecciones[0])
    partes.append("Siguiente paso: %s" % texto[:80])
    return " ".join(partes)
