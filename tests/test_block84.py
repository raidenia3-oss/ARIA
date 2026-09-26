"""BLOQUE 84 - unit tests for predictive intent engine (offline)."""

from backend.predictive.intent import (
    AUTO_THRESHOLD,
    CONFIRM_THRESHOLD,
    IntentAnalyzer,
    IntentHypothesis,
    PredictiveEngine,
    ProactiveTask,
    TaskGatekeeper,
    get_predictive_engine,
    reset_predictive_engine,
)


def test_thresholds_sane():
    assert 0 < CONFIRM_THRESHOLD < AUTO_THRESHOLD < 1.0


def test_analyzer_empty():
    assert IntentAnalyzer().analyze({}, 0.0) == []


def test_analyzer_detects_rag():
    hs = IntentAnalyzer().analyze({"memory": 6, "network": 4}, 8.0, "alert")
    kinds = [h.intent for h in hs]
    assert "rag_precache" in kinds
    assert all(h.confidence >= CONFIRM_THRESHOLD for h in hs)


def test_analyzer_ignores_weak():
    hs = IntentAnalyzer().analyze(
        {"vision": 1, "audio": 1, "memory": 1, "network": 1, "hardware": 1, "system": 1},
        0.0,
        "nominal",
    )
    assert hs == []


def test_gatekeeper_high_impact_needs_confirm():
    g = TaskGatekeeper()
    h = IntentHypothesis(intent="x", confidence=0.99, suggested_action="run:x", impact="high")
    assert g.decide(h) == "needs_confirm"


def test_gatekeeper_auto_vs_confirm():
    g = TaskGatekeeper()
    hi = IntentHypothesis(intent="a", confidence=0.9, suggested_action="run:a", impact="low")
    lo = IntentHypothesis(intent="b", confidence=0.6, suggested_action="run:b", impact="low")
    assert g.decide(hi) == "auto" and g.decide(lo) == "needs_confirm"


def test_gatekeeper_executes_registered():
    g = TaskGatekeeper()
    g.register_handler("run:a", lambda hypothesis_id: {"ok": True, "offline": True})
    t = ProactiveTask(action="run:a", impact="low")
    g.execute(t)
    assert t.status == "success" and t.result == {"ok": True, "offline": True}


def test_gatekeeper_error_captured():
    g = TaskGatekeeper()

    def _boom(hypothesis_id):
        raise RuntimeError("boom")

    g.register_handler("run:b", _boom)
    t = ProactiveTask(action="run:b", impact="low")
    g.execute(t)
    assert t.status == "error" and "boom" in t.result["error"]


def test_engine_observe_schedules_low_impact():
    eng = PredictiveEngine()
    out = eng.observe({"memory": 5, "network": 5}, 9.0, "anomaly")
    assert out["offline_only"] is True
    assert any(t["status"] == "success" for t in out["auto_scheduled"])


def test_engine_confirm_flow():
    eng = PredictiveEngine()
    out = eng.observe({"network": 4, "system": 1}, 2.0, "active")
    assert out["pending_confirm"], "se esperaba hipotesis pendiente"
    hid = out["pending_confirm"][0]["hypothesis_id"]
    r = eng.confirm(hid)
    assert r["confirmed"] is True and r["task"]["status"] == "success"
    assert eng.confirm("nope")["confirmed"] is False


def test_singleton():
    reset_predictive_engine()
    assert get_predictive_engine() is get_predictive_engine()
    reset_predictive_engine()
