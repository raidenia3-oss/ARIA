# -*- coding: utf-8 -*-
"""AURA OS — Browser Pool.

Manages parallel browser sessions with isolation
for RollerCoin mining and web automation.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURA.BrowserPool")


@dataclass
class BrowserSession:
    session_id: str
    browser_type: str
    status: str = "idle"
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    task: Optional[str] = None
    memory_usage_mb: float = 0.0


class BrowserPool:
    """Pool of isolated browser sessions."""

    STORAGE_FILE = Path("data/learning/browser_pool.json")
    MAX_SESSIONS = 5

    def __init__(self, default_type: str = "chromium") -> None:
        self.default_type = default_type
        self.sessions: Dict[str, BrowserSession] = {}
        self._task_queue: List[str] = []
        self.STORAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def create_session(self, browser_type: str = None) -> BrowserSession:
        if len(self.sessions) >= self.MAX_SESSIONS:
            raise RuntimeError("Browser pool at maximum capacity")
        browser_type = browser_type or self.default_type
        session_id = f"BRW-{uuid.uuid4().hex[:12]}"
        session = BrowserSession(
            session_id=session_id,
            browser_type=browser_type,
        )
        self.sessions[session_id] = session
        self._save()
        logger.info("Browser session created: %s (%s)", session_id, browser_type)
        return session

    def get_session(self, session_id: str) -> Optional[BrowserSession]:
        return self.sessions.get(session_id)

    def assign_task(self, session_id: str, task: str) -> bool:
        session = self.sessions.get(session_id)
        if not session or session.status != "idle":
            return False
        session.status = "active"
        session.task = task
        session.last_activity = time.time()
        self._save()
        logger.info("Task '%s' assigned to %s", task, session_id)
        return True

    def complete_task(self, session_id: str) -> bool:
        session = self.sessions.get(session_id)
        if not session or session.status != "active":
            return False
        session.status = "idle"
        session.task = None
        session.last_activity = time.time()
        self._save()
        logger.info("Task completed on %s", session_id)
        return True

    def release_session(self, session_id: str) -> bool:
        if session_id in self.sessions:
            del self.sessions[session_id]
            self._save()
            return True
        return False

    def get_idle_sessions(self) -> List[BrowserSession]:
        return [s for s in self.sessions.values() if s.status == "idle"]

    def get_active_sessions(self) -> List[BrowserSession]:
        return [s for s in self.sessions.values() if s.status == "active"]

    def get_pool_status(self) -> Dict[str, Any]:
        return {
            "total_sessions": len(self.sessions),
            "idle": len(self.get_idle_sessions()),
            "active": len(self.get_active_sessions()),
            "max_sessions": self.MAX_SESSIONS,
            "available_slots": self.MAX_SESSIONS - len(self.sessions),
            "sessions": [
                {
                    "session_id": s.session_id,
                    "browser_type": s.browser_type,
                    "status": s.status,
                    "task": s.task,
                    "memory_mb": s.memory_usage_mb,
                    "age_seconds": round(time.time() - s.created_at, 1),
                }
                for s in self.sessions.values()
            ],
        }

    def cleanup_stale(self, max_idle_sec: int = 3600) -> List[str]:
        now = time.time()
        stale = []
        for sid, session in list(self.sessions.items()):
            if session.status == "idle" and now - session.last_activity > max_idle_sec:
                stale.append(sid)
                self.release_session(sid)
        return stale

    def _save(self) -> None:
        try:
            data = {
                "sessions": [s.__dict__ for s in self.sessions.values()],
            }
            self.STORAGE_FILE.write_text(json.dumps(data, indent=2, default=str))
        except Exception:
            pass

    def _load(self) -> None:
        try:
            if self.STORAGE_FILE.exists():
                data = json.loads(self.STORAGE_FILE.read_text())
                for s in data.get("sessions", []):
                    session = BrowserSession(
                        session_id=s["session_id"],
                        browser_type=s["browser_type"],
                        status=s.get("status", "idle"),
                        created_at=s.get("created_at", 0.0),
                        last_activity=s.get("last_activity", 0.0),
                        task=s.get("task"),
                        memory_usage_mb=s.get("memory_usage_mb", 0.0),
                    )
                    self.sessions[session.session_id] = session
        except Exception:
            pass


browser_pool = BrowserPool()
