# -*- coding: utf-8 -*-
"""ARIA - Brief diario (resumen proactivo, idea del Private AI OS).

Al arrancar (o cuando lo pidas), ARIA te da un parte breve: que hizo sola desde la
ultima vez, que aprendio, que esta PENDIENTE de tu OK, como venias de animo, y el
estado del sistema. Es la 'morning brief' adaptada a un asistente personal.

Junta datos de: auditoria (lo que hizo), experiencia (lecciones), autonomia_guardia +
mejora (pendientes de aprobacion), conversacion (animo). Todo opcional y con fallback:
si un modulo no esta, esa seccion se omite. 100% local, Regla v2.

La composicion del texto (_componer) es PURA: testeable con datos inyectados.
"""
import time


def _componer(datos):
    """datos (dict) -> (lineas, texto). Puro, sin tocar otros modulos."""
    lineas = []
    lineas.append("BRIEF · %s" % datos.get("fecha", time.strftime("%Y-%m-%d %H:%M")))
    sis = datos.get("sistema")
    if sis:
        lineas.append("sistema: CPU %s%% · RAM %s%%" % (sis.get("cpu", "--"), sis.get("ram", "--")))
    aud = datos.get("auditoria")
    if aud:
        lineas.append("hice %d acciones (%d solas) desde la ultima vez"
                      % (aud.get("total", 0), aud.get("autonomas", 0)))
    pend = int(datos.get("pendientes", 0))
    if pend:
        lineas.append("** %d accion(es) esperan tu OK ** (di 'acciones pendientes')" % pend)
    lec = datos.get("lecciones") or []
    if lec:
        lineas.append("aprendi: " + "; ".join(str(x)[:60] for x in lec[:2]))
    animo = datos.get("animo")
    if animo and animo != "neutral":
        lineas.append("te noto viniendo con %s; aca estoy" % animo)
    extra = datos.get("nota")
    if extra:
        lineas.append(extra)
    if len(lineas) == 1:
        lineas.append("todo tranquilo. listo cuando me necesites.")
    return lineas, "\n".join(lineas)


def _sistema():
    try:
        import psutil
        return {"cpu": int(psutil.cpu_percent(None)),
                "ram": int(psutil.virtual_memory().percent)}
    except Exception:
        return None


def _auditoria():
    try:
        import auditoria
        r = auditoria.resumen()
        return {"total": r.get("total", 0), "autonomas": r.get("autonomas", 0)}
    except Exception:
        return None


def _pendientes():
    n = 0
    try:
        import autonomia_guardia
        n += len(autonomia_guardia.listar())
    except Exception:
        pass
    try:
        import mejora
        n += len(mejora.listar("pendiente"))
    except Exception:
        pass
    return n


def _lecciones():
    try:
        import experiencia
        return [x.get("leccion", "") for x in experiencia.leer(n=2)]
    except Exception:
        return []


def generar_brief(conversacion=None):
    """Arma el brief juntando lo que haya disponible. Devuelve {lineas, texto}."""
    animo = "neutral"
    if conversacion is not None:
        try:
            animo = conversacion.contexto().get("emocion_dominante", "neutral")
        except Exception:
            pass
    datos = {
        "fecha": time.strftime("%Y-%m-%d %H:%M"),
        "sistema": _sistema(),
        "auditoria": _auditoria(),
        "pendientes": _pendientes(),
        "lecciones": _lecciones(),
        "animo": animo,
    }
    lineas, texto = _componer(datos)
    return {"lineas": lineas, "texto": texto, "datos": datos}
