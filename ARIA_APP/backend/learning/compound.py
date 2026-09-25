"""ARIA Compound Learning — mistakes become permanent rules."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class MistakeCluster:
    pattern: str
    occurrences: int = 1
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    rule: str = ""
    active: bool = True


class CompoundLearning:
    def __init__(self, storage_dir: Optional[str] = None) -> None:
        if storage_dir is None:
            base = Path(__file__).resolve().parent.parent
            storage_dir = str(base / "logs" / "learning")
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._clusters: Dict[str, MistakeCluster] = {}
        self._load()

    def record_error(self, pattern: str, context: Optional[str] = None) -> Dict[str, Any]:
        if pattern in self._clusters:
            cluster = self._clusters[pattern]
            cluster.occurrences += 1
            cluster.last_seen = time.time()
            if context:
                cluster.rule = context
        else:
            self._clusters[pattern] = MistakeCluster(pattern=pattern, rule=context or "")
        self._save()
        cluster = self._clusters[pattern]
        if cluster.occurrences >= 3 and not cluster.rule:
            cluster.rule = f"Avoid repeating: {pattern}"
        return {
            "pattern": pattern,
            "occurrences": cluster.occurrences,
            "rule": cluster.rule,
            "active": cluster.active,
        }

    def get_rule(self, pattern: str) -> Optional[str]:
        c = self._clusters.get(pattern)
        if c and c.active and c.rule:
            return c.rule
        return None

    def active_rules(self, limit: int = 20) -> List[Dict[str, Any]]:
        items = [c for c in self._clusters.values() if c.active and c.rule]
        items.sort(key=lambda c: c.occurrences, reverse=True)
        return [
            {
                "pattern": c.pattern,
                "occurrences": c.occurrences,
                "rule": c.rule,
                "last_seen": c.last_seen,
            }
            for c in items[:limit]
        ]

    def suppress(self, pattern: str) -> Dict[str, Any]:
        if pattern in self._clusters:
            self._clusters[pattern].active = False
            self._save()
            return {"pattern": pattern, "suppressed": True}
        return {"pattern": pattern, "suppressed": False}

    def _save(self) -> None:
        try:
            path = self.storage_dir / "mistakes.json"
            data = {
                p: {
                    "pattern": c.pattern,
                    "occurrences": c.occurrences,
                    "first_seen": c.first_seen,
                    "last_seen": c.last_seen,
                    "rule": c.rule,
                    "active": c.active,
                }
                for p, c in self._clusters.items()
            }
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _load(self) -> None:
        path = self.storage_dir / "mistakes.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for pattern, item in data.items():
                c = MistakeCluster(pattern=item.get("pattern", pattern))
                c.occurrences = item.get("occurrences", 1)
                c.first_seen = item.get("first_seen", time.time())
                c.last_seen = item.get("last_seen", time.time())
                c.rule = item.get("rule", "")
                c.active = item.get("active", True)
                self._clusters[pattern] = c
        except Exception:
            pass
