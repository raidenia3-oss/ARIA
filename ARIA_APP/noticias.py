# -*- coding: utf-8 -*-
"""ARIA - Recolector de noticias (explora internet + redes y arma el dia).

ARIA junta los titulares del dia desde fuentes publicas via RSS (urllib, SALIENTE,
Regla v2: sin servidores, sin scraping fragil). Mezcla NOTICIAS (Google News) y
REDES/comunidad (Reddit RSS). Dedup, ordena y cachea en data/noticias.json. Lo que
recolecta se muestra en la bandeja emergente (bandeja.py).

Neutral: solo recolecta y lista titulares con su FUENTE y link; no opina ni toma
partido. Tu decides que leer. Para comentarios/hilos puntuales, se abre la pagina
en el navegador bajo demanda (no se scrapea masivo).

El parseo (_parse_feed) es PURO: testeable con XML de ejemplo.
"""
import os
import json
import time
import html
import re
try:
    import xml.etree.ElementTree as ET
except Exception:
    ET = None

_DIR = os.path.dirname(os.path.abspath(__file__))
_CACHE = os.path.join(_DIR, "data", "noticias.json")

# fuentes por defecto (editables). Google News (noticias) + Reddit (redes/comunidad).
FUENTES_DEF = [
    ("Google News", "https://news.google.com/rss?hl=es-419&gl=PE&ceid=PE:es"),
    ("Reddit r/worldnews", "https://www.reddit.com/r/worldnews/.rss"),
]


def _limpiar(t):
    t = re.sub(r"<[^>]+>", "", t or "")
    return html.unescape(t).strip()


def _parse_feed(xml_text, fuente=""):
    """Parsea RSS 2.0 (item) o Atom (entry). Devuelve lista de dicts. Puro."""
    if ET is None:
        return []
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return []
    items = []
    # RSS 2.0: .//item ; Atom: .//{ns}entry
    nodos = root.findall(".//item")
    atom = False
    if not nodos:
        nodos = [e for e in root.iter() if e.tag.endswith("}entry") or e.tag == "entry"]
        atom = True
    for n in nodos:
        def hijo(tag):
            for c in n:
                if c.tag == tag or c.tag.endswith("}" + tag):
                    return c
            return None
        tit = hijo("title")
        titulo = _limpiar(tit.text if tit is not None else "")
        if atom:
            lk = hijo("link")
            link = lk.get("href") if lk is not None else ""
            fe = hijo("updated") or hijo("published")
        else:
            lk = hijo("link")
            link = _limpiar(lk.text if lk is not None else "")
            fe = hijo("pubDate")
        fecha = _limpiar(fe.text if fe is not None else "")
        if titulo:
            items.append({"titulo": titulo[:200], "url": link, "fuente": fuente, "fecha": fecha})
    return items


def _descargar(url, timeout=12):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ARIA news)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def obtener(fuentes=None, maximo=20, guardar=True):
    """Recolecta titulares de todas las fuentes. Devuelve lista dedup + cachea."""
    fuentes = fuentes or FUENTES_DEF
    todas, vistos = [], set()
    errores = []
    for nombre, url in fuentes:
        try:
            xml = _descargar(url)
            for it in _parse_feed(xml, nombre):
                clave = it["titulo"].lower()[:80]
                if clave not in vistos:
                    vistos.add(clave)
                    todas.append(it)
        except Exception as exc:
            errores.append("%s: %s" % (nombre, exc))
    todas = todas[:maximo]
    paquete = {"ts": time.time(), "fecha": time.strftime("%Y-%m-%d %H:%M"),
               "noticias": todas, "errores": errores}
    if guardar and todas:
        try:
            os.makedirs(os.path.dirname(_CACHE), exist_ok=True)
            with open(_CACHE, "w", encoding="utf-8") as f:
                json.dump(paquete, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    return paquete


def cache():
    """Lee lo ultimo recolectado (para mostrar sin volver a bajar)."""
    try:
        return json.load(open(_CACHE, encoding="utf-8"))
    except Exception:
        return {"noticias": [], "fecha": None}


def resumen(paquete=None):
    p = paquete or cache()
    n = p.get("noticias", [])
    return "%d titulares (%s)" % (len(n), p.get("fecha") or "sin fecha")
