"""ARIA Working Memory — session-scoped context."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


class WorkingMemory:
    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}

    def set(self, session_id: str, key: str, value: Any) -> None:
        self._store.setdefault(session_id, {})[key] = value

    def get(self, session_id: str, key: str, default: Any = None) -> Any:
        return self._store.get(session_id, {}).get(key, default)

    def snapshot(self, session_id: str) -> Dict[str, Any]:
        return dict(self._store.get(session_id, {}))

    def reset(self, session_id: str) -> None:
        self._store.pop(session_id, None)

    def all(self) -> Dict[str, Dict[str, Any]]:
        return {k: dict(v) for k, v in self._store.items()}
