# -*- coding: utf-8 -*-
"""ARIA - Resurgir (idea robada de Neomas: 'Daily Resurface'). Cierra el loop de memoria.

Neomas lo resume: "tu mejor idea ya la escribiste; se esta muriendo en una nota que no
vas a reabrir". ARIA ya CAPTURA, CONECTA y RECUERDA (grafo, atomizacion, coherencia);
lo que faltaba era RESURGIR: cada dia saca UN nodo viejo del grafo de conocimiento, con
su FUENTE y FECHA, y te lo devuelve ("recuerdas esto que aprendiste?"). Lo suelta en la
bandeja o en el brief.

Elige el nodo mas 'olvidado' (el mas viejo que no se haya resurgido hace poco), con un
ESPACIADO para no repetir en dias. El 'por que ahora' sale de sus nodos relacionados en
el grafo (lo que se conecta con esa idea).

La LOGICA (elegir, espaciado, fechas, armar tarjeta) es PURA y testeable con nodos
inyectados. La parte impura (leer el grafo, el log diario) esta aislada y guardada.
100% local, Regla v2: sin red, sin servidores.
"""
import os
import json
import time
from datetime import datetime

_DIR = os.path.dirname(os.path.abspath(__file__))
_LOG = os.path.join(_DIR, "data", "resurgir.json")


# ======================================================================= LOGICA PURA

def _fecha(ts):
    """Timestamp epoch -> 'YYYY-MM-DD'. Puro."""
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d")
    except Exception:
        return ""


def dias_entre(a, b):
    """Dias entre dos fechas 'YYYY-MM-DD' (b - a). Puro. 0 si algo falla."""
    try:
        da = datetime.strptime(a, "%Y-%m-%d")
        db = datetime.strptime(b, "%Y-%m-%d")
        return (db - da).days
    except Exception:
        return 0


def elegir(nodos, historial, hoy, espaciado_dias=7):
    """Elige el nodo a resurgir hoy. PURO.

    nodos      = [{id, texto, tema, fuente, ts}, ...]
    historial  = {str(id): 'YYYY-MM-DD'}  ultima vez que se resurgio cada nodo
    hoy        = 'YYYY-MM-DD'
    Regla: descarta los resurgidos hace < espaciado_dias; entre los que quedan,
    prioriza los NUNCA resurgidos y, dentro de eso, el mas VIEJO (ts menor = mas
    'muriendo'). Determinista. Devuelve el nodo o None si no hay elegible.
    """
    elegibles = []
    for n in nodos or []:
        if not (n.get("texto") or "").strip():
            continue
        visto = historial.get(str(n.get("id")))
        if visto and dias_entre(visto, hoy) < espaciado_dias:
            continue                      # demasiado reciente, dejalo descansar
        nunca = 0 if visto else 1         # nunca resurgido pesa mas (va primero)
        elegibles.append((nunca, n))
    if not elegibles:
        return None
    # orden: primero los nunca vistos; luego el ts mas antiguo (idea mas olvidada)
    elegibles.sort(key=lambda x: (-x[0], float(x[1].get("ts") or 0)))
    return elegibles[0][1]


def por_que(nodo, relacionados):
    """Arma el 'por que ahora' a partir de los nodos conectados / el tema. Puro."""
    rel = [r.get("texto", "") for r in (relacionados or []) if r.get("texto")]
    if rel:
        return "Se conecta con: " + "; ".join(rel[:2])
    if nodo.get("tema"):
        return "Del tema: %s" % nodo["tema"]
    return "Una idea que guardaste y no has revisitado."


def tarjeta(nodo, relacionados=None, hoy=None):
    """Convierte el nodo elegido en una tarjeta mostrable. Puro."""
    if not nodo:
        return None
    f = _fecha(nodo.get("ts"))
    edad = dias_entre(f, hoy) if (f and hoy) else None
    return {
        "id": nodo.get("id"),
        "texto": nodo.get("texto", ""),
        "fuente": nodo.get("fuente") or "memoria de ARIA",
        "fecha": f,
        "edad_dias": edad,
        "por_que": por_que(nodo, relacionados),
    }


def como_noticia(tar):
    """Adapta la tarjeta al formato que ya consume la bandeja (titulo/fuente/url).
    url vacia: es memoria interna, no abre navegador. Puro."""
    if not tar:
        return None
    edad = ""
    if tar.get("edad_dias"):
        edad = " · hace %d dias" % tar["edad_dias"]
    return {"titulo": "Recuerda: " + tar["texto"],
            "fuente": "%s%s" % (tar["fuente"], edad),
            "url": ""}


def como_linea(tar):
    """Una linea para el brief diario. Puro."""
    if not tar:
        return "Resurgir: (sin nada que recordar todavia)"
    return "Resurgir: \"%s\" — %s (%s)" % (
        tar["texto"][:120], tar["por_que"], tar.get("fecha") or "sin fecha")


# ====================================================================== PARTE IMPURA

def _hoy():
    return time.strftime("%Y-%m-%d")


def cargar_historial(ruta=None):
    try:
        return json.load(open(ruta or _LOG, encoding="utf-8"))
    except Exception:
        return {}


def guardar_historial(hist, ruta=None):
    ruta = ruta or _LOG
    try:
        os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(hist, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def _leer_nodos(grafo):
    """Saca todos los nodos del grafo (impuro). Nunca lanza."""
    try:
        db = grafo._conn()
        filas = db.execute("SELECT id,texto,tema,fuente,ts FROM nodos").fetchall()
        return [{"id": i, "texto": t, "tema": tm, "fuente": fu, "ts": ts}
                for (i, t, tm, fu, ts) in filas]
    except Exception:
        return []


def resurgir(grafo=None, marcar=True, espaciado_dias=7):
    """Flujo completo: lee el grafo, elige un nodo olvidado, arma la tarjeta y lo
    marca en el historial para no repetirlo pronto. Devuelve la tarjeta o
    {'vacio': True} si no hay nada elegible. Nunca lanza."""
    if grafo is None:
        try:
            import conocimiento
            grafo = conocimiento.grafo()
        except Exception:
            return {"vacio": True, "motivo": "sin grafo"}
    hoy = _hoy()
    nodos = _leer_nodos(grafo)
    hist = cargar_historial()
    nodo = elegir(nodos, hist, hoy, espaciado_dias=espaciado_dias)
    if nodo is None:
        return {"vacio": True, "motivo": "nada elegible hoy"}
    rel = []
    try:
        rel = grafo.relacionados(nodo["id"], limite=3)
    except Exception:
        pass
    tar = tarjeta(nodo, rel, hoy)
    if marcar:
        hist[str(nodo["id"])] = hoy
        guardar_historial(hist)
    return tar


def para_bandeja(grafo=None):
    """Tarjeta lista para insertar en la bandeja (formato noticia)."""
    tar = resurgir(grafo=grafo)
    if tar.get("vacio"):
        return None
    return como_noticia(tar)
