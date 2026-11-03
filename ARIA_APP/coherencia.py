# -*- coding: utf-8 -*-
"""ARIA - Coherencia: detecta CONTRADICCIONES en lo que sabe (idea de Neomas).

Cuando ARIA aprende algo que choca con lo que ya tenia, en vez de guardar las dos
cosas calladas, lo DETECTA y lo muestra para resolver. Mantiene su memoria honesta
y coherente (va de la mano con certeza.py y el grafo).

Enfoque (de 'Finding Contradictions in Text', de Marneffe et al.): dos afirmaciones
RELACIONADAS (mismo sujeto) se contradicen si difieren por:
  - NEGACION  ('me gusta X' vs 'no me gusta X')
  - ANTONIMO  ('X es rapido' vs 'X es lento')
  - VALOR/NUMERO distinto para la misma relacion ('vivo en Lima' vs 'vivo en Cusco')

Puro y testeable (sin modelo pesado). Usa el grafo para traer las notas parecidas.
100% local, Regla v2.
"""
import re

_NEG = {"no", "nunca", "jamas", "tampoco", "ni", "sin"}

# pares de antonimos (si uno aparece en A y el otro en B, con mismo sujeto -> choque)
_ANTONIMOS = [
    ("sube", "baja"), ("subir", "bajar"), ("caliente", "frio"), ("rapido", "lento"),
    ("grande", "pequeno"), ("bueno", "malo"), ("abierto", "cerrado"),
    ("verdadero", "falso"), ("vivo", "muerto"), ("dia", "noche"), ("mas", "menos"),
    ("siempre", "nunca"), ("todo", "nada"), ("ama", "odia"), ("gusta", "odia"),
    ("alto", "bajo"), ("lleno", "vacio"), ("activa", "desactivada"),
    ("encendido", "apagado"), ("si", "no"), ("cerca", "lejos"), ("facil", "dificil"),
]
# relaciones cuyo VALOR deberia ser unico (si cambia -> posible contradiccion)
_RELACIONES = ["vive en", "vivo en", "trabaja en", "trabajo en", "prefiere", "prefiero",
               "se llama", "nacio en", "es de", "usa", "estudia"]


def _norm(t):
    return re.sub(r"\s+", " ", (t or "").lower()).strip()


def _palabras(t):
    return re.findall(r"[a-záéíóúñ]+", _norm(t))


def _contenido(t):
    return set(w for w in _palabras(t) if len(w) > 3 and w not in _NEG)


def relacionadas(a, b, minimo=1):
    """Mismo sujeto/tema: comparten palabras de contenido."""
    return len(_contenido(a) & _contenido(b)) >= minimo


def _negacion(t):
    return any(w in _NEG for w in _palabras(t))


def _antonimo(a, b):
    pa, pb = set(_palabras(a)), set(_palabras(b))
    for x, y in _ANTONIMOS:
        if (x in pa and y in pb) or (y in pa and x in pb):
            return "antonimo %s/%s" % (x, y)
    return None


def _valor_rel(t):
    """Si la frase es 'X <relacion> VALOR', devuelve (relacion, valor)."""
    low = _norm(t)
    for rel in _RELACIONES:
        i = low.find(rel)
        if i >= 0:
            valor = low[i + len(rel):].strip(" .:,")
            if valor:
                return rel, valor
    return None, None


def _num(t):
    return re.findall(r"\d+(?:[.,]\d+)?", t or "")


def contradice(a, b):
    """Devuelve (True/False, razon). Puro."""
    if not a or not b or _norm(a) == _norm(b):
        return False, ""
    if not relacionadas(a, b):
        return False, ""
    # 1) negacion: uno niega y el otro no, con alto solape
    if _negacion(a) != _negacion(b) and len(_contenido(a) & _contenido(b)) >= 2:
        return True, "uno niega lo que el otro afirma"
    # 2) antonimo
    ant = _antonimo(a, b)
    if ant:
        return True, ant
    # 3) valor distinto para la misma relacion
    ra, va = _valor_rel(a)
    rb, vb = _valor_rel(b)
    if ra and ra == rb and va and vb and _contenido(va).isdisjoint(_contenido(vb)) and va != vb:
        return True, "valor distinto en '%s': '%s' vs '%s'" % (ra, va, vb)
    # 4) numero distinto en contexto parecido
    na, nb = _num(a), _num(b)
    if na and nb and set(na) != set(nb) and len(_contenido(a) & _contenido(b)) >= 2:
        return True, "numero distinto: %s vs %s" % (na, nb)
    return False, ""


def revisar(grafo, proposicion, k=6):
    """Antes/al guardar 'proposicion', busca en el grafo las parecidas y reporta
    las que la contradicen. Devuelve lista de {texto, razon}."""
    conflictos = []
    try:
        similares = grafo.buscar(proposicion, k=k)
    except Exception:
        similares = []
    for s in similares:
        txt = s.get("texto", "")
        choca, razon = contradice(proposicion, txt)
        if choca:
            conflictos.append({"texto": txt, "razon": razon})
    return conflictos


def conflictos(grafo, limite=150):
    """Escanea el grafo y lista pares que se contradicen (acotado)."""
    try:
        db = grafo._conn()
        filas = db.execute("SELECT texto FROM nodos LIMIT ?", (limite,)).fetchall()
    except Exception:
        return []
    props = [f[0] for f in filas]
    out = []
    for i in range(len(props)):
        for j in range(i + 1, len(props)):
            choca, razon = contradice(props[i], props[j])
            if choca:
                out.append({"a": props[i], "b": props[j], "razon": razon})
    return out
