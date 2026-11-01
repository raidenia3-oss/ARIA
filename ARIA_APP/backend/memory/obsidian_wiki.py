# -*- coding: utf-8 -*-
"""ARIA OS - Obsidian/LLM Wiki Layer.

Base de conocimiento persistente en archivos Markdown (formato Obsidian).
Sirve como memoria de "mundo": conocimiento permanente que trasciende sesiones.
Inspirado en Obsidian/LLM Wiki del video de Wanderloots.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ARIA.Memory.ObsidianWiki")


@dataclass
class WikiNote:
    """Nota individual en el wiki."""
    note_id: str
    title: str
    content: str
    tags: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)  # IDs de notas vinculadas
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ObsidianWiki:
    """Wiki de archivos Markdown para conocimiento persistente.

    Cada nota es un archivo .md en un directorio. Soporta enlaces tipo
    [[Nota]] y búsqueda por contenido/tags.
    """

    def __init__(self, data_dir: str = "data/memory/obsidian_wiki") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._notes: Dict[str, WikiNote] = {}
        self._load_all()

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #
    def add_note(
        self,
        title: str,
        content: str,
        tags: Optional[List[str]] = None,
        links: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Crea o actualiza una nota. Retorna note_id."""
        note_id = self._slugify(title)
        now = time.time()
        existing = self._notes.get(note_id)
        if existing:
            existing.content = content
            existing.tags = tags or existing.tags
            existing.links = links or existing.links
            existing.updated_at = now
            existing.metadata = metadata or existing.metadata
        else:
            note = WikiNote(
                note_id=note_id,
                title=title,
                content=content,
                tags=tags or [],
                links=links or [],
                metadata=metadata or {},
            )
            self._notes[note_id] = note
        self._write_note(note_id)
        logger.debug(f"ObsidianWiki: Nota '{title}' guardada")
        return note_id

    def get_note(self, note_id: str) -> Optional[WikiNote]:
        return self._notes.get(note_id)

    def get_note_by_title(self, title: str) -> Optional[WikiNote]:
        note_id = self._slugify(title)
        return self._notes.get(note_id)

    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Búsqueda por título, contenido y tags."""
        q = query.lower()
        hits: List[Dict[str, Any]] = []
        for note in self._notes.values():
            score = 0.0
            if q in note.title.lower():
                score += 2.0
            if q in note.content.lower():
                score += 1.0
            for tag in note.tags:
                if q in tag.lower():
                    score += 1.5
            if score > 0:
                hits.append({
                    "note_id": note.note_id,
                    "title": note.title,
                    "content": note.content[:500],
                    "tags": note.tags,
                    "score": round(score, 4),
                    "source": "obsidian_wiki",
                })
        hits.sort(key=lambda h: h["score"], reverse=True)
        return hits[: max(1, top_k)]

    def get_by_tag(self, tag: str, top_k: int = 20) -> List[WikiNote]:
        return [n for n in self._notes.values() if tag in n.tags][: max(1, top_k)]

    def list_notes(self) -> List[WikiNote]:
        return list(self._notes.values())

    def stats(self) -> Dict[str, Any]:
        tag_counts: Dict[str, int] = {}
        for n in self._notes.values():
            for t in n.tags:
                tag_counts[t] = tag_counts.get(t, 0) + 1
        return {
            "total_notes": len(self._notes),
            "tags": tag_counts,
            "data_dir": str(self.data_dir),
        }

    # ------------------------------------------------------------------ #
    # Archivos Markdown
    # ------------------------------------------------------------------ #
    def _slugify(self, title: str) -> str:
        safe = re.sub(r"[^a-zA-Z0-9_.-]", "_", title.strip())
        return safe[:100] or "untitled"

    def _note_path(self, note_id: str) -> Path:
        return self.data_dir / f"{note_id}.md"

    def _write_note(self, note_id: str) -> None:
        note = self._notes[note_id]
        lines = [f"# {note.title}"]
        if note.tags:
            lines.append("tags: " + ", ".join(note.tags))
        if note.links:
            lines.append("links: " + ", ".join(note.links))
        lines.append("")
        lines.append(note.content)
        path = self._note_path(note_id)
        path.write_text("\n".join(lines), encoding="utf-8")

    def _load_all(self) -> None:
        for md_file in self.data_dir.glob("*.md"):
            try:
                text = md_file.read_text(encoding="utf-8")
                note = self._parse_md(md_file.stem, text)
                self._notes[note.note_id] = note
            except Exception as exc:
                logger.warning(f"ObsidianWiki: error cargando {md_file}: {exc}")
        logger.info(f"ObsidianWiki: {len(self._notes)} notas cargadas")

    @staticmethod
    def _parse_md(note_id: str, text: str) -> WikiNote:
        lines = text.splitlines()
        title = note_id
        tags: List[str] = []
        links: List[str] = []
        body: List[str] = []
        in_header = True
        for line in lines:
            stripped = line.strip()
            if in_header:
                if not stripped:
                    # La linea en blanco cierra la cabecera.
                    in_header = False
                    continue
                if stripped.startswith("# "):
                    title = stripped[2:].strip()
                    continue
                if stripped.startswith("tags:"):
                    tags = [t.strip() for t in stripped[5:].split(",") if t.strip()]
                    continue
                if stripped.startswith("links:"):
                    links = [l.strip() for l in stripped[6:].split(",") if l.strip()]
                    continue
                in_header = False
            body.append(line)
        return WikiNote(
            note_id=note_id,
            title=title,
            content="\n".join(body).strip(),
            tags=tags,
            links=links,
        )

    # ------------------------------------------------------------------ #
    # Enlaces wiki [[Nota]]
    # ------------------------------------------------------------------ #
    def resolve_links(self, content: str) -> List[str]:
        """Extrae IDs de notas referenciadas como [[Título]] en el contenido."""
        found = re.findall(r"\[\[([^\]]+)\]\]", content)
        return [self._slugify(t) for t in found]
