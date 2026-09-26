"""Browser task tracker for AURA — tracks Chrome-extension-driven browser tasks."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger("AURABrowserTasks")


@dataclass
class BrowserTask:
    task_id: str
    action: str
    url: str
    tab_id: Optional[int]
    status: str = "pending"
    result_summary: str = ""
    created_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "action": self.action,
            "url": self._sanitize_url(self.url),
            "tab_id": self.tab_id,
            "status": self.status,
            "result_summary": self.result_summary,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "error": self.error,
        }

    @staticmethod
    def _sanitize_url(url: str) -> str:
        try:
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(url)
            safe = urlunparse((
                parsed.scheme,
                parsed.hostname or "",
                parsed.path,
                "",
                "",
                "",
            ))
            return safe
        except Exception:
            return "[unsanitized]"


class BrowserTaskManager:
    _instance: Optional["BrowserTaskManager"] = None

    def __init__(self) -> None:
        self._tasks: Dict[str, BrowserTask] = {}

    @classmethod
    def get_instance(cls) -> "BrowserTaskManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def create(self, task_id: str, action: str, url: str, tab_id: Optional[int] = None) -> BrowserTask:
        task = BrowserTask(task_id=task_id, action=action, url=url, tab_id=tab_id)
        self._tasks[task_id] = task
        logger.info("Browser task created: %s (%s)", task_id, action)
        return task

    def complete(self, task_id: str, summary: str = "") -> None:
        task = self._tasks.get(task_id)
        if task:
            task.status = "completed"
            task.result_summary = summary[:500]
            task.finished_at = time.time()
            logger.info("Browser task completed: %s", task_id)

    def fail(self, task_id: str, error: str) -> None:
        task = self._tasks.get(task_id)
        if task:
            task.status = "failed"
            task.error = str(error)[:500]
            task.finished_at = time.time()
            logger.error("Browser task failed: %s — %s", task_id, error)

    def cancel(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task:
            return False
        task.status = "cancelled"
        task.finished_at = time.time()
        return True

    def get(self, task_id: str) -> Optional[BrowserTask]:
        return self._tasks.get(task_id)

    def list(self, status_filter: Optional[str] = None) -> list:
        tasks = list(self._tasks.values())
        if status_filter:
            tasks = [t for t in tasks if t.status == status_filter]
        return [t.to_dict() for t in sorted(tasks, key=lambda t: t.created_at, reverse=True)]

    def cleanup(self, max_age_seconds: float = 3600) -> int:
        cutoff = time.time() - max_age_seconds
        expired = [tid for tid, t in self._tasks.items() if t.created_at < cutoff]
        for tid in expired:
            del self._tasks[tid]
        return len(expired)


browser_task_manager = BrowserTaskManager.get_instance()
