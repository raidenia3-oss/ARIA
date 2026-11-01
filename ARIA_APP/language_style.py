# -*- coding: utf-8 -*-
"""ARIA - Guía de estilo de comunicación."""
ESTILO = {
    "inicio": "Saluda con calidez y una pregunta breve.",
    "respuesta": "Valida, resume y ofrece siguiente paso.",
    "cierre": "Cierra con invitación y una lección aprendida.",
}

def guia(modo="respuesta"):
    return ESTILO.get(modo, ESTILO["respuesta"])
