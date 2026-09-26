"""BLOQUE 104 - Local Final Sovereign System Lock-In, Smoke-Test Hardshell
& Production-Ready Daemon Verification.

Pruebas para el motor de bloqueo soberano final (SovereignLockEngine) y el
hardshell de pruebas de humo (SmokeHardshell). 100% local y soberano.
"""

import pytest

from backend.testing.sovereign_lock import (
    PRODUCTION_PORTS,
    REQUIRED_MODULES,
    LockReport,
    LockStatus,
    PortProbe,
    SmokeHardshell,
    SmokeResult,
    SovereignLockEngine,
    get_sovereign_lock,
    reset_sovereign_lock,
)


@pytest.fixture(autouse=True)
def _reset_lock():
    reset_sovereign_lock()
    yield
    reset_sovereign_lock()


def test_constants():
    assert PRODUCTION_PORTS
    assert len(PRODUCTION_PORTS) >= 1
    assert 8000 in PRODUCTION_PORTS
    assert len(REQUIRED_MODULES) >= 20
    assert "backend.main" in REQUIRED_MODULES
    assert "backend.ai.federated" in REQUIRED_MODULES
    assert "backend.ai.fine_tuning" in REQUIRED_MODULES
    assert "backend.testing.engine" in REQUIRED_MODULES


def test_smoke_hardshell_runs():
    sh = SmokeHardshell()
    rep = sh.run()
    assert isinstance(rep, SmokeResult)
    assert rep.report_id.startswith("smoke_")
    assert len(rep.ports) == len(PRODUCTION_PORTS)
    assert len(rep.modules) == len(REQUIRED_MODULES)
    assert rep.env_local_sha256
    assert rep.runtime_signature
    assert rep.status in ("passed", "degraded", "failed")
    assert rep.offline_only is True
    assert rep.finished_at > 0


def test_smoke_hardshell_last():
    sh = SmokeHardshell()
    assert sh.last() is None
    sh.run()
    assert sh.last() is not None


def test_smoke_result_finalize():
    rep = SmokeResult()
    rep.ports = [PortProbe(port=8000, alive=True), PortProbe(port=8080, alive=False)]
    rep.modules = []
    rep.finalize()
    assert rep.ports_ok == 1
    assert rep.ports_fail == 1
    assert rep.finished_at > 0


def test_lock_engine_initial_state():
    eng = SovereignLockEngine()
    st = eng.status()
    assert st["status"] == LockStatus.UNLOCKED.value
    assert st["sovereign_ready"] is False
    assert st["offline_only"] is True


def test_lock_engine_lock_and_verify():
    eng = SovereignLockEngine()
    rep = eng.lock()
    assert isinstance(rep, dict)
    assert rep["status"] in (LockStatus.LOCKED.value, LockStatus.FAILED.value)
    st = eng.status()
    assert st["status"] in (LockStatus.LOCKED.value, LockStatus.FAILED.value)
    v = eng.verify()
    assert "verified" in v
    assert "signature_match" in v
    assert v["offline_only"] is True


def test_lock_rest_contracts_daemons_audit104_ws():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.testing.sovereign_lock import reset_sovereign_lock, router

    reset_sovereign_lock()
    app = FastAPI()
    app.include_router(router)
    c = TestClient(app)
    assert c.get("/api/core/sovereign-lock/status").status_code == 200
    cc = c.get("/api/core/sovereign-lock/contracts")
    assert cc.status_code == 200 and cc.json()["block"] == 104
    d = c.get("/api/core/sovereign-lock/daemons")
    assert d.status_code == 200
    body = d.json()
    assert body["daemons_total"] == 4
    assert "cold_boot_ms" in body and "warm_boot_ms" in body
    names = {x["name"] for x in body["daemons"]}
    assert {"daemon_orchestrator", "vector_memory", "event_queue", "p2p_channel"} <= names
    a = c.get("/api/core/sovereign-lock/audit104")
    assert a.status_code == 200
    assert a.json()["blocks_total"] == 104
    assert a.json()["offline_only"] is True
    with c.websocket_connect("/api/core/sovereign-lock/ws") as ws:
        msg = ws.receive_json()
    assert msg["type"] == "connected"
    assert msg["offline_only"] is True
    reset_sovereign_lock()


def test_lock_engine_unlock():
    eng = SovereignLockEngine()
    eng.lock()
    rep = eng.unlock()
    assert rep["status"] == LockStatus.UNLOCKED.value
    st = eng.status()
    assert st["status"] == LockStatus.UNLOCKED.value


def test_lock_engine_double_lock_idempotent():
    eng = SovereignLockEngine()
    r1 = eng.lock()
    # Second call must not crash and must return a valid lock report.
    r2 = eng.lock()
    assert "report_id" in r1 and r1["report_id"].startswith("lock_")
    assert "report_id" in r2 and r2["report_id"].startswith("lock_")
    assert r1["status"] == r2["status"]


def test_lock_engine_smoke_and_module_audit():
    eng = SovereignLockEngine()
    smoke = eng.smoke_test()
    assert "ports" in smoke and "modules" in smoke
    mods = eng.module_audit()
    assert mods["modules_total"] == len(REQUIRED_MODULES)
    ports = eng.port_audit()
    assert ports["ports_total"] == len(PRODUCTION_PORTS)


def test_lock_report_serialization():
    lr = LockReport(
        status=LockStatus.LOCKED,
        modules_total=30,
        modules_ok=28,
        smoke_passed=True,
        e2e_passed=True,
        e2e_report_id="e2e_abc",
        hardening_checks=10,
        hardening_passed=9,
    )
    d = lr.to_dict()
    assert d["status"] == "locked"
    assert d["modules_total"] == 30
    assert d["modules_ok"] == 28
    assert d["smoke_passed"] is True
    assert d["e2e_passed"] is True
    assert d["e2e_report_id"] == "e2e_abc"
    assert d["immutable"] is True
    assert d["offline_only"] is True
    assert d["report_id"].startswith("lock_")


def test_get_sovereign_lock_singleton():
    a = get_sovereign_lock()
    b = get_sovereign_lock()
    assert a is b
