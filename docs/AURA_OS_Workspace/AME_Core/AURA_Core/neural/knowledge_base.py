"""Knowledge Base «Gems» para inyección de contexto local en AURA Neural Bridge."""

from __future__ import annotations

import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

BASE = Path(__file__).resolve().parent
KB_DIR = BASE / "knowledge_base"
KB_DIR.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class KnowledgeGem:
    name: str
    source: str
    loaded_at: float = field(default_factory=lambda: time.time())
    characters: int = 0
    preview: str = ""


def _read_text_file(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
        return text
    except Exception:
        return ""


def _build_preview(text: str, limit: int = 180) -> str:
    text = text.replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def load_gem(name: str) -> Optional[KnowledgeGem]:
    candidates = [
        KB_DIR / f"{name}.txt",
        KB_DIR / f"{name}.md",
    ]
    for path in candidates:
        if path.exists():
            text = _read_text_file(path)
            return KnowledgeGem(
                name=name,
                source=path.name,
                characters=len(text),
                preview=_build_preview(text),
            )
    return None


def list_gems() -> list[KnowledgeGem]:
    items: list[KnowledgeGem] = []
    for path in KB_DIR.glob("*"):
        if path.is_file() and path.suffix.lower() in {".txt", ".md"}:
            text = _read_text_file(path)
            items.append(
                KnowledgeGem(
                    name=path.stem,
                    source=path.name,
                    characters=len(text),
                    preview=_build_preview(text),
                )
            )
    return items


def build_context_prompt(base_prompt: str, gem_names: list[str]) -> str:
    context_parts: list[str] = []
    for name in gem_names:
        gem = load_gem(name)
        if gem:
            text = _read_text_file(KB_DIR / gem.source)
            context_parts.append(f"[CONOCIMIENTO:{gem.source}]\n{text}")
    if not context_parts:
        return base_prompt
    header = "Usa el siguiente contexto para responder de forma precisa:\n"
    return header + "\n\n".join(context_parts) + "\n\n[FIN CONTEXTO]\n\n" + base_prompt
