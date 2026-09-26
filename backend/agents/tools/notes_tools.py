from __future__ import annotations
import os
from datetime import datetime
from pathlib import Path


def _render_heading(title: str = "", level: int = 1) -> dict:
    level = max(1, min(6, int(level)))
    return {"markdown": f"{'#' * level} {title}"}


def _write_note(title: str = "", body: str = "", filename: str = "") -> dict:
    safe = (filename or "").strip() or datetime.now().strftime("note_%Y%m%d_%H%M%S.md")
    safe = Path(safe).name
    base = os.getenv("AURA_AGENT_NOTES_DIR", os.path.join("data", "agent_notes"))
    dirp = Path(base)
    dirp.mkdir(parents=True, exist_ok=True)
    path = dirp / safe
    content = f"# {title}\n\n{body}\n" if title else f"{body}\n"
    path.write_text(content, encoding="utf-8")
    return {"path": str(path), "chars": len(content), "filename": safe}


def _timestamp(zone: str = "local") -> dict:
    return {"iso": datetime.now().isoformat(), "zone": zone}


TOOLS = {
    "notes.markdown.render_heading": {
        "description": "Genera un encabezado Markdown de un nivel dado.",
        "parameters": {
            "type": "object",
            "properties": {"title": {"type": "string"}, "level": {"type": "integer", "default": 1}},
            "required": ["title"],
        },
        "category": "notes",
        "risk": "safe",
        "func": _render_heading,
    },
    "notes.local.write": {
        "description": "Escribe una nota Markdown en el directorio local de notas del agente.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "default": ""},
                "body": {"type": "string", "default": ""},
                "filename": {"type": "string", "default": ""},
            },
            "required": [],
        },
        "category": "notes",
        "risk": "safe",
        "func": _write_note,
    },
    "notes.sys.timestamp": {
        "description": "Devuelve la marca de tiempo local actual.",
        "parameters": {
            "type": "object",
            "properties": {"zone": {"type": "string", "default": "local"}},
            "required": [],
        },
        "category": "notes",
        "risk": "safe",
        "func": _timestamp,
    },
}
