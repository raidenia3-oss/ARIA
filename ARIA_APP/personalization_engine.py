# -*- coding: utf-8 -*-
"""ARIA - Personalización de tono y estilo conversacional."""
TONOS = {
    "amable": "Usa calidez, validación y frases cortas.",
    "directo": "Sé claro, conciso y orientado a acción.",
    "coach": "Guía con pasos y preguntas, sin regañar.",
}

def adaptar(texto, tono="amable"):
    guia = TONOS.get(tono, TONOS["amable"])
    return "%s\n%s" % (guia, texto)
