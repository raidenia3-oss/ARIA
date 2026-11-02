# -*- coding: utf-8 -*-
"""ARIA - Log de auditoria (todo lo que ARIA hace queda registrado).

Idea del 'Private AI OS': registro completo de cada accion, sobre todo las AUTONOMAS.
Asi puedes revisar que hizo ARIA sola, cuando y con que resultado. Es tu caja negra.

data/auditoria/acciones.jsonl (estructurado) + lectura/resumen. 100% local, Regla v2.
Lo llaman: la guardia de autonomia, mejora, act() del runtime, y cualquier accion
con efecto. Append-only (no se reescribe el historial).
"""
import os
import json
import time

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "auditoria")
_LOG = os.path.join(_DIR, "acciones.jsonl")


def registrar(accion, detalle="", resultado="", autonomo=False, tipo="accion"):
    """Anota una accion. autonomo=True si la inicio ARIA sola (no Daniel)."""
    item = {
        "ts": time.time(),
        "fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tipo": tipo,                      # accion | mejora | autonomia | error | aviso
        "accion": str(accion)[:120],
        "detalle": str(detalle)[:400],
        "resultado": str(resultado)[:200],
        "autonomo": bool(autonomo),
    }
    try:
        os.makedirs(_DIR, exist_ok=True)
        with open(_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return item


def _cargar():
    if not os.path.isfile(_LOG):
        return []
    out = []
    for ln in open(_LOG, encoding="utf-8"):
        ln = ln.strip()
        if ln:
            try:
                out.append(json.loads(ln))
            except Exception:
                pass
    return out


def leer(n=50, solo_autonomas=False, tipo=None):
    """Ultimas n acciones. Filtra por autonomas o por tipo."""
    items = _cargar()
    if solo_autonomas:
        items = [x for x in items if x.get("autonomo")]
    if tipo:
        items = [x for x in items if x.get("tipo") == tipo]
    return items[-n:]


def resumen():
    items = _cargar()
    por_tipo = {}
    for x in items:
        t = x.get("tipo", "accion")
        por_tipo[t] = por_tipo.get(t, 0) + 1
    autonomas = sum(1 for x in items if x.get("autonomo"))
    ultima = items[-1]["fecha"] if items else None
    return {"total": len(items), "autonomas": autonomas,
            "pedidas": len(items) - autonomas, "por_tipo": por_tipo,
            "ultima": ultima, "archivo": _LOG}
