"""AURA MemoryManager — BLOQUE 105.

Tres niveles de memoria:
- Corto plazo: contexto actual de la conversación
- Mediano plazo: historial de la conversación
- Largo plazo: patrones permanentes (cognitive graph + consolidador)

Auto-comprime, busca por similitud.
"""
from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from backend.memory.cognitive_graph import CognitiveGraphEngine, get_cognitive_graph

logger = logging.getLogger("AURA.MemoryManager")


@dataclass
class MemoryEntry:
    key: str
    value: str
    level: str = "short"  # short | medium | long
    source: str = "interaction"
    timestamp: float = field(default_factory=time.time)
    access_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.access_count += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "level": self.level,
            "source": self.source,
            "timestamp": self.timestamp,
            "access_count": self.access_count,
            "metadata": self.metadata,
        }


class MemoryManager:
    """Gestor de memoria multinivel con auto-compresión y búsqueda semántica."""

    SHORT_MAX = 50
    MEDIUM_MAX = 200
    LONG_MAX = 500

    def __init__(self, graph: Optional[CognitiveGraphEngine] = None) -> None:
        self._graph = graph or get_cognitive_graph()
        self._short: Dict[str, MemoryEntry] = {}
        self._medium: Dict[str, MemoryEntry] = {}
        self._long: Dict[str, MemoryEntry] = {}
        self._lock = None
        self._session_context: Dict[str, Dict[str, Any]] = {}

    def _import_lock(self):
        import threading
        return threading.RLock()

    def store(self, key: str, value: str, level: str = "short",
              source: str = "interaction", metadata: Optional[Dict[str, Any]] = None) -> MemoryEntry:
        entry = MemoryEntry(
            key=key, value=value, level=level, source=source,
            timestamp=time.time(), metadata=metadata or {},
        )
        store_map = {"short": self._short, "medium": self._medium, "long": self._long}
        store_map[level][key] = entry
        self._enforce_limits(level)
        if level == "long":
            self._graph.ingest(value, source=source, summary=key, metadata=metadata)
        return entry

    def get(self, key: str, level: Optional[str] = None) -> Optional[MemoryEntry]:
        for lvl in ([level] if level else ["short", "medium", "long"]):
            entry = getattr(self, f"_{lvl}").get(key)
            if entry:
                entry.touch()
                return entry
        return None

    def search(self, query: str, limit: int = 10) -> List[MemoryEntry]:
        q = (query or "").lower()
        if not q:
            return []
        results: List[Tuple[int, MemoryEntry]] = []
        for level in ("short", "medium", "long"):
            for entry in getattr(self, f"_{level}").values():
                score = self._score(q, entry)
                if score > 0:
                    results.append((score, entry))
        results.sort(key=lambda x: x[0], reverse=True)
        seen = set()
        out: List[MemoryEntry] = []
        for _, entry in results:
            if entry.key in seen:
                continue
            seen.add(entry.key)
            out.append(entry)
            if len(out) >= limit:
                break
        return out

    def _score(self, query: str, entry: MemoryEntry) -> int:
        text = f"{entry.key} {entry.value}".lower()
        score = 0
        for word in query.split():
            if len(word) < 2:
                continue
            if word in text:
                score += 10
            if word in entry.key.lower():
                score += 5
        return score

    def _enforce_limits(self, level: str) -> None:
        limits = {"short": self.SHORT_MAX, "medium": self.MEDIUM_MAX, "long": self.LONG_MAX}
        store = getattr(self, f"_{level}")
        limit = limits[level]
        if len(store) <= limit:
            return
        sorted_entries = sorted(store.values(), key=lambda e: e.access_count)
        for entry in sorted_entries[: len(store) - limit]:
            store.pop(entry.key, None)
            if level == "long":
                self._promote(entry)

    def _promote(self, entry: MemoryEntry) -> None:
        if entry.level == "short":
            entry.level = "medium"
            self._medium[entry.key] = entry
        elif entry.level == "medium":
            entry.level = "long"
            self._long[entry.key] = entry
            self._graph.ingest(entry.value, source=entry.source, summary=entry.key)

    def set_session_context(self, session_id: str, ctx: Dict[str, Any]) -> None:
        self._session_context[session_id] = ctx

    def get_session_context(self, session_id: str) -> Dict[str, Any]:
        return self._session_context.get(session_id, {})

    def clear_session(self, session_id: str) -> None:
        self._session_context.pop(session_id, None)

    def compress(self) -> Dict[str, int]:
        """Auto-comprime: promueve entries frecuentes a largo plazo."""
        promoted = 0
        for entry in list(self._short.values()):
            if entry.access_count >= 5:
                self._promote(entry)
                promoted += 1
        summaries = self._graph.consolidate(force=True)
        return {"promoted": promoted, "summaries": len(summaries)}

    def stats(self) -> Dict[str, Any]:
        return {
            "short": len(self._short),
            "medium": len(self._medium),
            "long": len(self._long),
            "graph_nodes": len(self._graph._nodes),
            "graph_edges": len(self._graph._edges),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "short": [e.to_dict() for e in self._short.values()],
            "medium": [e.to_dict() for e in self._medium.values()],
            "long": [e.to_dict() for e in self._long.values()],
        }


_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    global _manager
    if _manager is None:
        _manager = MemoryManager()
    return _manager


def reset_memory_manager() -> None:
    global _manager
    _manager = None