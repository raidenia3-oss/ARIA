# -*- coding: utf-8 -*-
"""AURA OS — Mistake Memory.

Prevents AURA from repeating failures by recording them
with context and checking before executing similar actions.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURA.MistakeMemory")


@dataclass
class MistakeEntry:
    mistake_id: str
    error_type: str
    error_message: str
    context: Dict[str, Any]
    stack: List[Dict[str, Any]]
    severity: str
    learned: bool = False
    times_repeated: int = 0
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)


class MistakeMemory:
    """Records and prevents repetition of errors."""

    MAX_ENTRIES = 500
    RECENCY_WINDOW = 86400
    MAX_REPEATS = 3

    def __init__(self) -> None:
        self.mistakes: Dict[str, MistakeEntry] = {}
        self._index_file = Path("data/learning/mistakes.json")
        self._index_file.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def record(self, error_type: str, error_message: str, context: Dict[str, Any] = None, severity: str = "medium") -> MistakeEntry:
        context = context or {}
        key = self._make_key(error_type, context)
        now = time.time()
        if key in self.mistakes:
            entry = self.mistakes[key]
            entry.times_repeated += 1
            entry.last_seen = now
            entry.context.update(context)
            if entry.times_repeated >= self.MAX_REPEATS:
                entry.severity = "critical"
            logger.warning("Mistake repeated: %s (x%d)", error_type, entry.times_repeated)
        else:
            mid = f"MIST-{int(now * 1000)}-{len(self.mistakes)}"
            entry = MistakeEntry(
                mistake_id=mid,
                error_type=error_type,
                error_message=error_message,
                context=context,
                stack=[{"type": error_type, "message": error_message, "time": now}],
                severity=severity,
                times_repeated=1,
            )
            self.mistakes[key] = entry
            logger.info("Mistake recorded: %s (x1)", error_type)
        self._trim_if_needed()
        self._save()
        return entry

    def check_before_execute(self, error_type: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        context = context or {}
        key = self._make_key(error_type, context)
        if key not in self.mistakes:
            return {"safe": True, "warnings": []}
        entry = self.mistakes[key]
        if entry.times_repeated >= self.MAX_REPEATS:
            return {
                "safe": False,
                "warning": f"Blocked: {error_type} repeated {entry.times_repeated} times",
                "mistake_id": entry.mistake_id,
                "alternative": self._suggest_alternative(entry),
                "severity": entry.severity,
            }
        if entry.times_repeated >= 2:
            return {
                "safe": True,
                "warnings": [f"Caution: {error_type} failed before ({entry.times_repeated}x)"],
                "mistake_id": entry.mistake_id,
            }
        return {"safe": True, "warnings": []}

    def learn_from(self, error_type: str, alternative_action: str) -> bool:
        for entry in self.mistakes.values():
            if entry.error_type == error_type:
                entry.learned = True
                entry.context["alternative"] = alternative_action
                logger.info("Learned alternative for %s: %s", error_type, alternative_action)
                self._save()
                return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        total = len(self.mistakes)
        learned = sum(1 for m in self.mistakes.values() if m.learned)
        critical = sum(1 for m in self.mistakes.values() if m.severity == "critical")
        recent = sum(1 for m in self.mistakes.values() if time.time() - m.last_seen < self.RECENCY_WINDOW)
        return {
            "total_mistakes": total,
            "learned": learned,
            "critical": critical,
            "recent": recent,
            "repeat_prevented": sum(1 for m in self.mistakes.values() if m.times_repeated >= self.MAX_REPEATS),
        }

    def get_recent_mistakes(self, limit: int = 10) -> List[Dict[str, Any]]:
        sorted_m = sorted(self.mistakes.values(), key=lambda m: m.last_seen, reverse=True)
        return [m.__dict__ for m in sorted_m[:limit]]

    def _make_key(self, error_type: str, context: Dict[str, Any]) -> str:
        context_str = json.dumps(context, sort_keys=True, default=str)
        import hashlib
        return hashlib.md5(f"{error_type}:{context_str}".encode()).hexdigest()

    def _suggest_alternative(self, entry: MistakeEntry) -> str:
        if "alternative" in entry.context:
            return entry.context["alternative"]
        if entry.error_type.startswith("research"):
            return "Try different search queries or reduce scope"
        if entry.error_type.startswith("automation"):
            return "Use alternative workflow or manual review"
        if entry.error_type.startswith("plugin"):
            return "Try different plugin or check dependencies"
        return "Retry with different parameters"

    def _trim_if_needed(self) -> None:
        if len(self.mistakes) > self.MAX_ENTRIES:
            sorted_m = sorted(self.mistakes.items(), key=lambda x: x[1].last_seen)
            to_remove = list(sorted_m[:self.MAX_ENTRIES // 4])
            for key, _ in to_remove:
                del self.mistakes[key]

    def _save(self) -> None:
        try:
            data = []
            for entry in self.mistakes.values():
                d = entry.__dict__.copy()
                d["first_seen"] = datetime.fromtimestamp(entry.first_seen).isoformat()
                d["last_seen"] = datetime.fromtimestamp(entry.last_seen).isoformat()
                data.append(d)
            self._index_file.write_text(json.dumps(data, indent=2, default=str))
        except Exception as exc:
            logger.debug("Save mistakes failed: %s", exc)

    def _load(self) -> None:
        try:
            if self._index_file.exists():
                data = json.loads(self._index_file.read_text())
                for entry in data:
                    first_seen = entry.get("first_seen", time.time())
                    last_seen = entry.get("last_seen", time.time())
                    if isinstance(first_seen, str):
                        try:
                            first_seen = datetime.fromisoformat(first_seen).timestamp()
                        except Exception:
                            first_seen = time.time()
                    if isinstance(last_seen, str):
                        try:
                            last_seen = datetime.fromisoformat(last_seen).timestamp()
                        except Exception:
                            last_seen = time.time()
                    e = MistakeEntry(
                        mistake_id=entry["mistake_id"],
                        error_type=entry["error_type"],
                        error_message=entry["error_message"],
                        context=entry.get("context", {}),
                        stack=entry.get("stack", []),
                        severity=entry.get("severity", "medium"),
                        learned=entry.get("learned", False),
                        times_repeated=entry.get("times_repeated", 0),
                        first_seen=first_seen,
                        last_seen=last_seen,
                    )
                    self.mistakes[e.mistake_id] = e
        except Exception:
            pass


mistake_memory = MistakeMemory()
