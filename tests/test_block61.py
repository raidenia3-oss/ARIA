"""Pruebas para BLOQUE 61 — AURA Master System Integration.

Valida el modulo de diagnostico maestro:
- snapshot/readiness con puertos, modulos, env vars.
- endpoints REST del master router.
- Sin dependencias cloud ni tokens expuestos.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict
from unittest.mock import patch

import pytest

from backend.core.diagnostics import (
    ECOSYSTEM_PORTS,
    MasterDiagnostics,
    _aggregate_status,
    _e2e_readiness,
    _ecosystem_modules,
    _env_status,
    get_master_diagnostics,
    master_health,
    master_readiness,
    master_snapshot,
)
from backend.core.routes import router as master_router

# ---------------------------------------------------------------------------
# _aggregate_status
# ---------------------------------------------------------------------------


def test_aggregate_status_all_down():
    readiness = {
        "backend_port": "down",
        "jan_port": "down",
        "ollama_port": "down",
        "frontend_port": "down",
        "discord_port": "down",
    }
    assert _aggregate_status(readiness) == "unhealthy"


def test_aggregate_status_all_up():
    readiness = {
        "backend_port": "ok",
        "jan_port": "ok",
        "ollama_port": "ok",
        "frontend_port": "ok",
        "discord_port": "ok",
    }
    assert _aggregate_status(readiness) == "healthy"


def test_aggregate_status_degraded_majority_up():
    readiness = {
        "backend_port": "ok",
        "jan_port": "ok",
        "ollama_port": "down",
        "frontend_port": "down",
        "discord_port": "down",
    }
    assert _aggregate_status(readiness) == "degraded"


def test_aggregate_status_empty():
    assert _aggregate_status({}) == "degraded"


# ---------------------------------------------------------------------------
# _env_status
# ---------------------------------------------------------------------------


def test_env_status_returns_presence_not_values():
    result = _env_status()
    assert isinstance(result, dict)
    for key in ("AURA_API_KEY", "DATABASE_URL", "HF_TOKEN", "ENVIRONMENT"):
        assert key in result
        assert result[key] in ("set", "missing")
    # Nunca expone el valor real
    for value in result.values():
        assert isinstance(value, str)


def test_env_status_with_mocked_env():
    with patch.dict(os.environ, {"AURA_API_KEY": "secret-value", "DATABASE_URL": "postgres://x"}):
        result = _env_status()
        assert result["AURA_API_KEY"] == "set"
        assert result["DATABASE_URL"] == "set"
        assert result["HF_TOKEN"] == "missing"


# ---------------------------------------------------------------------------
# _ecosystem_modules
# ---------------------------------------------------------------------------


def test_ecosystem_modules_returns_dict():
    result = _ecosystem_modules()
    assert isinstance(result, dict)
    assert "backend.main" in result
    assert "backend.diagnostics.health" in result
    assert "backend.production_routes" in result
    for value in result.values():
        assert value in ("ok", "error")


def test_ecosystem_modules_includes_block61():
    result = _ecosystem_modules()
    assert "backend.core.diagnostics" in result
    assert result["backend.core.diagnostics"] == "ok"


# ---------------------------------------------------------------------------
# _e2e_readiness
# ---------------------------------------------------------------------------


def test_e2e_readiness_structure():
    readiness = _e2e_readiness()
    assert isinstance(readiness, dict)
    for port_key in ECOSYSTEM_PORTS:
        assert f"{port_key}_port" in readiness
        assert readiness[f"{port_key}_port"] in ("ok", "down")
    assert "env_vars" in readiness
    assert "modules" in readiness
    assert "timestamp" in readiness


def test_e2e_readiness_timestamp_fresh():
    before = time.time()
    readiness = _e2e_readiness()
    after = time.time()
    assert before <= readiness["timestamp"] <= after


# ---------------------------------------------------------------------------
# MasterDiagnostics
# ---------------------------------------------------------------------------


def test_master_diagnostics_snapshot_structure():
    md = MasterDiagnostics()
    snap = md.snapshot()
    assert "status" in snap
    assert snap["status"] in ("healthy", "degraded", "unhealthy")
    assert "readiness" in snap
    assert "health_daemon" in snap
    assert "timestamp" in snap
    assert "iso" in snap


def test_master_diagnostics_health_flag():
    md = MasterDiagnostics()
    health = md.health()
    assert "healthy" in health
    assert isinstance(health["healthy"], bool)
    assert health["healthy"] == (health["status"] == "healthy")


def test_master_diagnostics_readiness():
    md = MasterDiagnostics()
    readiness = md.readiness()
    assert isinstance(readiness, dict)
    for port_key in ECOSYSTEM_PORTS:
        assert f"{port_key}_port" in readiness


def test_master_diagnostics_singleton():
    a = get_master_diagnostics()
    b = get_master_diagnostics()
    assert a is b


def test_master_snapshot_function():
    snap = master_snapshot()
    assert "status" in snap
    assert "readiness" in snap


def test_master_health_function():
    health = master_health()
    assert "healthy" in health
    assert isinstance(health["healthy"], bool)


def test_master_readiness_function():
    readiness = master_readiness()
    assert isinstance(readiness, dict)
    assert "timestamp" in readiness
    for port_key in ECOSYSTEM_PORTS:
        assert f"{port_key}_port" in readiness


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


def test_master_router_has_routes():
    routes = [r.path for r in master_router.routes]
    assert "/api/master/health" in routes
    assert "/api/master/readiness" in routes
    assert "/api/master/ports" in routes
    assert "/api/master/modules" in routes
    assert "/api/master/env" in routes
    assert "/api/master/snapshot/force" in routes


def test_master_router_prefix():
    assert master_router.prefix == "/api/master"
    assert "master-diagnostics" in master_router.tags


# ---------------------------------------------------------------------------
# No cloud dependencies
# ---------------------------------------------------------------------------


def test_no_cloud_imports_in_diagnostics():
    """Verifica que el modulo no importa servicios cloud."""
    import backend.core.diagnostics as mod

    source = open(mod.__file__).read()
    forbidden = ["boto3", "azure", "google.cloud", "sentry_sdk", "datadog"]
    for bad in forbidden:
        assert bad not in source, f"Cloud dependency found: {bad}"


def test_no_tokens_exposed_in_env_status():
    """_env_status nunca debe devolver valores reales de variables sensibles."""
    with patch.dict(
        os.environ,
        {
            "AURA_API_KEY": "super-secret-token",
            "HF_TOKEN": "hf_abc123",
            "GEMINI_API_KEY": "google-key",
        },
    ):
        result = _env_status()
        for value in result.values():
            assert value in ("set", "missing"), f"Value leak: {value}"
