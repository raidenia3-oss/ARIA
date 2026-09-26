#!/usr/bin/env python3
"""
AURA Memory Manager — Gestión de memoria persistente para asistente virtual tipo JARVIS.

Almacena y recupera:
  - Hechos sobre el usuario (preferencias, datos personales, proyectos)
  - Contexto de conversación reciente
  - Preferencias de comunicación (tono, formato, idioma)
  - Hábitos y rutinas
  - Relaciones entre entidades (personas, proyectos, dispositivos)

Características:
  - Memoria a corto plazo (sesión actual)
  - Memoria a largo plazo (persistente en JSONL)
  - Olvido inteligente por relevancia y antigüedad
  - Búsqueda semántica ligera (TF-IDF)
  - Export/import para sincronización entre instancias

Uso:
  python scripts/memory_manager.py --remember "User likes Python" --type fact
  python scripts/memory_manager.py --recall "What does user like?"
  python scripts/memory_manager.py --export --output memory_backup.jsonl
  python scripts/memory_manager.py --import memory_backup.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MemoryManager")

REPO_ROOT = Path(__file__).resolve().parent.parent
MEMORY_DIR = REPO_ROOT / "memory"
LONG_TERM_FILE = MEMORY_DIR / "long_term_memory.jsonl"
SHORT_TERM_FILE = MEMORY_DIR / "short_term_memory.jsonl"
PROFILE_FILE = MEMORY_DIR / "user_profile.json"

MEMORY_TYPES = ["fact", "preference", "habit", "relationship", "project", "event", "skill", "error"]


class MemoryEntry:
    """Entrada de memoria con metadatos."""

    def __init__(
        self,
        content: str,
        memory_type: str = "fact",
        confidence: float = 1.0,
        source: str = "user",
        tags: Optional[List[str]] = None,
        context: Optional[str] = None,
    ):
        self.content = content
        self.memory_type = memory_type
        self.confidence = confidence
        self.source = source
        self.tags = tags or []
        self.context = context
        self.created_at = datetime.now().isoformat()
        self.last_accessed = datetime.now().isoformat()
        self.access_count = 0
        self.relevance_score = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "memory_type": self.memory_type,
            "confidence": self.confidence,
            "source": self.source,
            "tags": self.tags,
            "context": self.context,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "relevance_score": self.relevance_score,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        entry = cls(
            content=data.get("content", ""),
            memory_type=data.get("memory_type", "fact"),
            confidence=data.get("confidence", 1.0),
            source=data.get("source", "user"),
            tags=data.get("tags", []),
            context=data.get("context"),
        )
        entry.created_at = data.get("created_at", entry.created_at)
        entry.last_accessed = data.get("last_accessed", entry.last_accessed)
        entry.access_count = data.get("access_count", 0)
        entry.relevance_score = data.get("relevance_score", 1.0)
        return entry

    def touch(self) -> None:
        self.last_accessed = datetime.now().isoformat()
        self.access_count += 1
        self.relevance_score = min(2.0, self.relevance_score + 0.1)


class ShortTermMemory:
    """Memoria a corto plazo (sesión actual)."""

    def __init__(self, max_items: int = 50):
        self.max_items = max_items
        self.items: List[MemoryEntry] = []

    def add(self, entry: MemoryEntry) -> None:
        self.items.append(entry)
        if len(self.items) > self.max_items:
            self.items.pop(0)

    def get_recent(self, n: int = 10) -> List[MemoryEntry]:
        return self.items[-n:]

    def clear(self) -> None:
        self.items = []


class LongTermMemory:
    """Memoria a largo plazo (persistente)."""

    def __init__(self, storage_path: Path = LONG_TERM_FILE):
        self.storage_path = storage_path
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.entries: List[MemoryEntry] = []
        self._load()

    def _load(self) -> None:
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                data = json.loads(line)
                                self.entries.append(MemoryEntry.from_dict(data))
                            except json.JSONDecodeError:
                                continue
            except Exception as exc:
                logger.warning(f"Failed to load memory: {exc}")

    def save(self) -> None:
        with open(self.storage_path, "w", encoding="utf-8") as f:
            for entry in self.entries:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

    def add(self, entry: MemoryEntry) -> None:
        self.entries.append(entry)
        self.save()

    def search(self, query: str, top_k: int = 5) -> List[MemoryEntry]:
        query_words = set(re.findall(r"\w+", query.lower()))
        scored = []
        for entry in self.entries:
            content_words = set(re.findall(r"\w+", entry.content.lower()))
            overlap = len(query_words & content_words)
            score = overlap * entry.relevance_score * (1 + 0.1 * entry.access_count)
            scored.append((score, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:top_k]]

    def decay(self, days_threshold: int = 30) -> None:
        cutoff = datetime.now() - timedelta(days=days_threshold)
        kept = []
        for entry in self.entries:
            last_accessed = datetime.fromisoformat(entry.last_accessed)
            if last_accessed > cutoff:
                entry.relevance_score = max(0.1, entry.relevance_score - 0.05)
                kept.append(entry)
        self.entries = kept
        self.save()

    def export(self, output_path: Path) -> None:
        with open(output_path, "w", encoding="utf-8") as f:
            for entry in self.entries:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

    def import_(self, input_path: Path) -> int:
        count = 0
        if not input_path.exists():
            return 0
        with open(input_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        entry = MemoryEntry.from_dict(data)
                        existing = [e for e in self.entries if e.content == entry.content]
                        if not existing:
                            self.entries.append(entry)
                            count += 1
                    except json.JSONDecodeError:
                        continue
        self.save()
        return count


class UserProfile:
    """Perfil del usuario con preferencias y personalización."""

    DEFAULTS = {
        "name": "Usuario",
        "preferred_name": "Usuario",
        "language": "es",
        "timezone": "America/Mexico_City",
        "tone": "neutral",
        "response_length": "medium",
        "topics_of_interest": [],
        "communication_style": "casual",
        "notification_preferences": {
            "voice": True,
            "text": True,
            "frequency": "normal",
        },
        "work_schedule": {
            "start": "09:00",
            "end": "18:00",
            "timezone": "America/Mexico_City",
        },
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }

    def __init__(self, storage_path: Path = PROFILE_FILE):
        self.storage_path = storage_path
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.storage_path.exists():
            try:
                return json.loads(self.storage_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return dict(self.DEFAULTS)

    def save(self) -> None:
        self.data["updated_at"] = datetime.now().isoformat()
        self.storage_path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")

    def update(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.data)


class MemoryManager:
    """Gestor principal de memoria de AURA."""

    def __init__(self):
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory()
        self.profile = UserProfile()

    def remember(self, content: str, memory_type: str = "fact", source: str = "user", tags: Optional[List[str]] = None) -> MemoryEntry:
        entry = MemoryEntry(
            content=content,
            memory_type=memory_type,
            source=source,
            tags=tags or [],
        )
        self.short_term.add(entry)
        self.long_term.add(entry)
        logger.info(f"Remembered: {content[:50]}...")
        return entry

    def recall(self, query: str, top_k: int = 5) -> List[MemoryEntry]:
        results = self.long_term.search(query, top_k=top_k)
        for entry in results:
            entry.touch()
        self.long_term.save()
        return results

    def forget(self, content: str) -> bool:
        before = len(self.long_term.entries)
        self.long_term.entries = [e for e in self.long_term.entries if e.content != content]
        after = len(self.long_term.entries)
        if before != after:
            self.long_term.save()
            logger.info(f"Forgot: {content[:50]}...")
            return True
        return False

    def get_context(self, n: int = 5) -> List[Dict]:
        recent = self.short_term.get_recent(n)
        return [entry.to_dict() for entry in recent]

    def update_profile(self, key: str, value: Any) -> None:
        self.profile.update(key, value)

    def get_profile(self) -> Dict[str, Any]:
        return self.profile.to_dict()

    def decay_old_memories(self, days: int = 30) -> int:
        before = len(self.long_term.entries)
        self.long_term.decay(days_threshold=days)
        after = len(self.long_term.entries)
        return before - after

    def export_all(self, output_dir: Path) -> Dict[str, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = {}
        paths["long_term"] = output_dir / "long_term_memory.jsonl"
        paths["profile"] = output_dir / "user_profile.json"
        paths["short_term"] = output_dir / "short_term_memory.jsonl"
        self.long_term.export(paths["long_term"])
        paths["profile"].write_text(json.dumps(self.profile.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        with open(paths["short_term"], "w", encoding="utf-8") as f:
            for entry in self.short_term.items:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        return paths

    def import_all(self, input_dir: Path) -> int:
        count = 0
        for name in ["long_term_memory.jsonl", "short_term_memory.jsonl"]:
            p = input_dir / name
            if p.exists():
                count += self.long_term.import_(p)
        profile_path = input_dir / "user_profile.json"
        if profile_path.exists():
            try:
                self.profile.data = json.loads(profile_path.read_text(encoding="utf-8"))
                self.profile.save()
            except Exception:
                pass
        return count


def main() -> None:
    p = argparse.ArgumentParser(description="AURA Memory Manager")
    p.add_argument("--remember", type=str, default=None, help="Recordar información")
    p.add_argument("--recall", type=str, default=None, help="Buscar en memoria")
    p.add_argument("--forget", type=str, default=None, help="Olvidar información")
    p.add_argument("--type", type=str, default="fact", choices=MEMORY_TYPES)
    p.add_argument("--tags", nargs="+", default=[])
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--context", action="store_true", help="Mostrar contexto reciente")
    p.add_argument("--profile", action="store_true", help="Mostrar perfil de usuario")
    p.add_argument("--update-profile", nargs="+", default=[], help="Actualizar perfil: key=value")
    p.add_argument("--decay", type=int, default=30, help="Días para decaimiento de memorias")
    p.add_argument("--export", type=str, default=None, help="Exportar memoria a directorio")
    p.add_argument("--import", dest="import_", type=str, default=None, help="Importar memoria desde directorio")
    args = p.parse_args()

    manager = MemoryManager()

    if args.remember:
        entry = manager.remember(args.remember, memory_type=args.type, tags=args.tags)
        print(json.dumps(entry.to_dict(), indent=2, ensure_ascii=False))
        return

    if args.recall:
        results = manager.recall(args.recall, top_k=args.top_k)
        print(json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False))
        return

    if args.forget:
        success = manager.forget(args.forget)
        print(json.dumps({"forgotten": success}, ensure_ascii=False))
        return

    if args.context:
        ctx = manager.get_context()
        print(json.dumps(ctx, indent=2, ensure_ascii=False))
        return

    if args.profile:
        print(json.dumps(manager.get_profile(), indent=2, ensure_ascii=False))
        return

    if args.update_profile:
        for item in args.update_profile:
            if "=" in item:
                key, value = item.split("=", 1)
                manager.update_profile(key.strip(), value.strip())
        print(json.dumps(manager.get_profile(), indent=2, ensure_ascii=False))
        return

    if args.decay:
        forgotten = manager.decay_old_memories(days=args.decay)
        print(json.dumps({"forgotten_count": forgotten}, ensure_ascii=False))
        return

    if args.export:
        paths = manager.export_all(Path(args.export))
        print(json.dumps({k: str(v) for k, v in paths.items()}, indent=2, ensure_ascii=False))
        return

    if args.import_:
        count = manager.import_all(Path(args.import_))
        print(json.dumps({"imported": count}, ensure_ascii=False))
        return

    p.print_help()


if __name__ == "__main__":
    main()