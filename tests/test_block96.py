"""BLOQUE 96 - unit tests for self-healing engine."""

import os

import pytest

from backend.resilience.self_healing import (
    FaultDetector,
    FaultEvent,
    RemediationAction,
    RemediationController,
    SelfHealingEngine,
    get_self_healing_engine,
    reset_self_healing_engine,
)


@pytest.fixture(autouse=True)
def _clean():
    for f in ["data/resilience/healing_log.jsonl", "data/resilience/thresholds.json"]:
        if os.path.exists(f):
            os.remove(f)
    reset_self_healing_engine()
    yield
    reset_self_healing_engine()


def test_detector_scan_no_faults():
    d = FaultDetector()
    faults = d.scan()
    assert isinstance(faults, list)


def test_detector_update_thresholds():
    d = FaultDetector()
    t = d.update_thresholds({"memory_mb": 1.0})
    assert t["memory_mb"] == 1.0


def test_remediation_gc_collect():
    r = RemediationController()
    f = FaultEvent(
        event_id="f1", kind="memory_pressure", severity="warning", detail="test", memory_mb=999.0
    )
    a = r.remediate(f)
    assert a.action == "gc_collect"
    assert a.status == "ok"


def test_remediation_cooldown():
    r = RemediationController()
    r._cooldown = 10.0
    r._last_action_ts = __import__("time").time()
    assert r.can_act() is False
    assert r.cooldown_remaining() > 0


def test_inject_fault_triggers_remediation():
    e = SelfHealingEngine(auto_heal=True)
    e.remediator._cooldown = 0.0
    e.remediator._last_action_ts = 0.0
    events = []
    e.on_event(lambda p: events.append(p))
    f = e.inject_fault("memory_pressure", detail="test", severity="warning")
    assert f.kind == "memory_pressure"
    assert any(p.get("type") == "fault_detected" for p in events)
    assert any(p.get("type") == "remediation_applied" for p in events)


def test_inject_fault_no_auto_heal():
    e = SelfHealingEngine(auto_heal=False)
    f = e.inject_fault("cpu_saturation", detail="x")
    assert len(e.actions()) == 0


def test_force_remediate_unknown():
    e = SelfHealingEngine()
    a = e.force_remediate("bogus_action")
    assert a.status == "error"


def test_force_remediate_gc():
    e = SelfHealingEngine()
    a = e.force_remediate("gc_collect", detail="manual")
    assert a.action == "gc_collect"
    assert a.status == "ok"


def test_thresholds_roundtrip():
    e = SelfHealingEngine()
    t = e.update_thresholds({"cpu_percent": 50.0})
    assert t["cpu_percent"] == 50.0
    assert e.thresholds()["cpu_percent"] == 50.0


def test_status_fields():
    e = SelfHealingEngine()
    s = e.status()
    assert "auto_heal" in s
    assert "faults_total" in s
    assert "actions_total" in s
    assert s["offline_only"] is True


def test_singleton():
    a = get_self_healing_engine()
    b = get_self_healing_engine()
    assert a is b


def test_reset_clears_state():
    e = get_self_healing_engine()
    e.inject_fault("memory_pressure")
    assert e.status()["faults_total"] >= 1
    e.reset()
    assert e.status()["faults_total"] == 0
