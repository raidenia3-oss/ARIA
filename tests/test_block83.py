"""BLOQUE 83 - unit tests for sensory fusion engine (offline)."""

import threading

import pytest

from backend.fusion.sensory import (
    ContextEvaluator,
    FusionEngine,
    SensorEvent,
    SensoryBus,
    get_fusion_engine,
    reset_fusion_engine,
)


def test_event_defaults_and_score():
    e = SensorEvent(source="vision", kind="frame", severity="high")
    assert e.event_id and e.ts > 0
    assert e.score() == pytest.approx(3.0)
    assert e.to_dict()["offline_only"] is True


def test_event_rejects_bad_source():  # noqa
    import pytest as _p

    with _p.raises(ValueError):
        SensorEvent(source="nope")


def test_event_rejects_bad_severity():
    import pytest as _p

    with _p.raises(ValueError):
        SensorEvent(severity="nope")


def test_bus_orders_by_time():
    import time as _t

    now = _t.time()
    b = SensoryBus()
    b.publish(SensorEvent(source="audio", ts=now))
    b.publish(SensorEvent(source="vision", ts=now - 5))
    w = b.window(window_s=3600.0)
    assert [e.source for e in w] == ["vision", "audio"]


def test_bus_subscribe_and_clear():
    b, seen = SensoryBus(), []
    b.subscribe(lambda e: seen.append(e.event_id))
    b.publish(SensorEvent(source="memory"))
    assert len(seen) == 1 and len(b) == 1
    assert b.clear() == 1 and len(b) == 0


def test_evaluator_nominal_empty():
    s = ContextEvaluator().evaluate([])
    assert s.state == "nominal" and s.fused_score == 0


def test_evaluator_alert_and_anomaly():
    ev = ContextEvaluator()
    s1 = ev.evaluate(
        [
            SensorEvent(source="hardware", severity="high"),
            SensorEvent(source="network", severity="high"),
        ]
    )
    assert s1.state == "alert"
    s2 = ev.evaluate([SensorEvent(source="hardware", severity="critical") for _ in range(3)])
    assert s2.state == "anomaly" and s2.anomalies


def test_engine_ingest_snapshot_history():
    eng = FusionEngine()
    eng.ingest("vision", "frame", {"a": 1}, "low")
    eng.ingest("audio", "cmd", {}, "info")
    snap = eng.snapshot()
    assert snap.event_count == 2 and snap.sources == {"vision": 1, "audio": 1}
    assert eng.last() is snap and len(eng.history()) == 1


def test_engine_thread_safety():
    eng = FusionEngine()

    def _w(n):
        for i in range(50):
            eng.ingest("system", f"k-{n}-{i}")

    ts = [threading.Thread(target=_w, args=(n,)) for n in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(eng.bus) == 200
    assert eng.snapshot().event_count == 200


def test_singleton():
    reset_fusion_engine()
    assert get_fusion_engine() is get_fusion_engine()
    reset_fusion_engine()
