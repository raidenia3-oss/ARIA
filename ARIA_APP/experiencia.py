# -*- coding: utf-8 -*-
"""ARIA - Biblioteca de experiencia (idea de Harness2 'experience.md', local, Regla v2).

ARIA guarda LECCIONES de lo que funciono y lo que fallo, para ser mas eficiente en
tareas futuras. Dos caras:
  - experience.md   -> legible por humanos (lo puedes leer/editar tu)
  - experience.jsonl-> fuente estructurada para recuperar lecciones relevantes

Antes de una tarea, ARIA llama relevantes(tarea) y lee lo aprendido antes.
EXPLORAR PARA MEJORAR: si hay memoria semantica, 'relevantes' recupera por significado.

Sin red, sin servidores. Todo archivo local.
"""
import os
import json
import time
import re

_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(_DIR, "data")
_MD = os.path.join(_DATA, "experience.md")
_JSONL = os.path.join(_DATA, "experience.jsonl")


_SEM_CACHE = "sin_calcular"   # se calcula una sola vez por proceso


def _sem():
    global _SEM_CACHE
    if _SEM_CACHE != "sin_calcular":
        return _SEM_CACHE
    _SEM_CACHE = None
    try:
        import memory_semantic as ms
        if ms.disponible():
            _SEM_CACHE = ms.MemoriaSemantica(os.path.join(_DATA, "experiencia_sem.db"))
    except Exception:
        _SEM_CACHE = None
    return _SEM_CACHE


def registrar(leccion, contexto="", resultado="exito", tema=""):
    """Guarda una leccion. resultado: 'exito' | 'fallo' | 'nota'."""
    leccion = (leccion or "").strip()
    if not leccion:
        return {"error": "leccion vacia"}
    os.makedirs(_DATA, exist_ok=True)
    item = {"ts": time.time(), "fecha": time.strftime("%Y-%m-%d %H:%M"),
            "tema": tema, "resultado": resultado,
            "contexto": contexto[:300], "leccion": leccion[:600]}
    # 1) fuente estructurada
    try:
        with open(_JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    except Exception as exc:
        return {"error": "no pude escribir jsonl: %s" % exc}
    # 2) vista humana (append a experience.md)
    icono = {"exito": "[OK]", "fallo": "[X]", "nota": "[~]"}.get(resultado, "[~]")
    linea = "- %s **%s** (%s%s): %s\n" % (
        icono, item["fecha"], tema or "general",
        (" / " + contexto[:60]) if contexto else "", leccion)
    try:
        nuevo = not os.path.isfile(_MD)
        with open(_MD, "a", encoding="utf-8") as f:
            if nuevo:
                f.write("# ARIA - Experiencia (lecciones aprendidas)\n\n")
            f.write(linea)
    except Exception:
        pass
    # 3) indexar en memoria semantica (opcional)
    sem = _sem()
    if sem is not None:
        try:
            sem.recordar(leccion, meta=json.dumps({"tema": tema, "resultado": resultado},
                                                  ensure_ascii=False))
        except Exception:
            pass
    return {"ok": True, "leccion": leccion}


def _cargar():
    items = []
    if not os.path.isfile(_JSONL):
        return items
    for ln in open(_JSONL, encoding="utf-8"):
        ln = ln.strip()
        if ln:
            try:
                items.append(json.loads(ln))
            except Exception:
                pass
    return items


def leer(tema=None, n=10, solo=None):
    """Lecciones recientes. 'solo' filtra por resultado (exito/fallo)."""
    items = _cargar()
    if tema:
        items = [x for x in items if x.get("tema") == tema]
    if solo:
        items = [x for x in items if x.get("resultado") == solo]
    return items[-n:]


def _palabras(t):
    return set(w for w in re.findall(r"\w+", (t or "").lower()) if len(w) > 4)


def relevantes(tarea, k=5):
    """Lecciones mas relevantes a una tarea. Semantica si esta; si no, por palabras."""
    sem = _sem()
    if sem is not None:
        res = sem.buscar(tarea, k=k)
        if res:
            return [{"leccion": r["texto"], "meta": r.get("meta")} for r in res]
    # fallback: solape de palabras
    objetivo = _palabras(tarea)
    punt = []
    for x in _cargar():
        score = len(objetivo & _palabras(x.get("leccion", "")))
        if score:
            punt.append((score, x))
    punt.sort(key=lambda s: -s[0])
    return [{"leccion": x["leccion"], "tema": x.get("tema"),
             "resultado": x.get("resultado")} for _, x in punt[:k]]


def resumen():
    items = _cargar()
    exitos = sum(1 for x in items if x.get("resultado") == "exito")
    fallos = sum(1 for x in items if x.get("resultado") == "fallo")
    temas = sorted({x.get("tema", "") for x in items if x.get("tema")})
    return {"total": len(items), "exitos": exitos, "fallos": fallos,
            "temas": temas, "archivo": _MD}
