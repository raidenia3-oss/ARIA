# -*- coding: utf-8 -*-
"""ARIA - Planificador coarse-to-fine (idea de Next Concept Modeling, local, Regla v2).

En vez de improvisar una respuesta larga token a token, ARIA primero hace un BOCETO
(la estructura: los conceptos y su orden) y luego EXPANDE cada punto. Da respuestas
mas coherentes en un modelo chico (1.5B). No es la velocidad de NCM (eso necesita el
modelo entrenado), pero si su calidad estructural.

Costo: son 2+ pasadas = mas latencia. Por eso SOLO se usa en respuestas largas
(explicaciones, ensayos); el chat corto va en UNA pasada.

El cerebro entra como responder(texto)->texto. Si hay grafo de conocimiento, el
boceto se nutre de lo que ARIA ya sabe. Sin dependencias nuevas.
"""
import re

# senales de que la respuesta sera LARGA (vale la pena estructurar)
_SENALES_LARGO = [
    "explica", "explicame", "detalla", "describe", "ensayo", "resumen largo",
    "compara", "ventajas y desventajas", "paso a paso", "a fondo", "en detalle",
    "como funciona", "por que", "analiza", "profundiza", "guia", "tutorial",
]


def es_largo(pregunta, umbral_palabras=0):
    """Heuristica: decide si la respuesta merece el modo estructurado (2 pasadas)."""
    p = (pregunta or "").lower()
    if any(s in p for s in _SENALES_LARGO):
        return True
    # preguntas muy largas o con varias sub-preguntas tambien
    if len(pregunta) > 180 or pregunta.count("?") >= 2:
        return True
    return False


def _resp(responder, prompt):
    try:
        r = responder(prompt)
        if isinstance(r, dict):
            r = r.get("response") or r.get("text") or str(r)
        return str(r).strip()
    except Exception as exc:
        return "(cerebro no respondio: %s)" % exc


def _puntos_boceto(texto, maximo=6):
    """Extrae los puntos del boceto (lineas con vineta/numero)."""
    puntos = []
    for ln in (texto or "").splitlines():
        ln = ln.strip()
        m = re.match(r"^(?:[-*•]|\d+[\.\)])\s+(.*)$", ln)
        if m and m.group(1).strip():
            puntos.append(m.group(1).strip())
    if not puntos:  # si el cerebro no uso vinetas, parte por frases
        puntos = [s.strip() for s in re.split(r"[.\n]", texto or "") if len(s.strip()) > 8]
    return puntos[:maximo]


def responder_estructurado(responder, pregunta, grafo=None, forzar=False, maximo=5):
    """Responde en modo coarse-to-fine SI la pregunta es larga (o forzar=True).
    Si es corta, una sola pasada (modo 'directo').

    Devuelve {modo, boceto?, puntos?, respuesta}."""
    if not callable(responder):
        return {"error": "responder debe ser callable(texto)->texto"}

    if not forzar and not es_largo(pregunta):
        return {"modo": "directo", "respuesta": _resp(responder, pregunta)}

    # contexto del grafo (lo que ARIA ya sabe) para guiar el boceto
    contexto = ""
    if grafo is not None:
        try:
            sabidos = grafo.buscar(pregunta, k=3)
            if sabidos:
                contexto = (" Considera lo que ya se: "
                            + "; ".join(s.get("texto", "")[:80] for s in sabidos))
        except Exception:
            pass

    # PASE 1: boceto (estructura)
    p_boceto = ("Antes de responder, haz un BOCETO: lista de 3 a %d puntos clave (con "
                "vinetas) que deberia cubrir la respuesta a: '%s'.%s Solo el boceto."
                % (maximo, pregunta, contexto))
    boceto = _resp(responder, p_boceto)
    puntos = _puntos_boceto(boceto, maximo)
    if not puntos:
        # si no salio boceto util, cae a una sola pasada
        return {"modo": "directo", "respuesta": _resp(responder, pregunta)}

    # PASE 2: expandir cada punto
    partes = []
    for i, punto in enumerate(puntos, 1):
        p_exp = ("Desarrolla este punto de la respuesta a '%s', claro y conciso, sin "
                 "repetir los otros puntos:\n%d) %s" % (pregunta, i, punto))
        partes.append("%d) %s\n%s" % (i, punto, _resp(responder, p_exp)))

    respuesta = "\n\n".join(partes)
    return {"modo": "estructurado", "boceto": puntos, "respuesta": respuesta}
