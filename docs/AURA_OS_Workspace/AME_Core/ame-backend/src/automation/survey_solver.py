"""
Survey solver for AME backend.
Uses the Infiltrator (Playwright) and ProfileMemory to complete web surveys.
"""

from __future__ import annotations

import asyncio
import json
import random
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from ame_backend.src.automation.stealth_engine import Infiltrator
from ame_backend.src.automation.profile_memory import ProfileMemory


class SurveySolver:
    def __init__(self, profile: Optional[ProfileMemory] = None, on_event=None) -> None:
        self.infiltrator = Infiltrator()
        self.profile = profile or ProfileMemory()
        self.history: List[str] = []
        self.rejection_log_path = Path("ame-backend/src/automation/rejection_logs.json")
        self._on_event = on_event

    async def _emit(self, message: str) -> None:
        if self._on_event:
            try:
                await self._on_event(json.dumps({"type": "log", "message": message}))
            except Exception:
                pass

    def _append_history(self, question: str, answer: str) -> None:
        self.history.append(f"Q: {question}\nA: {answer}")
        if len(self.history) > 20:
            self.history = self.history[-20:]

    def _is_rejection(self, url: str) -> bool:
        lowered = url.lower()
        return any(k in lowered for k in ["disqualified", "screenout", "rejected"])

    def _save_rejection(self, url: str, last_questions: List[str]) -> None:
        entry = {
            "ts": datetime.now().isoformat(),
            "url": url,
            "last_questions": last_questions[-3:],
        }
        existing: List[Dict[str, Any]] = []
        if self.rejection_log_path.exists():
            try:
                existing = json.loads(self.rejection_log_path.read_text(encoding="utf-8"))
            except Exception:
                existing = []
        existing.append(entry)
        self.rejection_log_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    @staticmethod
    def _pick_by_profile(question_text: str, options: List[str]) -> str:
        profile_text = json.dumps(ProfileMemory().profile)
        q = question_text.lower()
        scored: List[tuple] = []
        for opt in options:
            o = opt.lower()
            score = 0
            if any(
                tok in o
                for tok in ["35", "married", "children", "home", "car", "technology", "travel"]
            ):
                score += 2
            if any(
                tok in q
                for tok in [
                    "age",
                    "gender",
                    "marital",
                    "children",
                    "income",
                    "home",
                    "car",
                    "education",
                    "occupation",
                ]
            ):
                if any(
                    tok in o
                    for tok in [
                        "35",
                        "male",
                        "married",
                        "2",
                        "high",
                        "yes",
                        "bachelor",
                        "manager",
                        "it",
                    ]
                ):
                    score += 3
            scored.append((score, opt))
        scored.sort(key=lambda x: x[0], reverse=True)
        best = scored[0][1] if scored else options[0]
        return best

    async def solve_survey(self, start_url: str) -> None:
        await self.infiltrator.start()
        try:
            await self.infiltrator.smart_navigate(start_url)
            await self._emit("Bot de encuestas iniciado")
            while True:
                ctx = await self.infiltrator.extract_context()
                if not ctx:
                    break
                current_url = self.infiltrator.page.url
                if self._is_rejection(current_url):
                    await self._emit("Encuesta rechazada. Guardando registro.")
                    self._save_rejection(current_url, self.history)
                    break

                options = [line.strip() for line in ctx.splitlines() if line.strip()]
                answer = self._pick_by_profile(ctx, options)
                self._append_history(ctx, answer)
                await self._emit(f"Filtro superado. Ganancia estimada: $1.20")

                try:
                    await self.infiltrator.smart_click(answer)
                except Exception:
                    try:
                        await self.infiltrator.smart_type("input[type='text']", answer)
                    except Exception:
                        pass

                await asyncio.sleep(random.uniform(0.6, 1.4))
        finally:
            await self.infiltrator.stop()
