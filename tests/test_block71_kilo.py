"""BLOQUE 71 - REST API tests for governor endpoints."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.telemetry.governor import (
    GovernorEngine,
    GovernorThresholds,
    WorkloadItem,
    reset_governor,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_governor()
    yield
    reset_governor()


def test_get_resources():
    with TestClient(app) as c:
        r = c.get("/api/telemetry/resources")
        assert r.status_code == 200
        d = r.json()
        assert "cpu_percent" in d
        assert "ram_percent" in d


def test_workload_crud():
    with TestClient(app) as c:
        r = c.post(
            "/api/telemetry/workloads", json={"workload_id": "w1", "name": "test", "priority": 3}
        )
        assert r.status_code == 200
        assert r.json()["registered"] == "w1"
        r = c.get("/api/telemetry/workloads")
        assert r.status_code == 200
        assert len(r.json()["workloads"]) == 1
        r = c.delete("/api/telemetry/workloads/w1")
        assert r.status_code == 200
        r = c.get("/api/telemetry/workloads")
        assert len(r.json()["workloads"]) == 0


def test_evaluate():
    with TestClient(app) as c:
        r = c.post("/api/telemetry/evaluate")
        assert r.status_code == 200
        d = r.json()
        assert "decision" in d
        assert "action" in d


def test_status():
    with TestClient(app) as c:
        r = c.get("/api/telemetry/status")
        assert r.status_code == 200
        d = r.json()
        assert d["enabled"] is True
        assert "workloads" in d


def test_thresholds_update():
    with TestClient(app) as c:
        r = c.get("/api/telemetry/thresholds")
        assert r.status_code == 200
        r = c.put("/api/telemetry/thresholds", json={"cpu_warn": 50.0})
        assert r.status_code == 200
        r = c.get("/api/telemetry/thresholds")
        assert r.json()["cpu_warn"] == 50.0


def test_decisions():
    with TestClient(app) as c:
        c.post("/api/telemetry/evaluate")
        c.post("/api/telemetry/evaluate")
        r = c.get("/api/telemetry/decisions")
        assert r.status_code == 200
        assert r.json()["count"] >= 1
