"""BLOQUE 99 - unit tests for local simulation, stress-testing & infinite horizon optimization."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.simulation.engine import (
    FAULT_TYPES,
    InfiniteHorizonOptimizer,
    ScenarioConfig,
    SimulationEngine,
    SyntheticSimulator,
    get_engine,
    reset_engine,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_engine()
    yield
    reset_engine()


# ---------------------------------------------------------------- simulator ----


def test_scenario_deterministic_same_seed():
    sim = SyntheticSimulator()
    cfg = ScenarioConfig(seed=123, steps=50, faults=[{"type": "p2p_partition", "step": 10}])
    r1 = sim.run(cfg)
    r2 = sim.run(cfg)
    assert r1.consensus_accuracy == r2.consensus_accuracy
    assert r1.recovery_time_ms == r2.recovery_time_ms


def test_fault_injection_counts():
    sim = SyntheticSimulator()
    cfg = ScenarioConfig(
        steps=100,
        faults=[
            {"type": "p2p_partition", "step": 10},
            {"type": "memory_spike", "step": 50},
        ],
    )
    r = sim.run(cfg)
    assert r.faults_injected == 2
    assert 0.0 <= r.resilience <= 1.0
    assert r.consensus_accuracy > 0.0


def test_invalid_fault_type_ignored():
    sim = SyntheticSimulator()
    cfg = ScenarioConfig(steps=10, faults=[{"type": "alien_fault", "step": 5}])
    r = sim.run(cfg)
    assert r.faults_injected == 0


def test_config_clamping():
    cfg = ScenarioConfig(agents=99999, steps=999999, replication_rate=5.0, gamma=2.0)
    assert cfg.agents == 512 and cfg.steps == 100_000
    assert cfg.replication_rate == 1.0 and cfg.gamma <= 0.999


# ------------------------------------------------------------ stress suite ----


def test_stress_suite_covers_all_fault_types():
    eng = SimulationEngine()
    rep = eng.stress_suite(agents=8, seed=5)
    assert len(rep["scenarios"]) == len(FAULT_TYPES)
    assert rep["worst_resilience"] >= 0.0
    assert set(rep["fault_types"]) == set(FAULT_TYPES)


def test_higher_replication_improves_resilience():
    sim = SyntheticSimulator()
    weak = sim.run(
        ScenarioConfig(
            seed=7,
            steps=100,
            replication_rate=0.0,
            faults=[{"type": "agent_saturation", "step": 30}],
        )
    )
    strong = sim.run(
        ScenarioConfig(
            seed=7,
            steps=100,
            replication_rate=0.9,
            faults=[{"type": "agent_saturation", "step": 30}],
        )
    )
    assert strong.resilience >= weak.resilience


def test_engine_records_results():
    eng = SimulationEngine()
    eng.run_scenario(ScenarioConfig())
    eng.run_scenario(ScenarioConfig())
    assert eng.status()["scenarios_run"] == 2
    eng.reset()
    assert eng.status()["scenarios_run"] == 0


# --------------------------------------------------------------- optimizer ----


def test_optimizer_converges():
    opt = InfiniteHorizonOptimizer(max_iterations=100)
    rep = opt.optimize()
    assert rep["converged"] is True
    assert 0.0 <= rep["policy"] <= 1.0
    assert rep["iterations"] > 0


def test_optimizer_return_is_discounted_and_finite():
    opt = InfiniteHorizonOptimizer(gamma=0.9)
    rep = opt.optimize(iterations=5)
    vals = [h["discounted_return"] for h in rep["history"]]
    assert all(v == v and abs(v) != float("inf") for v in vals)  # finite
    assert rep["gamma"] == 0.9


def test_optimizer_reset():
    opt = InfiniteHorizonOptimizer()
    opt.optimize(iterations=10)
    opt.reset()
    assert opt.status()["history_len"] == 0
    assert opt.converged is False


# ------------------------------------------------------------ REST / WS -------


def _client() -> TestClient:
    app = FastAPI()
    from backend.simulation.routes import router

    app.include_router(router)
    return TestClient(app)


def test_rest_scenario_endpoint():
    c = _client()
    resp = c.post("/api/simulation/infinite/scenario", json={"agents": 4, "steps": 20})
    assert resp.status_code == 200
    d = resp.json()
    assert d["status"] == "completed"
    assert d["config"]["agents"] == 4


def test_rest_stress_and_status_and_reset():
    c = _client()
    assert c.post("/api/simulation/infinite/stress", json={"agents": 4}).status_code == 200
    st = c.get("/api/simulation/infinite/status").json()
    assert st["scenarios_run"] == 4 and st["offline_only"] is True
    res = c.get("/api/simulation/infinite/results").json()
    assert res["count"] == 4
    assert c.post("/api/simulation/infinite/reset").json()["reset"] is True


def test_rest_optimize_endpoint():
    c = _client()
    resp = c.post("/api/simulation/infinite/optimize", json={"iterations": 20})
    assert resp.status_code == 200
    d = resp.json()
    assert d["offline_only"] is True
    assert "converged" in d


def test_rest_scenario_validation_rejects_bad_input():
    c = _client()
    assert c.post("/api/simulation/infinite/scenario", json={"agents": 0}).status_code == 422
    assert c.post("/api/simulation/infinite/scenario", json={"steps": 0}).status_code == 422


def test_ws_simulation_heartbeat():
    c = _client()
    with c.websocket_connect("/api/simulation/infinite/ws") as ws:
        msg = ws.receive_json()
    assert msg["event"] == "heartbeat"
    assert msg["offline_only"] is True
    assert "scenarios_run" in msg["status"]


def test_singleton_engine():
    assert get_engine() is get_engine()
