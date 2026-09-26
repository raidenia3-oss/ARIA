"""BLOQUE 100 - E2E tests for the sovereign omni-agent master runtime & unified gateway."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core.aura_master_runtime import (
    ENGINE_PROBES,
    LIFECYCLE_STATES,
    TOTAL_BLOCKS,
    MasterRuntimeEngine,
    get_master_runtime,
    reset_master_runtime,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_master_runtime()
    yield
    reset_master_runtime()


def _client() -> TestClient:
    app = FastAPI()
    from backend.core.aura_master_runtime import router

    app.include_router(router)
    return TestClient(app)


# ------------------------------------------------------------ engine core -----


def test_initial_state_is_cold():
    rt = get_master_runtime()
    assert rt.status()["state"] == "cold"
    assert rt.status()["session_id"] is None
    assert TOTAL_BLOCKS == 100


def test_launch_sets_ready_and_session():
    rt = MasterRuntimeEngine()
    rep = rt.launch()
    assert rep["launched"] is True
    assert rep["state"] == "ready"
    assert rep["session_id"].startswith("msr_")
    assert rep["total_blocks"] == 100
    assert rt.status()["state"] == "ready"


def test_launch_idempotent():
    rt = MasterRuntimeEngine()
    r1 = rt.launch()
    r2 = rt.launch()
    assert r2.get("already") is True
    assert r2["session_id"] == r1["session_id"]


def test_degraded_state_when_engine_fails():
    rt = MasterRuntimeEngine()
    rt.register_engine("broken", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    rep = rt.launch()
    assert rep["state"] == "degraded" and rep["launched"] is True


def test_cold_when_no_engines_ok():
    rt = MasterRuntimeEngine()
    rt.register_engine("broken", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    # sustituye probes reales por uno roto: vacia la lista global en copia local
    import backend.core.aura_master_runtime as mod

    saved = mod.ENGINE_PROBES
    mod.ENGINE_PROBES = []
    try:
        rep = rt.launch()
    finally:
        mod.ENGINE_PROBES = saved
    assert rep["state"] == "cold" and rep["launched"] is False


def test_shutdown_and_relaunch():
    rt = MasterRuntimeEngine()
    rt.launch()
    sd = rt.shutdown()
    assert sd["shutdown"] is True and sd["state"] == "stopped"
    assert rt.status()["session_id"] is None


def test_heartbeat_increments():
    rt = MasterRuntimeEngine()
    b1 = rt.heartbeat()
    b2 = rt.heartbeat()
    assert b2["beat"] == b1["beat"] + 1
    assert rt.status()["heartbeat_count"] == 2


def test_probe_engines_tolerates_failures():
    rt = MasterRuntimeEngine()
    rt.register_engine("broken", lambda: (_ for _ in ()).throw(RuntimeError("e")))
    p = rt.probe_engines()
    assert p["engines_ok"] == p["engines_total"] - 1
    assert any(e.get("error") == "e" for e in p["engines"])


def test_singleton_and_reset():
    assert get_master_runtime() is get_master_runtime()
    get_master_runtime().launch()
    reset_master_runtime()
    assert get_master_runtime().status()["state"] == "cold"


def test_real_probes_registered():
    assert len(ENGINE_PROBES) == 4
    p = MasterRuntimeEngine().probe_engines()
    names = {e["engine"] for e in p["engines"]}
    assert {"refactoring", "planner", "sovereign_bootstrapper", "simulation"} <= names


# ------------------------------------------------------------ E2E REST/WS -----


def test_e2e_full_lifecycle_rest():
    c = _client()
    st = c.get("/api/aura/master/status").json()
    assert st["state"] == "cold"
    launch = c.post("/api/aura/master/launch").json()
    assert launch["launched"] is True
    eco = c.get("/api/aura/master/ecosystem").json()
    assert eco["total_blocks"] == 100 and eco["offline_only"] is True
    assert eco["engines_ok"] >= 3
    met = c.get("/api/aura/master/metrics").json()
    assert met["state"] in ("ready", "degraded")
    assert c.post("/api/aura/master/shutdown").json()["shutdown"] is True
    assert c.post("/api/aura/master/reset").json()["reset"] is True


def test_e2e_ws_master_heartbeat():
    c = _client()
    with c.websocket_connect("/api/aura/master/ws") as ws:
        msg = ws.receive_json()
    assert msg["event"] == "master_heartbeat"
    assert msg["offline_only"] is True
    assert "state" in msg and "beat" in msg


def test_e2e_validation_endpoint_unauthorized_path():
    c = _client()
    # contratos existentes intactos: rutas desconocidas -> 404 (no 500)
    assert c.get("/api/aura/master/unknown").status_code == 404
