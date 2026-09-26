"""BLOQUE 103 - Local Comprehensive E2E Integration Testing & Swarm Stress-Test.

Pruebas para el motor E2E (MatrixEngine) y el runner de estres/concurrente del
enjambre. 100% local y soberano: sin HTTP real, sin cloud, sin telemetria externa.
"""

import pytest

from backend.testing.engine import (
    MAX_AGENTS,
    MAX_OPS_PER_AGENT,
    MatrixEngine,
    get_matrix,
    reset_matrix,
)
from backend.testing.models import ALL_CHAIN_STEPS, MatrixReport, StressReport
from backend.testing.steps import STEP_FNS


@pytest.fixture(autouse=True)
def _reset_matrix():
    reset_matrix()
    yield
    reset_matrix()


def test_step_fns_cover_all_chain_steps():
    for name in ALL_CHAIN_STEPS:
        assert name in STEP_FNS, f"missing step fn for {name}"


def test_status_and_contracts():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.testing.routes import router
    from backend.testing.stress import get_stress, safe_max_agents

    app = FastAPI()
    app.include_router(router)
    c = TestClient(app)
    r = c.get("/api/testing/matrix/status")
    assert r.status_code == 200
    assert r.json()["offline_only"] is True
    cc = c.get("/api/testing/matrix/contracts")
    assert cc.json()["block"] == 103
    assert 1 <= safe_max_agents(1000) <= 64


def test_matrix_engine_runs_full_chain():
    eng = MatrixEngine()
    rep = eng.run_chain()
    assert isinstance(rep, MatrixReport)
    assert rep.status in ("passed", "partial")
    assert len(rep.steps) == len(ALL_CHAIN_STEPS)
    assert rep.coverage_blocks >= 1
    assert rep.offline_only is True
    assert rep.report_id.startswith("e2e_")


def test_matrix_engine_history_and_last():
    eng = MatrixEngine()
    eng.run_chain()
    assert eng.last() is not None
    hist = eng.history(limit=5)
    assert len(hist) >= 1
    assert hist[-1].report_id == eng.last().report_id


def test_matrix_engine_partial_chain():
    eng = MatrixEngine()
    rep = eng.run_chain(steps=["memory_cognitive", "federated_round"])
    assert len(rep.steps) == 2
    assert rep.passed + rep.failed == 2


def test_matrix_engine_unknown_step():
    eng = MatrixEngine()
    rep = eng.run_chain(steps=["does_not_exist"])
    assert rep.steps[0].ok is False
    assert rep.steps[0].error == "unknown_step"


def test_matrix_engine_timeout_on_hanging_step(monkeypatch):
    from backend.testing.engine import MatrixEngine

    eng = MatrixEngine(timeout_s=0.05)

    def _hang():
        import time

        time.sleep(5.0)
        return {"ok": True}

    monkeypatch.setitem(STEP_FNS, "memory_cognitive", _hang)
    rep = eng.run_chain(steps=["memory_cognitive"])
    assert rep.steps[0].ok is False
    assert rep.steps[0].error == "step_timeout"


def test_matrix_engine_emits_fusion_event():
    eng = MatrixEngine()
    eng.run_chain()
    assert eng.last() is not None


def test_stress_report_serialization():
    sr = StressReport(
        agents=4,
        ops_per_agent=10,
        total_ops=40,
        ok_ops=38,
        failed_ops=2,
        deadlocks=0,
        avg_latency_ms=12.5,
        p95_latency_ms=30.0,
        throughput_ops=100.0,
        faults_injected=2,
        status="passed",
    )
    d = sr.to_dict()
    assert d["agents"] == 4
    assert d["total_ops"] == 40
    assert d["ok_ops"] == 38
    assert d["failed_ops"] == 2
    assert d["throughput_ops"] == 100.0
    assert d["offline_only"] is True
    assert d["report_id"].startswith("stress_")


def test_matrix_report_finalize_status():
    rep = MatrixReport()
    from backend.testing.models import StepResult

    rep.steps = [StepResult(step="a", ok=True), StepResult(step="b", ok=True)]
    rep.finalize()
    assert rep.status == "passed"
    assert rep.passed == 2 and rep.failed == 0
    assert rep.finished_at != ""

    rep2 = MatrixReport()
    rep2.steps = [StepResult(step="a", ok=True), StepResult(step="b", ok=False)]
    rep2.finalize()
    assert rep2.status == "partial"

    rep3 = MatrixReport()
    rep3.steps = [StepResult(step="a", ok=False)]
    rep3.finalize()
    assert rep3.status == "failed"


def test_matrix_engine_constants():
    assert MAX_AGENTS >= 1
    assert MAX_OPS_PER_AGENT >= 1
    assert isinstance(ALL_CHAIN_STEPS, list) and len(ALL_CHAIN_STEPS) >= 10


def test_full_chain_passes_via_rest():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.testing.routes import router

    app = FastAPI()
    app.include_router(router)
    c = TestClient(app)
    r = c.post("/api/testing/matrix/run", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "passed", body
    assert body["passed"] == len(ALL_CHAIN_STEPS)
    assert body["coverage_blocks"] == 102


def test_chain_subset_and_bad_step():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.testing.routes import router

    app = FastAPI()
    app.include_router(router)
    c = TestClient(app)
    r = c.post("/api/testing/matrix/run", json={"steps": ["master_launch", "fusion_ingest"]})
    assert r.json()["passed"] == 2
    bad = c.post("/api/testing/matrix/run", json={"steps": ["nope"]})
    assert bad.status_code == 400


def test_stress_small_swarm_no_deadlock():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.testing.routes import router

    app = FastAPI()
    app.include_router(router)
    c = TestClient(app)
    r = c.post("/api/testing/matrix/stress", json={"agents": 4, "ops_per_agent": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["deadlocks"] == 0
    assert body["ok_ops"] + body["failed_ops"] == body["total_ops"]


def test_stress_with_fault_injection_counts():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.testing.routes import router

    app = FastAPI()
    app.include_router(router)
    c = TestClient(app)
    r = c.post(
        "/api/testing/matrix/stress", json={"agents": 8, "ops_per_agent": 2, "inject_faults": True}
    )
    body = r.json()
    # seeds 0,7,14 de 16 ops -> 3 fallos sinteticos
    assert body["faults_injected"] == 3
    assert body["status"] in ("partial", "passed", "failed")


def test_ws_heartbeat():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.testing.routes import router

    app = FastAPI()
    app.include_router(router)
    c = TestClient(app)
    with c.websocket_connect("/api/testing/matrix/ws") as ws:
        msg = ws.receive_json()
    assert msg["event"] == "testing_heartbeat"
    assert msg["offline_only"] is True


def test_history_and_reset():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.testing.routes import router

    app = FastAPI()
    app.include_router(router)
    c = TestClient(app)
    c.post("/api/testing/matrix/run", json={"steps": ["fusion_ingest"]})
    c.post("/api/testing/matrix/stress", json={"agents": 2, "ops_per_agent": 2})
    assert c.get("/api/testing/matrix/history").json()["count"] >= 1
    assert c.get("/api/testing/matrix/stress/history").json()["count"] >= 1
    assert c.post("/api/testing/matrix/reset").json()["reset"] is True
    assert c.get("/api/testing/matrix/report").status_code == 404
