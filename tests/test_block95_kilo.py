"""BLOQUE 95 - REST + WS tests para /api/daemon/sync."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.daemon.sync_routes import reset_sync_engine, router


@pytest.fixture(autouse=True)
def _clean():
    reset_sync_engine()
    yield
    reset_sync_engine()


@pytest.fixture
def client():
    app = FastAPI(title="AURA Sync Test", version="test")
    app.include_router(router)
    with TestClient(app) as c:
        yield c


def test_status(client):
    r = client.get("/api/daemon/sync/status")
    assert r.status_code == 200
    data = r.json()
    assert data["sync"]["local_node_id"]
    assert data["daemon"]["offline_only"] is True


def test_register_peer(client):
    r = client.post(
        "/api/daemon/sync/peers/register",
        json={
            "peer_id": "p1",
            "display_name": "Peer 1",
            "ip_address": "192.168.1.5",
            "port": 8000,
            "capabilities": ["code", "rag"],
        },
    )
    assert r.status_code == 200
    assert r.json()["node_id"] == "p1"


def test_list_peers(client):
    client.post("/api/daemon/sync/peers/register", json={"peer_id": "p1"})
    client.post("/api/daemon/sync/peers/register", json={"peer_id": "p2"})
    r = client.get("/api/daemon/sync/peers")
    assert r.json()["count"] == 2


def test_sync_with_peer(client):
    client.post("/api/daemon/sync/peers/register", json={"peer_id": "p1"})
    r = client.post("/api/daemon/sync/sync", json={"peer_id": "p1", "state_data": {"key": "value"}})
    assert r.json()["sync"] is True


def test_daemon_lifecycle(client):
    r = client.post("/api/daemon/sync/daemon/start")
    assert r.json()["started"] is True
    r = client.get("/api/daemon/sync/health")
    assert r.json()["healthy"] is True
    r = client.post("/api/daemon/sync/daemon/stop")
    assert r.json()["stopped"] is True
