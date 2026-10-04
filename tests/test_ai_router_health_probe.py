"""Gate C5 — el router sondea la salud UNA vez y no reintenta providers caidos
en cada request.

Antes, si un provider local estaba caido (jan:1337, Ollama apagado) el router
lo intentaba en CADA request: un timeout garantizado por llamada. La salud se
mide una vez (conexion TCP), se cachea, y los caidos se excluyen del orden.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from backend import ai_router as mod


def _reset_health() -> None:
    mod.AIRouter._health_cache = {}
    mod.AIRouter._health_probed_at = 0.0
    mod.AIRouter._health_source = "unavailable"


@pytest.fixture(autouse=True)
def _clean_health_cache():
    _reset_health()
    yield
    _reset_health()


def _router(tmp_path) -> mod.AIRouter:
    return mod.AIRouter(state_file=str(tmp_path / "state.json"))


def test_dead_provider_is_excluded_from_order(tmp_path, monkeypatch):
    router = _router(tmp_path)
    monkeypatch.setattr(router, "_probe_provider", lambda p: p.name != "jan")
    router.probe_once(force=True)
    names = {p.name for p in router._get_provider_order()}
    assert "jan" not in names, "un provider caido sigue en el orden"


def test_health_is_probed_once_not_per_call(tmp_path, monkeypatch):
    router = _router(tmp_path)
    calls = {"n": 0}

    def _fake_probe(p):
        calls["n"] += 1
        return True

    monkeypatch.setattr(router, "_probe_provider", _fake_probe)
    router.probe_once(force=True)
    after_probe = calls["n"]
    assert after_probe == len(router.providers) and after_probe > 0

    for _ in range(5):
        router._get_provider_order()
    assert calls["n"] == after_probe, "el router sono la salud por request"


def test_probe_within_ttl_is_not_repeated(tmp_path, monkeypatch):
    router = _router(tmp_path)
    monkeypatch.setattr(router, "_probe_provider", lambda p: True)
    router.probe_once(force=True)
    probed_at = mod.AIRouter._health_probed_at
    router.probe_once()  # dentro del TTL -> cache
    assert mod.AIRouter._health_probed_at == probed_at


def test_snapshot_reports_measured_source(tmp_path, monkeypatch):
    router = _router(tmp_path)
    monkeypatch.setattr(router, "_probe_provider", lambda p: True)
    snap = router.health_snapshot()
    assert snap["data_source"] == "measured"
    assert set(snap["providers"]) == set(router.providers)
