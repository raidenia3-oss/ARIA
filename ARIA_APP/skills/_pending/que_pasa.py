# -*- coding: utf-8 -*-
# BORRADOR de skill autogenerado por ARIA (NO se ejecuta hasta aprobar).
# Peticion original de Daniel: 'que pasa'
# match() ya esta cableado a las palabras clave detectadas.
# Falta implementar run(). Para activar: "aprueba skill que_pasa".

SKILL_ENABLED = False

import re

_DISPARADOR = re.compile(r"(pasa)", re.I)

def match(msg):
    return bool(_DISPARADOR.search(msg))

def run(msg):
    # TODO: implementar la respuesta (sin red ni servidores).
    return ""  # TODO
