"""BLOQUE 66 - Kilo integration tests: /api/automation/watchdog REST + recovery.

Complementa tests/test_block66.py validando:
- endpoints REST de supervision de salud
- checkpoint save/restore via REST
- politicas de reinteto actualizables
- higiene: sin dependencias cloud de monitorizacion (Datadog, New Relic, etc.)
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.automation.watchdog import reset_watchdog, router


@pytest.fixture
def client():
    reset_watchdog()
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        yield c
    reset_watchdog()


def _unique(client, suffix):
    """Run an endpoint with a fresh session_id so state does not leak across tests."""
    import uuid

    sid = f"{suffix}-{uuid.uuid4().hex[:8]}"
    return sid


def test_router_paths():
    paths = [rt.path for rt in router.routes]
    assert router.prefix == "/api/automation/watchdog"
    for p in (
        "/api/automation/watchdog/status",
        "/api/automation/watchdog/start",
        "/api/automation/watchdog/stop",
        "/api/automation/watchdog/track",
        "/api/automation/watchdog/check",
        "/api/automation/watchdog/policy",
        "/api/automation/watchdog/checkpoint",
        "/api/automation/watchdog/checkpoints",
        "/api/automation/watchdog/checkpoints/restore",
        "/api/automation/watchdog/events",
    ):
        assert p in paths, p


def test_status_default(client):
    r = client.get("/api/automation/watchdog/status")
    assert r.status_code == 200
    data = r.json()
    assert data["session_id"] == "default"
    assert data["health"] == "healthy"
    assert data["running"] is False


def test_start_stop(client):
    s = client.post("/api/automation/watchdog/start")
    assert s.status_code == 200
    assert client.get("/api/automation/watchdog/status").json()["running"] is True
    client.post("/api/automation/watchdog/stop")
    assert client.get("/api/automation/watchdog/status").json()["running"] is False


def test_track_and_check(client):
    r = client.post("/api/automation/watchdog/track", json={"pid": 999999})
    assert r.status_code == 200
    chk = client.post("/api/automation/watchdog/check")
    assert chk.status_code == 200
    healths = chk.json()["health"]
    assert any(h["pid"] == 999999 and h["status"] == "crashed" for h in healths)
    events = client.get("/api/automation/watchdog/events").json()["events"]
    assert any(e["kind"] == "process_crash" for e in events)


def test_checkpoint_save_restore(client):
    import uuid

    sid = f"cp-{uuid.uuid4().hex[:8]}"
    r = client.post(
        "/api/automation/watchdog/checkpoint",
        json={
            "task_id": "t1",
            "objective": "test",
            "progress": {"step": 5},
            "active_macros": ["m1"],
        },
        params={"session_id": sid},
    )
    assert r.status_code == 200
    cp = r.json()["checkpoint"]
    assert cp["task_id"] == "t1"
    listed = client.get("/api/automation/watchdog/checkpoints", params={"session_id": sid}).json()[
        "checkpoints"
    ]
    assert len(listed) == 1
    restored = client.get(
        "/api/automation/watchdog/checkpoints/restore", params={"session_id": sid}
    ).json()
    assert restored["checkpoint"]["task_id"] == "t1"
    assert restored["checkpoint"]["progress"]["step"] == 5


def test_policy_update(client):
    r = client.post(
        "/api/automation/watchdog/policy",
        json={
            "inactivity_timeout": 10.0,
            "max_retries": 5,
            "auto_restart": False,
        },
    )
    assert r.status_code == 200
    p = r.json()["policy"]
    assert p["inactivity_timeout"] == 10.0
    assert p["max_retries"] == 5
    assert p["auto_restart"] is False


def test_untrack(client):
    client.post("/api/automation/watchdog/track", json={"pid": 888888})
    r = client.delete("/api/automation/watchdog/track/888888")
    assert r.status_code == 200
    assert client.get("/api/automation/watchdog/status").json()["processes_monitored"] == 0


def test_no_cloud_monitoring_deps():
    import backend.automation.watchdog as mod

    src = open(mod.__file__, encoding="utf-8-sig").read()
    for bad in (
        "datadog",
        "newrelic",
        "new_relic",
        "sentry_sdk",
        "appdynamics",
        "dynatrace",
        "prometheus_client",
        "access_token=",
        "api_key=",
        "secret=",
    ):
        assert bad not in src, f"cloud dep/token found in watchdog: {bad}"
