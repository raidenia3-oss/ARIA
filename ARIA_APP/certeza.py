# -*- coding: utf-8 -*-
"""ARIA - Integridad: 'no inventes, pregunta' (del Private AI OS).

Regla dura: ante un dato especifico que ARIA NO tiene (precio, fecha, nombre, numero,
cifra), NO se lo inventa. O lo busca en una fuente, o te PREGUNTA/avisa que no esta
segura. Mejor un 'no se, lo confirmo' que un dato falso dicho con seguridad.

Este modulo decide cuando ESCALAR (preguntar/buscar) en vez de responder de memoria.
Puro y testeable. 100% local, Regla v2.
"""
import re

# senales de que la pregunta pide un DATO ESPECIFICO (no opinion ni charla)
_FACTUAL = [
    r"\bcuanto\b", r"\bcuantos\b", r"\bcuando\b", r"\bque dia\b", r"\bque fecha\b",
    r"\bque hora\b", r"\bquien es\b", r"\bprecio\b", r"\bcuesta\b", r"\bvale\b",
    r"\bnumero de\b", r"\btelefono\b", r"\bdireccion\b", r"\bcuantas\b",
    r"\ben que ano\b", r"\bporcentaje\b", r"\bcifra\b", r"\bestadistica\b",
    r"\bcotizacion\b", r"\bultim[oa]s? (precio|version|noticia|dato)",
]
# charla/opinion: NO requiere fuente (ahi ARIA puede responder normal)
_NO_FACTUAL = [r"\bque opinas\b", r"\bque piensas\b", r"\bcomo te sientes\b",
               r"\bque prefieres\b", r"\bayudame a\b", r"\bexplica\b", r"\bque tal\b"]


def es_factual_especifico(pregunta):
    """True si la pregunta pide un dato concreto y verificable."""
    p = (pregunta or "").lower()
    if any(re.search(rx, p) for rx in _NO_FACTUAL):
        return False
    return any(re.search(rx, p) for rx in _FACTUAL)


def debe_escalar(pregunta, tiene_fuente=False, en_memoria=False):
    """True si ARIA deberia PREGUNTAR/BUSCAR en vez de responder de memoria:
    es un dato especifico y NO lo tiene ni en una fuente ni en su memoria."""
    return es_factual_especifico(pregunta) and not (tiene_fuente or en_memoria)


def frase_escalada(tema=""):
    """Frase honesta para cuando ARIA no tiene el dato (no inventa)."""
    t = (" sobre %s" % tema) if tema else ""
    return ("No quiero inventarte un dato%s. Puedo buscarlo en una fuente, o si tu lo "
            "sabes, confirmamelo y seguimos." % t)
