"""
Hunting loop for AME automation.
Main loop that iterates over target platforms, logs in, and launches the survey solver.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import List

from src.config.targets import load_targets
from automation.platform_adapters import PlatformAdapters
from automation.survey_solver import SurveySolver
from automation.financial_optimizer import FinancialOptimizer

logger = logging.getLogger(__name__)


class HuntingLoop:
    def __init__(self, on_event=None) -> None:
        self._on_event = on_event
        self.adapters = PlatformAdapters()
        self.solver = SurveySolver(on_event=on_event)

    async def _emit(self, message: str) -> None:
        if self._on_event:
            try:
                await self._on(message)
            except Exception:
                pass

    async def _on(self, message: str) -> None:
        if self._on_event:
            if asyncio.iscoroutinefunction(self._on_event):
                await self._on_event(message)
            else:
                self._on_event(message)

    async def run(self) -> None:
        targets = load_targets()
        if not targets:
            await self._emit("No targets configured.")
            return
        for target in targets:
            platform = target.get("platform")
            await self._emit(f"Starting platform: {platform}")
            login_result = await self.adapters.login_to_platform(platform)
            if login_result.get("status") != "ok":
                await self._emit(f"Login failed for {platform}: {login_result}")
                self._run_financial_optimizer()
                continue
            await self._emit(f"Login successful for {platform}")
            await self.solver.solve_survey(login_result.get("url", target.get("base_url", "")))
            self._run_financial_optimizer()
            await asyncio.sleep(random.uniform(2.0, 5.0))

    def _run_financial_optimizer(self) -> None:
        try:
            optimizer = FinancialOptimizer()
            result = optimizer.optimize_targets()
            logger.info("Financial optimization result: %s", result)
        except Exception as exc:
            logger.warning("Financial optimizer failed: %s", exc)
