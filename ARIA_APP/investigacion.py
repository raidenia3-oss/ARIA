# -*- coding: utf-8 -*-
"""ARIA - Investigacion -> playbook (idea de REA: 'reverse-engineer' un tema).

Le das un tema (o competidor/canal) y las FUENTES que ARIA junta de la web, y ella
las convierte en un PLAYBOOK estructurado: resumen, hallazgos clave, patrones que se
repiten, que replicar, riesgos, y las fuentes. Asi ARIA no te tira un muro de texto,
sino un analisis accionable.

ARIA consigue las fuentes con su skill web (urllib, saliente, Regla v2). Este modulo
ESTRUCTURA lo que ya esta adentro (usa atomizacion para sacar los puntos). La
estructuracion (analizar/playbook_md) es PURA: testeable con fuentes inyectadas.

fuentes = [{"titulo":..., "url":..., "texto":...}, ...]
"""
import re
from collections import Counter

# verbos/senales de TACTICA accionable (que replicar)
_ACCION = ("usa", "crea", "publica", "ofrece", "lanza", "automatiza", "optimiza",
           "construye", "aplica", "implementa", "prueba", "mide", "segmenta",
           "reutiliza", "integra", "replica", "enfoca", "prioriza")
# senales de RIESGO / advertencia
_RIESGO = ("riesgo", "cuidado", "problema", "falla", "error", "evita", "no ",
           "peligro", "ban", "penaliz", "limit", "costoso", "dificil", "advertencia")


def _atomos_de(fuentes):
    """Junta atomos de todas las fuentes (reusa atomizacion)."""
    try:
        import atomizacion as at
    except Exception:
        at = None
    out = []
    for f in fuentes:
        texto = f.get("texto", "")
        if at is not None:
            for a in at._atomos(texto):
                out.append({"texto": a, "fuente": f.get("titulo") or f.get("url") or "?"})
        else:
            for frase in re.split(r"(?<=[.!?])\s+", texto):
                if len(frase.split()) >= 4:
                    out.append({"texto": frase.strip(), "fuente": f.get("titulo", "?")})
    return out


def _conceptos(fuentes, n=8):
    texto = " ".join(f.get("texto", "") for f in fuentes)
    try:
        import atomizacion as at
        return at._conceptos(texto, n)
    except Exception:
        pal = [w for w in re.findall(r"[a-záéíóúñ]{5,}", texto.lower())]
        return [w for w, _ in Counter(pal).most_common(n)]


def _clasifica(atomos, palabras):
    return [a for a in atomos if any(p in a["texto"].lower() for p in palabras)]


def analizar(tema, fuentes):
    """Convierte fuentes en un playbook estructurado. Devuelve un dict."""
    atomos = _atomos_de(fuentes)
    conceptos = _conceptos(fuentes)
    replicar = _clasifica(atomos, _ACCION)[:8]
    riesgos = _clasifica(atomos, _RIESGO)[:6]
    # hallazgos: los primeros atomos que NO son ni tactica ni riesgo (contexto)
    usados = {id(a) for a in replicar} | {id(a) for a in riesgos}
    hallazgos = [a for a in atomos if id(a) not in usados][:8]
    return {
        "tema": tema,
        "resumen": (atomos[0]["texto"] if atomos else ""),
        "conceptos": conceptos,
        "hallazgos": hallazgos,
        "que_replicar": replicar,
        "riesgos": riesgos,
        "fuentes": [{"titulo": f.get("titulo", "?"), "url": f.get("url", "")} for f in fuentes],
        "n_fuentes": len(fuentes),
        "n_atomos": len(atomos),
    }


def playbook_md(analisis):
    """Renderiza el analisis como un playbook en Markdown."""
    L = ["# Playbook: %s" % analisis.get("tema", ""), ""]
    if analisis.get("resumen"):
        L += ["> %s" % analisis["resumen"], ""]
    if analisis.get("conceptos"):
        L += ["**Temas clave:** " + ", ".join(analisis["conceptos"]), ""]

    def bloque(titulo, items, campo="texto"):
        if not items:
            return []
        out = ["## %s" % titulo]
        for it in items:
            src = it.get("fuente")
            out.append("- %s%s" % (it[campo], (" _(%s)_" % src) if src else ""))
        out.append("")
        return out

    L += bloque("Hallazgos", analisis.get("hallazgos"))
    L += bloque("Que replicar (tacticas)", analisis.get("que_replicar"))
    L += bloque("Riesgos / cuidado", analisis.get("riesgos"))
    if analisis.get("fuentes"):
        L += ["## Fuentes"]
        for f in analisis["fuentes"]:
            L.append("- %s %s" % (f.get("titulo", ""), f.get("url", "")))
    return "\n".join(L)


def investigar(tema, fuentes, al_grafo=False):
    """Analiza + (opcional) mete los hallazgos al grafo de conocimiento."""
    an = analizar(tema, fuentes)
    if al_grafo:
        try:
            import conocimiento
            g = conocimiento.grafo()
            for a in an["hallazgos"] + an["que_replicar"]:
                g.aprender(a["texto"], tema=tema, fuente=a.get("fuente", ""))
        except Exception:
            pass
    an["playbook"] = playbook_md(an)
    return an
