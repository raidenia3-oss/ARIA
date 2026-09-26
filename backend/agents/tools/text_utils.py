from __future__ import annotations
import re


def _slugify(text: str = "") -> str:
    s = (text or "").strip().lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    return s.strip("-")


def _split_lines(text: str = "", limit: int = 100) -> list:
    lines = [l.rstrip() for l in (text or "").splitlines() if l.strip()]
    return lines[: max(1, int(limit))]


def _count_words(text: str = "") -> dict:
    words = [w for w in (text or "").split() if w.strip()]
    return {"word_count": len(words), "char_count": len(text or "")}


TOOLS = {
    "text.utils.slugify": {
        "description": "Convierte un texto libre en un slug URL-safe (minusculas, guiones).",
        "parameters": {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "Texto a convertir"}},
            "required": ["text"],
        },
        "category": "text",
        "risk": "safe",
        "func": _slugify,
    },
    "text.utils.split_lines": {
        "description": "Divide texto en lineas limpias no vacias con un limite opcional.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Texto multilinea"},
                "limit": {"type": "integer", "description": "Maximo de lineas", "default": 100},
            },
            "required": ["text"],
        },
        "category": "text",
        "risk": "safe",
        "func": _split_lines,
    },
    "text.utils.count_words": {
        "description": "Cuenta palabras en un texto y devuelve estadisticas basicas.",
        "parameters": {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "Texto a analizar"}},
            "required": ["text"],
        },
        "category": "text",
        "risk": "safe",
        "func": _count_words,
    },
}
