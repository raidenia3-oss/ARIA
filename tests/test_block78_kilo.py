"""BLOQUE 78 - Local Decentralized P2P Mesh REST tests."""

from __future__ import annotations

import pytest

from backend.network.mesh import reset_mesh_orchestrator
from backend.network.mesh_router import router


@pytest.fixture(autouse=True)
def _reset():
    reset_mesh_orchestrator()
    yield
    reset_mesh_orchestrator()


@pytest.fixture
def client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        yield c


def test_mesh_status(client):
    r = client.get("/api/network/mesh/status")
    assert r.status_code == 200
    body = r.json()
    assert body["peers"] == 0
    assert "node_id" in body


def test_mesh_nodes_empty(client):
    r = client.get("/api/network/mesh/nodes")
    assert r.status_code == 200
    assert r.json() == []


def test_mesh_add_and_list_node(client):
    r = client.post(
        "/api/network/mesh/nodes",
        json={
            "node_id": "node-1",
            "host": "192.168.1.10",
            "port": 48178,
            "shared_secret": "sec",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["node_id"] == "node-1"
    assert body["host"] == "192.168.1.10"

    listing = client.get("/api/network/mesh/nodes")
    assert listing.status_code == 200
    assert len(listing.json()) == 1


def test_mesh_add_duplicate_node(client):
    client.post("/api/network/mesh/nodes", json={"node_id": "dup"})
    r = client.post("/api/network/mesh/nodes", json={"node_id": "dup"})
    assert r.status_code == 409


def test_mesh_remove_node(client):
    client.post("/api/network/mesh/nodes", json={"node_id": "r1"})
    r = client.delete("/api/network/mesh/nodes/r1")
    assert r.status_code == 200
    assert r.json()["removed"] is True
    r2 = client.delete("/api/network/mesh/nodes/r1")
    assert r2.status_code == 404


def test_mesh_sync(client):
    r = client.post(
        "/api/network/mesh/sync",
        json={
            "knowledge": {"k": 1},
            "tasks": [{"id": "t1"}],
            "directives": [{"id": "d1"}],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["knowledge"] == {"k": 1}
    assert body["version"] == 1
    assert body["tasks"][0]["id"] == "t1"


def test_mesh_packet_encode_decode(client):
    enc = client.post(
        "/api/network/mesh/packet/encode",
        json={
            "payload": "hello",
            "dst": "peer",
            "msg_type": "data",
        },
    )
    assert enc.status_code == 200
    hexdata = enc.json()["encoded_hex"]

    dec = client.post(
        "/api/network/mesh/packet/decode",
        json={
            "payload": hexdata,
        },
    )
    assert dec.status_code == 200
    body = dec.json()
    assert body["payload"] == "hello"
    assert body["msg_type"] == "data"


def test_mesh_packet_decode_bad(client):
    r = client.post("/api/network/mesh/packet/decode", json={"payload": "nothex"})
    assert r.status_code == 400


def test_mesh_health(client):
    r = client.get("/api/network/mesh/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["offline_only"] is True


def test_mesh_reset(client):
    client.post("/api/network/mesh/nodes", json={"node_id": "x"})
    r = client.post("/api/network/mesh/reset")
    assert r.status_code == 200
    listing = client.get("/api/network/mesh/nodes")
    assert listing.json() == []
