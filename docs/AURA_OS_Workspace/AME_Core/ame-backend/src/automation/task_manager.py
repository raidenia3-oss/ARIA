"""
Task manager for AME automation.
Starts and tracks background automation tasks (surveys, etc.) using asyncio.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from ame_backend.src.automation.survey_solver import SurveySolver

logger = logging.getLogger(__name__)


class TaskManager:
    def __init__(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        self._loop = loop or asyncio.get_event_loop()
        self._tasks: Dict[str, asyncio.Task] = {}
        self._solver = SurveySolver()

    def start_survey_bot(self, start_url: str) -> Dict[str, Any]:
        if "surveys" in self._tasks and not self._tasks["surveys"].done():
            return {"status": "already_running", "target": "surveys"}

        task = self._loop.create_task(self._run_survey(start_url))
        self._tasks["surveys"] = task
        logger.info("Started survey bot task")
        return {"status": "started", "target": "surveys"}

    async def _run_survey(self, start_url: str) -> None:
        try:
            await self._solver.solve_survey(start_url)
        except Exception as exc:
            logger.exception("Survey bot failed: %s", exc)

    def stop_survey_bot(self) -> Dict[str, Any]:
        task = self._tasks.get("surveys")
        if not task or task.done():
            return {"status": "not_running", "target": "surveys"}
        task.cancel()
        return {"status": "stopped", "target": "surveys"}

    def status(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for name, task in self._tasks.items():
            out[name] = {
                "done": task.done(),
                "cancelled": task.cancelled(),
            }
        return out
