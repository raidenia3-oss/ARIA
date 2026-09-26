# -*- coding: utf-8 -*-
"""AURA OS — Learning Daemon.

Executes the autonomous learning cycle every 6 hours:
1. Evaluates recent research
2. Proposes improvements
3. Updates knowledge graph
4. Evolves prompts
5. Records mistakes
6. Reports to dashboard
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURA.LearningDaemon")

CYCLE_INTERVAL = 21600


class LearningDaemon:
    """Autonomous learning cycle daemon."""

    def __init__(self) -> None:
        self.active: bool = False
        self._task: Optional[asyncio.Task] = None
        self.last_cycle: float = 0.0
        self.cycle_count: int = 0
        self.results: List[Dict[str, Any]] = []

    async def start(self) -> None:
        self.active = True
        logger.info("Learning daemon started")
        while self.active:
            try:
                await self.run_cycle()
            except Exception as exc:
                logger.error("Cycle error: %s", exc)
            await asyncio.sleep(CYCLE_INTERVAL)

    async def run_cycle(self) -> Dict[str, Any]:
        logger.info("=== Learning cycle %d ===", self.cycle_count + 1)
        result: Dict[str, Any] = {"cycle": self.cycle_count, "timestamp": datetime.now().isoformat()}

        try:
            from backend.learning.learning_loop import learning_engine
            report = learning_engine.get_learning_report()
            result["evaluation_report"] = report
            proposals = learning_engine.propose_improvements()
            result["proposals"] = [{"title": p.title, "impact": p.impact} for p in proposals]
            for p in proposals[:3]:
                learning_engine.apply_proposal(p.proposal_id)
        except Exception as exc:
            logger.debug("Eval cycle: %s", exc)
            result["evaluation_error"] = str(exc)

        try:
            from backend.learning.mistake_memory import mistake_memory
            stats = mistake_memory.get_stats()
            result["mistake_stats"] = stats
            if stats.get("critical", 0) > 0:
                logger.warning("%d critical mistakes to review", stats["critical"])
        except Exception as exc:
            logger.debug("Mistake cycle: %s", exc)
            result["mistake_error"] = str(exc)

        try:
            from backend.learning.knowledge_graph import knowledge_graph
            kg_stats = knowledge_graph.get_stats()
            gaps = knowledge_graph.detect_gaps("research")
            result["kg_stats"] = kg_stats
            result["knowledge_gaps"] = gaps[:5]
        except Exception as exc:
            logger.debug("KG cycle: %s", exc)
            result["kg_error"] = str(exc)

        try:
            from backend.learning.auto_prompt import auto_prompt_generator
            best = auto_prompt_generator.get_best_prompt("research")
            if best:
                result["best_prompt_evolved"] = True
                result["best_prompt"] = best[:200]
            stats = auto_prompt_generator.get_stats()
            result["prompt_stats"] = stats
            if stats.get("total_prompts", 0) > 5:
                new_best = auto_prompt_generator.evolve("research")
                result["evolved"] = True
        except Exception as exc:
            logger.debug("Prompt cycle: %s", exc)
            result["prompt_error"] = str(exc)

        try:
            from backend.learning.auto_scaling import auto_scaler
            bottleneck_report = auto_scaler.get_bottlenecks_report()
            perf = auto_scaler.get_perf_report()
            result["bottlenecks"] = bottleneck_report
            result["performance"] = perf
            decision = auto_scaler.scale("research")
            result["scale_decision"] = decision.__dict__ if hasattr(decision, "__dict__") else str(decision)
        except Exception as exc:
            logger.debug("Scale cycle: %s", exc)
            result["scale_error"] = str(exc)

        result["success"] = True
        self.last_cycle = time.time()
        self.cycle_count += 1
        self.results.append(result)
        logger.info("=== Learning cycle %d complete ===", self.cycle_count)
        return result

    def stop(self) -> None:
        self.active = False
        if self._task:
            self._task.cancel()
        logger.info("Learning daemon stopped after %d cycles", self.cycle_count)

    def get_status(self) -> Dict[str, Any]:
        return {
            "active": self.active,
            "cycle_count": self.cycle_count,
            "last_cycle": datetime.fromtimestamp(self.last_cycle).isoformat() if self.last_cycle else None,
            "cycle_interval_sec": CYCLE_INTERVAL,
            "next_cycle_in": max(0, CYCLE_INTERVAL - (time.time() - self.last_cycle)) if self.last_cycle else CYCLE_INTERVAL,
            "results_count": len(self.results),
        }


learning_daemon = LearningDaemon()
