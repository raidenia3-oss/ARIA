# -*- coding: utf-8 -*-
"""AURA OS - Survey Bot (OPCION A - SIMULADO)."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict

from backend.core import get_event_bus

logger = logging.getLogger("AURA.SurveyBot")


async def complete_surveys_auto() -> float:
    """Completa encuestas automaticamente (SIMULADO)."""
    bus = get_event_bus()
    logger.info("[SURVEY] Buscando encuestas...")
    bus.emit_simple("survey_started", {"timestamp": datetime.now().isoformat()}, agent="revenue")

    surveys = [f"Survey_{i}" for i in range(1, 6)]
    total_points = 0

    for sid in surveys:
        await asyncio.sleep(2.0)
        points = 15  # fake: 10-20 pts
        total_points += points
        logger.info("[SURVEY] Completada %s: %d puntos", sid, points)
        bus.emit_simple("survey_completed", {
            "survey_id": sid,
            "points": points,
            "timestamp": datetime.now().isoformat(),
        }, agent="revenue")

    usd_value = 0.20
    fee = usd_value * 0.25
    net_profit = usd_value - fee

    logger.info("[SURVEY] Total puntos: %d = $%.2f, fees: $%.2f, neto: $%.2f", total_points, usd_value, fee, net_profit)

    bus.emit_simple("surveys_complete", {
        "surveys": len(surveys),
        "total_points": total_points,
        "net_profit": net_profit,
        "timestamp": datetime.now().isoformat(),
    }, agent="revenue")

    return net_profit