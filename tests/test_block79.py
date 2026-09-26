"""BLOQUE 79 - Unit tests for Master Orchestrator & Unified Control Engine."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from backend.master_control.master import (
    GlobalEvent,
    MasterConfig,
    MasterOrchestrator,
    get_master_orchestrator,
    reset_master_orchestrator,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_master_orchestrator()
    yield
    reset_master_orchestrator()


def _mk(handlers=None, config=None):
    default = {
        "noop": lambda **kw: {"ok": True},
        "echo": lambda **kw: dict(kw),
        "fail": lambda **kw: (_ for _ in ()).throw(RuntimeError("boom")),
    }
    if handlers:
        default.update(handlers)
    return MasterOrchestrator(config=config, handlers=default)


# ---------- registro y salud de submodulos ----------
def test_register_module_healthy():
    o = _mk()
    o.register_module("rag", lambda: {"collections": 2})
    st = o.module_health("rag")
    assert st.healthy is True and st.details == {"collections": 2}


def test_module_health_failure_graceful():
    o = _mk()

    def bad():
        raise RuntimeError("crashed")

    o.register_module("vision", bad)
    st = o.module_health("vision")
    assert st.healthy is False and "crashed" in st.error


def test_module_not_registered():
    o = _mk()
    st = o.module_health("ghost")
    assert st.healthy is False and st.error == "module not registered"


def test_unregister_module():
    o = _mk()
    o.register_module("a", lambda: {})
    o.unregister_module("a")
    assert "a" not in o.module_names()


# ---------- eventos globales ----------
def test_emit_event_decisions_by_level():
    o = _mk()
    assert o.emit_event("vision", "tick", "info").decision == "acknowledge"
    assert o.emit_event("watchdog", "anomaly", "warn").decision == "monitor"
    assert o.emit_event("watchdog", "failure", "error").decision == "investigate"
    assert o.emit_event("watchdog", "crash", "critical").decision == "escalate"


def test_events_filters():
    o = _mk()
    o.emit_event("rag", "query", "info")
    o.emit_event("mesh", "sync", "warn")
    o.emit_event("mesh", "timeout", "error")
    assert len(o.events(level="warn")) == 1
    assert len(o.events(source="mesh")) == 2
    assert len(o.events(limit=2)) == 2


def test_events_retention_cap():
    cfg = MasterConfig(max_events=10)
    o = _mk(config=cfg)
    for i in range(25):
        o.emit_event("telemetry", "beat", "info", {"i": i})
    assert len(o.events()) <= 10


# ---------- pipelines (misiones compuestas) ----------
def test_pipeline_success_chain():
    o = _mk()
    run = o.run_pipeline(
        "mission",
        [
            {"kind": "noop"},
            {"kind": "echo", "params": {"target": "rag"}},
        ],
    )
    assert run.status == "success"
    assert all(s.status == "success" for s in run.steps)
    assert run.steps[1].result == {"target": "rag"}


def test_pipeline_unknown_kind_fails():
    o = _mk()
    run = o.run_pipeline("bad", [{"kind": "does_not_exist"}])
    assert run.status == "error"
    assert "no handler" in run.error


def test_pipeline_aborts_on_failed_step():
    o = _mk()
    run = o.run_pipeline(
        "broken",
        [
            {"kind": "fail"},
            {"kind": "noop"},
        ],
    )
    assert run.status == "error"
    assert run.steps[0].status == "error"
    assert run.steps[1].status == "pending"  # abortado, no ejecutado


def test_pipeline_custom_handler():
    o = _mk()
    o.register_handler("rag_search", lambda q="": {"hits": [q]})
    run = o.run_pipeline("mission", [{"kind": "rag_search", "params": {"q": "war"}}])
    assert run.status == "success"
    assert run.steps[0].result == {"hits": ["war"]}


# ---------- ciclo maestro ----------
def test_run_cycle_reports_unhealthy():
    o = _mk()
    o.register_module("ok", lambda: {})
    o.register_module("bad", lambda: 1 / 0)
    res = o.run_cycle()
    assert res["unhealthy"] == ["bad"]
    warns = o.events(level="warn")
    assert any(e.kind == "module_unhealthy" for e in warns)


def test_status_snapshot():
    o = _mk()
    o.register_module("m", lambda: {})
    o.emit_event("x", "y", "info")
    o.run_pipeline("p", [{"kind": "noop"}])
    st = o.status()
    assert st["enabled"] is True and st["offline_only"] is True
    assert st["events_total"] == 1 and st["pipelines_total"] == 1
    assert "m" in st["modules_registered"]


# ---------- singleton ----------
def test_singleton_isolation():
    reset_master_orchestrator()
    e1 = get_master_orchestrator()
    e2 = get_master_orchestrator()
    assert e1 is e2
    reset_master_orchestrator()
    e3 = get_master_orchestrator()
    assert e3 is not e1
