# -*- coding: utf-8 -*-
"""AURA OS - Revenue Aggregator (REAL bots)."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List

from backend.core import get_event_bus
from backend.revenue.rollercoin_bot_real import run_rollercoin_bot_real
from backend.revenue.crypto_bot_real import monitor_crypto_real
from backend.revenue.mistplay_bot_real import run_mistplay_real
from backend.revenue.survey_bot_real import complete_surveys_real

logger = logging.getLogger("AURA.RevenueAggregator")


class RevenueAggregator:
    """Agrega ingresos REALES de todos los bots."""

    def __init__(self) -> None:
        self.total_earned: float = 0.0
        self.revenue_log: List[Dict[str, Any]] = []
        self._bus = get_event_bus()

    async def run_all_generators(self) -> Dict[str, Any]:
        """Corre todos los generadores REALES en paralelo."""
        logger.info("[REVENUE] Ejecutando generadores REALES...")

        results = await asyncio.gather(
            run_rollercoin_bot_real(),
            monitor_crypto_real(),
            run_mistplay_real(),
            complete_surveys_real(),
            return_exceptions=True,
        )

        rollercoin_profit, crypto_profit, mistplay_profit, survey_profit = results

        # Manejar excepciones
        names = ["rollercoin", "crypto", "mistplay", "surveys"]
        for i, name in enumerate(names):
            val = results[i]
            if isinstance(val, Exception):
                logger.error("[REVENUE] Error en %s: %s", name, val)
                results[i] = 0.0

        rollercoin_profit = float(results[0] or 0)
        crypto_profit = float(results[1] or 0)
        mistplay_profit = float(results[2] or 0)
        survey_profit = float(results[3] or 0)

        total = rollercoin_profit + crypto_profit + mistplay_profit + survey_profit
        self.total_earned += total

        record = {
            "timestamp": datetime.now().isoformat(),
            "by_source": {
                "rollercoin": rollercoin_profit,
                "crypto": crypto_profit,
                "mistplay": mistplay_profit,
                "surveys": survey_profit,
            },
            "total": total,
        }
        self.revenue_log.append(record)

        logger.info("[REVENUE] Ciclo REAL: +$%.2f (Total: $%.2f)", total, self.total_earned)

        self._bus.emit_simple("revenue_cycle_complete", {
            "total": total,
            "by_source": record["by_source"],
            "total_earned": self.total_earned,
            "timestamp": datetime.now().isoformat(),
            "source": "real",
        }, agent="revenue")

        return {
            "total_earned": total,
            "by_source": record["by_source"],
            "timestamp": record["timestamp"],
        }

    def get_today(self) -> Dict[str, Any]:
        """Retorna ingresos del dia actual."""
        today = datetime.now().strftime("%Y-%m-%d")
        today_earned = sum(
            r["total"] for r in self.revenue_log
            if r["timestamp"].startswith(today)
        )
        return {
            "total_earned_usd": round(today_earned, 4),
            "cycles": len([r for r in self.revenue_log if r["timestamp"].startswith(today)]),
            "timestamp": datetime.now().isoformat(),
        }