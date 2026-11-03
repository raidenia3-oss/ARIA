# -*- coding: utf-8 -*-
"""ARIA - Atomizacion de fuentes (idea de Neomas 'source atomization').

Le das un documento/nota y ARIA no lo guarda entero: lo PARTE en conocimiento util:
  - resumen   : indice breve de la fuente
  - conceptos : los terminos clave que aparecen
  - atomos    : afirmaciones atomicas (una idea por linea), cada una ligada a su FUENTE

Luego cada atomo entra al grafo de conocimiento (conocimiento.aprender), revisando
CONTRADICCIONES con coherencia antes de guardar. Asi una fuente se vuelve conocimiento
conectado, honesto y rastreable a su origen.

Base heuristica (sin LLM): parte por frases, filtra las que son afirmaciones, saca
conceptos por frecuencia. Opcionalmente el cerebro puede refinar. 100% local, Regla v2.
La extraccion (_frases/_atomos/_conceptos) es PURA: testeable.
"""
import os
import re
from collections import Counter

# palabras vacias (no son conceptos)
_STOP = {"que", "con", "los", "las", "una", "uno", "del", "por", "para", "como", "mas",
         "pero", "sus", "este", "esta", "esto", "son", "fue", "han", "hay", "muy", "ser",
         "the", "and", "for", "con", "entre", "cuando", "donde", "porque", "tambien",
         "sobre", "desde", "hasta", "cada", "todo", "toda", "sin", "ya", "lo", "le", "se"}


def _frases(texto):
    """Parte el texto en frases."""
    t = re.sub(r"\s+", " ", (texto or "").strip())
    partes = re.split(r"(?<=[.!?])\s+|\n+", t)
    return [p.strip() for p in partes if p.strip()]


def _es_atomo(frase):
    """Una afirmacion atomica: ni muy corta ni pregunta ni titulo suelto."""
    f = frase.strip()
    if len(f.split()) < 4 or len(f) > 240:
        return False
    if f.endswith("?") or f.endswith(":"):
        return False
    # debe tener algo de verbo/estructura (heuristica: tiene espacio y minusculas)
    return bool(re.search(r"[a-záéíóúñ]{3,}\s+[a-záéíóúñ]{2,}", f.lower()))


def _atomos(texto, maximo=40):
    return [f for f in _frases(texto) if _es_atomo(f)][:maximo]


def _conceptos(texto, n=8):
    palabras = re.findall(r"[a-záéíóúñ]{4,}", (texto or "").lower())
    palabras = [w for w in palabras if w not in _STOP]
    comunes = Counter(palabras).most_common(n * 2)
    # prioriza los que aparecen >=2 veces
    conceptos = [w for w, c in comunes if c >= 2][:n]
    if not conceptos:
        conceptos = [w for w, _ in comunes[:n]]
    return conceptos


def atomizar(texto, fuente=""):
    """Devuelve {fuente, resumen, conceptos, atomos}."""
    frases = _frases(texto)
    atomos = _atomos(texto)
    conceptos = _conceptos(texto)
    resumen = (frases[0][:160] if frases else "")
    return {
        "fuente": fuente or "(sin fuente)",
        "resumen": resumen,
        "conceptos": conceptos,
        "atomos": [{"texto": a, "fuente": fuente or "(sin fuente)"} for a in atomos],
        "n_atomos": len(atomos),
    }


def atomizar_archivo(ruta):
    """Lee un .md/.txt y lo atomiza (la fuente es el nombre del archivo)."""
    try:
        with open(ruta, "r", encoding="utf-8", errors="replace") as f:
            texto = f.read()
    except Exception as exc:
        return {"error": "no pude leer %s: %s" % (ruta, exc)}
    return atomizar(texto, fuente=os.path.basename(ruta))


def ingerir(grafo, texto, fuente="", revisar_coherencia=True, tema=""):
    """Atomiza y mete cada atomo al grafo, revisando contradicciones antes.
    Devuelve {agregados, conflictos, conceptos}."""
    datos = atomizar(texto, fuente)
    agregados, conflictos = 0, []
    coh = None
    if revisar_coherencia:
        try:
            import coherencia as coh  # noqa
        except Exception:
            coh = None
    for at in datos["atomos"]:
        txt = at["texto"]
        if coh is not None:
            try:
                ch = coh.revisar(grafo, txt)
                if ch:
                    conflictos.append({"atomo": txt, "choca_con": ch})
                    continue   # no guardes algo que contradice; se reporta para resolver
            except Exception:
                pass
        try:
            if grafo.aprender(txt, tema=tema or (datos["conceptos"][0] if datos["conceptos"] else ""),
                              fuente=fuente):
                agregados += 1
        except Exception:
            pass
    return {"agregados": agregados, "conflictos": conflictos,
            "conceptos": datos["conceptos"], "resumen": datos["resumen"]}
