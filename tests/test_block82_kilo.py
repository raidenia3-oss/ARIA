"""BLOQUE 82 - REST API tests for Ecosystem Execution endpoints."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.runner.ecosystem import EcosystemRunner
from backend.runner.orchestrator import get_ecosystem_orchestrator, reset_ecosystem_orchestrator
from backend.runner.runner_routes import router


def _noop(kind):
    def _h(directive, step, params):
        return {"scope": kind, "offline": True}

    return _h


@pytest.fixture(autouse=True)
def _reset():
    reset_ecosystem_orchestrator()
    yield
    reset_ecosystem_orchestrator()


@pytest.fixture
def client(tmp_path):
    orch = get_ecosystem_orchestrator()
    for s in EcosystemRunner.SUPPORTED_SCOPES:
        orch.runner.register_handler(s, _noop(s))
    app = FastAPI(title="AURA Ecosystem Test", version="test")
    app.include_router(router)
    with TestClient(app) as c:
        yield c


def test_status(client):
    r = client.get("/api/ecosystem/status")
    assert r.status_code == 200
    d = r.json()
    assert d["online"] is True
    assert d["offline_only"] is True
    assert "rag" in d["supported_scopes"]


def test_scopes(client):
    r = client.get("/api/ecosystem/scopes")
    assert r.status_code == 200
    assert set(r.json()["scopes"]) == set(EcosystemRunner.SUPPORTED_SCOPES)


def test_execute_foreground(client):
    r = client.post(
        "/api/ecosystem/execute",
        json={
            "mission_id": "e1",
            "title": "Recon offline",
            "description": "d",
            "scopes": ["rag", "audit"],
        },
    )
    assert r.status_code == 200
    d = r.json()
    assert d["mission_id"] == "e1"
    assert d["status"] == "success"
    assert d["summary"]["completed_steps"] == 2


def test_execute_defaults_scopes(client):
    r = client.post("/api/ecosystem/execute", json={"description": "sin scopes"})
    assert r.status_code == 200
    d = r.json()
    assert d["summary"]["total_steps"] >= 1


def test_execute_background(client):
    r = client.post(
        "/api/ecosystem/execute",
        json={
            "mission_id": "e2",
            "title": "t",
            "description": "d",
            "scopes": ["rag", "memory"],
            "background": True,
        },
    )
    assert r.status_code == 200
    d = r.json()
    assert d["background"] is True
    assert d["task_id"]


def test_mission_detail_and_history(client):
    client.post(
        "/api/ecosystem/execute",
        json={"mission_id": "e3", "title": "t", "description": "d", "scopes": ["audit"]},
    )
    r1 = client.get("/api/ecosystem/missions/e3")
    assert r1.status_code == 200
    assert r1.json()["mission_id"] == "e3"
    r2 = client.get("/api/ecosystem/history")
    assert r2.status_code == 200
    assert r2.json()["count"] >= 1


def test_mission_detail_not_found(client):
    r = client.get("/api/ecosystem/missions/nope")
    assert r.status_code == 404


def test_interrupt(client):
    res = client.post(
        "/api/ecosystem/execute",
        json={
            "mission_id": "e4",
            "title": "t",
            "description": "d",
            "scopes": ["rag"],
            "background": True,
        },
    )
    tid = res.json()["task_id"]
    r = client.post(f"/api/ecosystem/interrupt/{tid}")
    assert r.status_code == 200
    assert r.json()["interrupted"] is True


def test_history_limit(client):
    for i in range(3):
        client.post(
            "/api/ecosystem/execute",
            json={"mission_id": f"e{i}", "title": "t", "description": "d", "scopes": ["audit"]},
        )
    r = client.get("/api/ecosystem/history", params={"limit": 2})
    assert r.status_code == 200
    assert r.json()["count"] == 2
