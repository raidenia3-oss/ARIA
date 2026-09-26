"""BLOQUE 96 - REST + WS tests para /api/resilience/healing."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.resilience.healing_routes import reset_self_healing_engine, router


@pytest.fixture(autouse=True)
def _clean():
    reset_self_healing_engine()
    yield
    reset_self_healing_engine()


@pytest.fixture
def client():
    app = FastAPI(title="AURA Healing Test", version="test")
    app.include_router(router)
    with TestClient(app) as c:
        yield c


def test_status(client):
    r = client.get("/api/resilience/healing/status")
    assert r.status_code == 200
    data = r.json()
    assert data["offline_only"] is True
    assert "faults_total" in data


def test_scan(client):
    r = client.post("/api/resilience/healing/scan")
    assert r.status_code == 200
    assert "faults" in r.json()


def test_inject_fault(client):
    r = client.post(
        "/api/resilience/healing/faults/inject",
        json={"kind": "memory_pressure", "detail": "test", "severity": "warning"},
    )
    assert r.status_code == 200
    assert r.json()["kind"] == "memory_pressure"


def test_faults_list(client):
    client.post("/api/resilience/healing/faults/inject", json={"kind": "cpu_saturation"})
    r = client.get("/api/resilience/healing/faults")
    assert r.json()["count"] >= 1


def test_actions_list(client):
    client.post("/api/resilience/healing/faults/inject", json={"kind": "memory_pressure"})
    r = client.post(
        "/api/resilience/healing/remediate", json={"action": "gc_collect", "detail": "manual"}
    )
    assert r.json()["status"] == "ok"
    r = client.get("/api/resilience/healing/actions")
    assert r.json()["count"] >= 1


def test_thresholds(client):
    r = client.get("/api/resilience/healing/thresholds")
    assert "thresholds" in r.json()
    r = client.post(
        "/api/resilience/healing/thresholds", json={"thresholds": {"cpu_percent": 42.0}}
    )
    assert r.json()["thresholds"]["cpu_percent"] == 42.0


def test_reset(client):
    client.post("/api/resilience/healing/faults/inject", json={"kind": "memory_pressure"})
    r = client.post("/api/resilience/healing/reset")
    assert r.json()["reset"] is True
    r = client.get("/api/resilience/healing/status")
    assert r.json()["faults_total"] == 0
