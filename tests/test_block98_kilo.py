"""BLOQUE 98 - REST + WS tests for /api/core/sovereign-boot."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core.sovereign_bootstrapper import reset_sovereign_bootstrapper, router


@pytest.fixture(autouse=True)
def _clean():
    reset_sovereign_bootstrapper()
    yield
    reset_sovereign_bootstrapper()


@pytest.fixture
def client():
    app = FastAPI(title="AURA Sovereign Boot Test", version="test")
    app.include_router(router)
    with TestClient(app) as c:
        yield c


def test_status(client):
    r = client.get("/api/core/sovereign-boot/status")
    assert r.status_code == 200
    data = r.json()
    assert data["offline_only"] is True
    assert "hardening" in data
    assert "health" in data


def test_snapshot(client):
    r = client.get("/api/core/sovereign-boot/snapshot")
    assert r.status_code == 200
    assert r.json()["offline_only"] is True


def test_boot(client):
    r = client.post("/api/core/sovereign-boot/boot", json={"force": True})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    assert data["booted"] is True
    assert data["offline_only"] is True


def test_audits(client):
    client.post("/api/core/sovereign-boot/boot", json={})
    r = client.get("/api/core/sovereign-boot/audits")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] >= 8
    assert data["offline_only"] is True


def test_events(client):
    client.post("/api/core/sovereign-boot/boot", json={})
    r = client.get("/api/core/sovereign-boot/events")
    assert r.status_code == 200
    assert r.json()["count"] >= 1


def test_hardening_get(client):
    r = client.get("/api/core/sovereign-boot/hardening")
    assert r.status_code == 200
    assert r.json()["offline_only"] is True


def test_hardening_set(client):
    r = client.post("/api/core/sovereign-boot/hardening", json={"level": "paranoid"})
    assert r.status_code == 200
    assert r.json()["level"] == 3


def test_health(client):
    r = client.get("/api/core/sovereign-boot/health")
    assert r.status_code == 200
    assert "blocks_total" in r.json()


def test_reset(client):
    client.post("/api/core/sovereign-boot/boot", json={})
    r = client.post("/api/core/sovereign-boot/reset", json={})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_channels(client):
    r = client.get("/api/core/sovereign-boot/channels")
    assert r.status_code == 200
    data = r.json()
    assert "channels" in data
    assert "ws" in data
    assert data["offline_only"] is True


def test_ws_heartbeat(client):
    with client.websocket_connect("/api/core/sovereign-boot/ws") as ws:
        msg = ws.receive_json()
        assert isinstance(msg, dict)
