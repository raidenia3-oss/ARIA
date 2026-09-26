"""AURA Short-Term Memory — recent interactions, file-backed."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ShortTermMemory:
    path: str
    max_items: int = 200
    _items: List[Dict[str, Any]] = field(default_factory=list)

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
                json.dump(self._items[-self.max_items :], f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def append(
        self, user_message: str, response: str, meta: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "user": user_message,
            "response": response,
            "meta": meta or {},
        }
        self._items.append(entry)
        if len(self._items) > self.max_items:
            self._items = self._items[-self.max_items :]
        self.save()
        return entry

    def recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        return list(reversed(self._items[-limit:]))

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        q = query.lower()
        matches = [
            item
            for item in self._items
            if q in item.get("user", "").lower() or q in item.get("response", "").lower()
        ]
        return list(reversed(matches[-limit:]))
