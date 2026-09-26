# -*- coding: utf-8 -*-
"""AURA OS - Tests for OPCIÓN A Revenue Generators."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime

import pytest

from backend.core import get_event_bus, reset_event_bus
from backend.daemon.aura_daemon import get_daemon
from backend.revenue.crypto_opportunities import monitor_crypto_opportunities
from backend.revenue.mistplay_bot import run_mistplay_bot
from backend.revenue.revenue_aggregator import RevenueAggregator
from backend.revenue.rollercoin_bot_advanced import run_rollercoin_bot
from backend.revenue.survey_bot import complete_surveys_auto


@pytest.fixture(autouse=True)
def _fresh_bus():
    reset_event_bus()
    yield
    reset_event_bus()


@pytest.mark.asyncio
async def test_rollercoin_returns_float():
    """test_rollercoin_returns_float - verifica que rollercoin retorna float > 0."""
    result = await run_rollercoin_bot()
    assert isinstance(result, float)
    assert result > 0
    assert result == pytest.approx(0.65, abs=0.01)


@pytest.mark.asyncio
async def test_crypto_returns_float():
    """test_crypto_returns_float - verifica que crypto retorna float > 0."""
    result = await monitor_crypto_opportunities()
    assert isinstance(result, float)
    assert result > 0
    # 3 opportunities: 0.35 + 0.28 + 0.22 = 0.85
    assert result == pytest.approx(0.85, abs=0.01)


@pytest.mark.asyncio
async def test_mistplay_returns_float():
    """test_mistplay_returns_float - verifica que mistplay retorna float > 0."""
    result = await run_mistplay_bot()
    assert isinstance(result, float)
    assert result > 0
    # usd_value=0.40, fee=30%=0.12, net=0.28
    assert result == pytest.approx(0.28, abs=0.01)


@pytest.mark.asyncio
async def test_surveys_returns_float():
    """test_surveys_returns_float - verifica que surveys retorna float > 0."""
    result = await complete_surveys_auto()
    assert isinstance(result, float)
    assert result > 0
    # usd_value=0.20, fee=25%=0.05, net=0.15
    assert result == pytest.approx(0.15, abs=0.01)


@pytest.mark.asyncio
async def test_revenue_aggregator_runs():
    """test_revenue_aggregator_runs - verifica que el aggregator corre todos los bots."""
    agg = RevenueAggregator()
    result = await agg.run_all_generators()

    assert "total_earned" in result
    assert "by_source" in result
    assert result["total_earned"] > 0

    sources = result["by_source"]
    assert "rollercoin" in sources
    assert "crypto" in sources
    assert "mistplay" in sources
    assert "surveys" in sources

    assert sources["rollercoin"] > 0
    assert sources["crypto"] > 0
    assert sources["mistplay"] > 0
    assert sources["surveys"] > 0

    # Verificar que se guardo en el log
    assert len(agg.revenue_log) >= 1
    assert agg.total_earned > 0


def test_revenue_endpoints():
    """test_revenue_endpoints - verifica que los endpoints de revenue existen."""
    from backend.daemon.daemon_routes import router

    paths = [r.path for r in router.routes]
    # router has prefix /api/daemon
    assert "/api/daemon/revenue/today" in paths
    assert "/api/daemon/revenue/log" in paths
    assert "/api/daemon/revenue/status" in paths


def test_daemon_has_revenue():
    """test_daemon_has_revenue - verifica que el daemon tiene revenue integrado."""
    daemon = get_daemon()
    assert hasattr(daemon, "revenue_aggregator")
    assert hasattr(daemon, "total_revenue")
    assert hasattr(daemon, "_run_revenue_generators")
    assert daemon.total_revenue == 0.0
