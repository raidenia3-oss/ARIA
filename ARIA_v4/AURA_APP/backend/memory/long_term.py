"""AURA Long-Term Memory — persistent facts with optional vector search."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class LongTermMemory:
    path: str
    _items: List[Dict[str, Any]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self._items = []

    def load(self) -> None:
        if not os.path.exists(self.path):
            self._items = []
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self._items = json.load(f)
        except Exception:
            self._items = []

    def save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._items, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def add(self, content: str, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        entry = {
            "id": str(abs(hash(content + str(datetime.utcnow().isoformat())))),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "content": content,
            "meta": meta or {},
        }
        self._items.append(entry)
        self.save()
        return entry

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        q = query.lower()
        scored = []
        for item in self._items:
            text = json.dumps(item, ensure_ascii=False).lower()
            score = text.count(q)
            if score > 0:
                scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:limit]]

    def all(self, limit: int = 100) -> List[Dict[str, Any]]:
        return list(reversed(self._items[-limit:]))
