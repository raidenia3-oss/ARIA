"""ARIA Proactive System — event-driven alerts, reminders, owner state engine."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ProactiveEvent:
    id: str
    type: str
    title: str
    body: str
    severity: str = "info"
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Reminder:
    id: str
    title: str
    body: str
    due_at: str
    repeat: str = "none"
    created_at: float = field(default_factory=time.time)
    meta: Dict[str, Any] = field(default_factory=dict)


class ProactiveSystem:
    def __init__(self, storage_dir: Optional[str] = None) -> None:
        if storage_dir is None:
            base = Path(__file__).resolve().parent.parent.parent
            storage_dir = str(base / "logs" / "proactive")
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._alerts: List[ProactiveEvent] = []
        self._reminders: List[Reminder] = []
        self._owner_state: Dict[str, Any] = {
            "mood": "neutral",
            "focus": "unknown",
            "last_activity": time.time(),
        }
        self._load()

    def alert(
        self, title: str, body: str, severity: str = "info", ttl_seconds: int = 3600
    ) -> ProactiveEvent:
        event = ProactiveEvent(
            id=str(int(time.time() * 1000)),
            type="alert",
            title=title,
            body=body,
            severity=severity,
            expires_at=time.time() + ttl_seconds,
        )
        self._alerts.append(event)
        self._save_alerts()
        return event

    def remind(self, title: str, body: str, due_at: str, repeat: str = "none") -> Reminder:
        reminder = Reminder(
            id=str(int(time.time() * 1000)),
            title=title,
            body=body,
            due_at=due_at,
            repeat=repeat,
        )
        self._reminders.append(reminder)
        self._save_reminders()
        return reminder

    def update_owner_state(
        self, mood: str = "", focus: str = "", activity: str = ""
    ) -> Dict[str, Any]:
        if mood:
            self._owner_state["mood"] = mood
        if focus:
            self._owner_state["focus"] = focus
        if activity:
            self._owner_state["last_activity"] = time.time()
            self._owner_state["last_activity_type"] = activity
        self._save_owner_state()
        return dict(self._owner_state)

    def active_alerts(self, limit: int = 20) -> List[Dict[str, Any]]:
        now = time.time()
        items = [e for e in self._alerts if (e.expires_at or 0) >= now]
        items.sort(key=lambda e: e.created_at, reverse=True)
        return [self._event_to_dict(e) for e in items[:limit]]

    def due_reminders(self, limit: int = 20) -> List[Dict[str, Any]]:
        now = datetime.utcnow().isoformat() + "Z"
        items = [r for r in self._reminders if r.due_at <= now]
        items.sort(key=lambda r: r.due_at, reverse=True)
        return [self._reminder_to_dict(r) for r in items[:limit]]

    def owner_state(self) -> Dict[str, Any]:
        return dict(self._owner_state)

    def _event_to_dict(self, e: ProactiveEvent) -> Dict[str, Any]:
        return {
            "id": e.id,
            "type": e.type,
            "title": e.title,
            "body": e.body,
            "severity": e.severity,
            "created_at": e.created_at,
            "expires_at": e.expires_at,
        }

    def _reminder_to_dict(self, r: Reminder) -> Dict[str, Any]:
        return {
            "id": r.id,
            "title": r.title,
            "body": r.body,
            "due_at": r.due_at,
            "repeat": r.repeat,
            "created_at": r.created_at,
        }

    def _save_alerts(self) -> None:
        try:
            path = self.storage_dir / "alerts.json"
            path.write_text(
                json.dumps([self._event_to_dict(e) for e in self._alerts], ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _save_reminders(self) -> None:
        try:
            path = self.storage_dir / "reminders.json"
            path.write_text(
                json.dumps(
                    [self._reminder_to_dict(r) for r in self._reminders], ensure_ascii=False
                ),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _save_owner_state(self) -> None:
        try:
            path = self.storage_dir / "owner_state.json"
            path.write_text(json.dumps(self._owner_state, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def _load(self) -> None:
        for name, attr, cls in [
            ("alerts.json", "_alerts", ProactiveEvent),
            ("reminders.json", "_reminders", Reminder),
        ]:
            path = self.storage_dir / name
            if not path.exists():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if name == "alerts.json":
                    self._alerts = [cls(**item) for item in data]
                else:
                    self._reminders = [cls(**item) for item in data]
            except Exception:
                pass
        path = self.storage_dir / "owner_state.json"
        if path.exists():
            try:
                self._owner_state = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
