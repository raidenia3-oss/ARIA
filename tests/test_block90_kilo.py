"""BLOQUE 90 - REST + WS tests for /api/security/identity (offline)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.security.identity_engine import reset_identity_engine
from backend.security.identity_routes import router


@pytest.fixture
def client():
    reset_identity_engine()
    app = FastAPI(title="AURA Identity Test", version="test")
    app.include_router(router)
    with TestClient(app) as c:
        yield c
    reset_identity_engine()


def test_status(client):
    r = client.get("/api/security/identity/status")
    assert r.status_code == 200 and r.json()["offline_only"] is True


def test_register_and_list(client):
    r = client.post("/api/security/identity/register", json={"label": "nodo-a", "role": "peer"})
    assert r.status_code == 200
    nid = r.json()["node_id"]
    g = client.get(f"/api/security/identity/nodes/{nid}")
    assert g.status_code == 200
    assert client.get("/api/security/identity/nodes").json()["count"] == 1


def test_sign_verify_roundtrip(client):
    r = client.post("/api/security/identity/register", json={"label": "a"})
    nid = r.json()["node_id"]
    s = client.post(
        "/api/security/identity/sign", json={"node_id": nid, "payload": {"msg": "hola"}}
    )
    sig = s.json()["signature_base64"]
    v = client.post(
        "/api/security/identity/verify",
        json={"sender": nid, "payload": s.json()["payload"], "signature_base64": sig},
    )
    assert v.json()["verified"] is True
    bad = client.post(
        "/api/security/identity/verify",
        json={"sender": nid, "payload": {"msg": "x"}, "signature_base64": "bad"},
    )
    assert bad.json()["verified"] is False


def test_cert_issue_and_list(client):
    r = client.post("/api/security/identity/register", json={"label": "a"})
    nid = r.json()["node_id"]
    c = client.post("/api/security/identity/certs", json={"subject_node": nid, "role": "peer"})
    assert c.status_code == 200
    assert client.get("/api/security/identity/certs").json()["count"] == 1


def test_ephemeral_lifecycle(client):
    r = client.post("/api/security/identity/register", json={"label": "a"})
    nid = r.json()["node_id"]
    e = client.post("/api/security/identity/ephemeral", json={"node_id": nid, "scope": "swarm"})
    tok = e.json()["token"]
    v = client.post(
        "/api/security/identity/ephemeral/validate",
        json={"token": tok, "node_id": nid, "scope": "swarm"},
    )
    assert v.json()["valid"] is True
    rv = client.post(f"/api/security/identity/ephemeral/revoke", params={"node_id": nid})
    assert rv.json()["revoked"] is True
    v2 = client.post(
        "/api/security/identity/ephemeral/validate",
        json={"token": tok, "node_id": nid, "scope": "swarm"},
    )
    assert v2.json()["valid"] is False


def test_ws_heartbeat(client):
    with client.websocket_connect("/api/security/identity/ws") as ws:
        d = ws.receive_json()
        assert d["type"] == "heartbeat" and d["offline_only"] is True
