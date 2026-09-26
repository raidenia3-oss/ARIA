"""BLOQUE 76 - REST integration tests for Memory Inspector endpoints."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def _reset():
    from backend.automation.memory_injector import reset_memory_inspector

    reset_memory_inspector()
    yield
    reset_memory_inspector()


@pytest.fixture
def client():
    from backend.automation.memory_injector import reset_memory_inspector

    reset_memory_inspector()
    app = FastAPI(title="AURA Memory Test", version="test")
    from backend.automation.memory_routes import router as memory_router

    app.include_router(memory_router)
    with TestClient(app) as c:
        yield c
    reset_memory_inspector()


def test_status(client):
    r = client.get("/api/automation/memory/status")
    assert r.status_code == 200
    body = r.json()
    assert body["backend"] == "InMemoryBackend"
    assert "authorized" in body


def test_processes(client):
    r = client.get("/api/automation/memory/processes")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_authorize_and_revoke(client):
    r = client.post("/api/automation/memory/authorize", json={"pid": 123})
    assert r.status_code == 200
    assert 123 in r.json()["authorized"]["pids"]
    r = client.post("/api/automation/memory/revoke", json={"pid": 123})
    assert r.status_code == 200
    assert 123 not in r.json()["authorized"]["pids"]


def test_scan_unauthorized(client):
    r = client.post("/api/automation/memory/scan", json={"pid": 999, "pattern": "DE AD"})
    assert r.status_code == 403


def test_read_unauthorized(client):
    r = client.post("/api/automation/memory/read", json={"pid": 999, "address": 0x1000})
    assert r.status_code == 403


def test_write_unauthorized(client):
    r = client.post(
        "/api/automation/memory/write", json={"pid": 999, "address": 0x1000, "value": 1}
    )
    assert r.status_code == 403


def test_watchpoint_unauthorized(client):
    r = client.post("/api/automation/memory/watchpoint", json={"pid": 999, "address": 0x1000})
    assert r.status_code == 403


def test_watchpoints_empty(client):
    r = client.get("/api/automation/memory/watchpoints")
    assert r.status_code == 200
    assert r.json() == []


def test_watchpoints_start_stop(client):
    r = client.post("/api/automation/memory/watchpoints/start")
    assert r.status_code == 200
    r = client.post("/api/automation/memory/watchpoints/stop")
    assert r.status_code == 200


def test_delete_missing_watchpoint(client):
    r = client.delete("/api/automation/memory/watchpoint/99999")
    assert r.status_code == 200
    assert r.json()["ok"] is False
