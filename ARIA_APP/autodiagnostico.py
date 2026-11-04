# -*- coding: utf-8 -*-
"""ARIA - Autodiagnostico: ARIA se revisa a si misma y dice que esta bien y que roto.

Nace de los fallos reales (el cerebro que no cargaba por RAM, capas sin enganchar...).
Al arrancar (o con el comando 'diagnostico'), corre chequeos de cada subsistema y da
un parte claro: [OK]/[FALLA] + pista de que arreglar. Asi los problemas se ven ANTES
de explotar en el chat.

Chequea: modulos criticos importables, RAM/disco, cerebro, memoria semantica, grafo,
guardia de autonomia enganchada, avatar presente, vault. 100% local, Regla v2.
El runner (_evaluar) es puro y testeable.
"""
import os

_DIR = os.path.dirname(os.path.abspath(__file__))


def _evaluar(chequeos):
    """Corre una lista de (nombre, funcion->()->(ok, detalle)). Devuelve el reporte."""
    res = []
    for nombre, fn in chequeos:
        try:
            ok, detalle = fn()
        except Exception as exc:
            ok, detalle = False, "excepcion: %s" % exc
        res.append({"nombre": nombre, "ok": bool(ok), "detalle": str(detalle)[:160]})
    return res


# ---- chequeos individuales (cada uno devuelve (ok, detalle)) ----
def _chk_modulos():
    criticos = ["aria_va_core", "conocimiento", "experiencia", "mejora",
                "autonomia_guardia", "auditoria", "certeza", "nucleo", "forma",
                "presencia", "conversacion", "coherencia", "atomizacion", "vault_md"]
    faltan = []
    for m in criticos:
        try:
            __import__(m)
        except Exception:
            faltan.append(m)
    return (not faltan, "todos importan" if not faltan else "no importan: " + ", ".join(faltan))


def _chk_ram():
    try:
        import psutil
        libre = psutil.virtual_memory().available / (1024 ** 3)
        return (libre >= 1.5, "%.1f GB libres%s" % (libre, "" if libre >= 1.5 else " (poca RAM: cierra cosas)"))
    except Exception:
        return (True, "psutil no instalado (no critico)")


def _chk_disco():
    try:
        import shutil
        libre = shutil.disk_usage(_DIR).free / (1024 ** 3)
        return (libre >= 1.0, "%.1f GB libres" % libre)
    except Exception:
        return (True, "no medido")


def _chk_cerebro():
    try:
        from aria_va_core import LocalAIBrain  # noqa
        return (True, "LocalAIBrain importa (carga real al instanciar)")
    except Exception as exc:
        return (False, "no importa el cerebro: %s" % exc)


def _chk_semantica():
    try:
        import memory_semantic as ms
        return (ms.disponible(), "disponible" if ms.disponible() else "sin sqlite-vec/fastembed (degrada a palabra)")
    except Exception:
        return (True, "modulo no presente (opcional)")


def _chk_grafo():
    try:
        import conocimiento
        g = conocimiento.grafo()
        g._conn()
        return (True, "grafo operativo: %s nodos" % g.stats().get("nodos", "?"))
    except Exception as exc:
        return (False, "grafo fallo: %s" % exc)


def _chk_guardia_enganchada():
    """La guardia DEBE envolver la ejecucion autonoma (si no, autonomia insegura)."""
    ruta = os.path.join(_DIR, "autonomy", "runtime.py")
    try:
        txt = open(ruta, encoding="utf-8").read()
        ok = "autonomia_guardia" in txt and "guard(" in txt
        return (ok, "guardia enganchada en runtime" if ok else "¡AUTONOMIA SIN GUARDIA! no enciendas AUTO")
    except Exception:
        return (True, "runtime no encontrado (no critico si no usas autonomia)")


def _chk_avatar():
    ruta = os.path.join(_DIR, "assets", "chibi", "cyberpunk", "sheet.png")
    if os.path.isfile(ruta):
        return (True, "sheet.png presente (%d KB)" % (os.path.getsize(ruta) // 1024))
    return (False, "falta el sheet.png del avatar (regenerar con gen_local)")


def _chk_vault():
    try:
        import vault_md  # noqa
        return (True, "vault_md disponible")
    except Exception as exc:
        return (False, "vault_md no importa: %s" % exc)


_CHEQUEOS = [
    ("modulos", _chk_modulos), ("ram", _chk_ram), ("disco", _chk_disco),
    ("cerebro", _chk_cerebro), ("memoria_semantica", _chk_semantica),
    ("grafo", _chk_grafo), ("guardia_autonomia", _chk_guardia_enganchada),
    ("avatar", _chk_avatar), ("vault", _chk_vault),
]


def chequear():
    """Corre todos los chequeos. Devuelve {reporte, ok, fallas, texto}."""
    rep = _evaluar(_CHEQUEOS)
    fallas = [r for r in rep if not r["ok"]]
    lineas = ["DIAGNOSTICO ARIA:"]
    for r in rep:
        lineas.append("  [%s] %s: %s" % ("OK" if r["ok"] else "FALLA", r["nombre"], r["detalle"]))
    if fallas:
        lineas.append("-> revisar: " + ", ".join(f["nombre"] for f in fallas))
    else:
        lineas.append("-> todo en orden.")
    return {"reporte": rep, "ok": not fallas, "fallas": [f["nombre"] for f in fallas],
            "texto": "\n".join(lineas)}


if __name__ == "__main__":
    print(chequear()["texto"])
