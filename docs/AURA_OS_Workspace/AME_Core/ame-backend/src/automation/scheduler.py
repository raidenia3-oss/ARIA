"""
Async scheduler for AME automation tasks.
Runs the survey solver loop and publishes balance reports to the WebSocket bridge.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ame_backend.src.automation.survey_solver import SurveySolver


class AutomationScheduler:
    def __init__(self, ws_callback=None) -> None:
        self.scheduler = AsyncIOScheduler()
        self.ws_callback = ws_callback
        self.solver = SurveySolver()
        self.report_path = Path("ame-backend/src/automation/balance_report.json")

    def _build_report(self) -> Dict[str, Any]:
        rejection_log = Path("ame-backend/src/automation/rejection_logs.json")
        data: Dict[str, Any] = {
            "ts": datetime.now().isoformat(),
            "status": "running",
            "history_len": len(self.solver.history),
            "rejections": 0,
        }
        if rejection_log.exists():
            try:
                data["rejections"] = len(json.loads(rejection_log.read_text(encoding="utf-8")))
            except Exception:
                data["rejections"] = 0
        return data

    async def _publish_report(self) -> None:
        report = self._build_report()
        if self.report_path.exists():
            try:
                existing = json.loads(self.report_path.read_text(encoding="utf-8"))
            except Exception:
                existing = []
        else:
            existing = []
        existing.append(report)
        self.report_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        if self.ws_callback:
            try:
                await self.ws_callback(json.dumps(report))
            except Exception:
                pass

    def start(self) -> None:
        self.scheduler.add_job(self._publish_report, "interval", hours=6, id="report_job")
        self.scheduler.start()

    def stop(self) -> None:
        self.scheduler.shutdown(wait=False)
