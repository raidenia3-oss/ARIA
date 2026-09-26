"""BLOQUE 94 - REST + WebSocket contract tests for the ZKP & audit engine.

Validates the /api/security/zkp endpoints and the /ws channel.
"""

from __future__ import annotations

import json
from typing import Any, Dict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.security.zk_audit import reset_zk_audit_engine
from backend.security.zk_routes import router as zk_router


@pytest.fixture(autouse=True)
def _reset_engine():
    reset_zk_audit_engine()
    yield
    reset_zk_audit_engine()


@pytest.fixture
def client():
    reset_zk_audit_engine()
    app = FastAPI(title="AURA ZKP Test", version="test")
    app.include_router(zk_router)
    with TestClient(app) as c:
        yield c
    reset_zk_audit_engine()


def test_zkp_status_endpoint(client):
    r = client.get("/api/security/zkp/status")
    assert r.status_code == 200
    body: Dict[str, Any] = r.json()
    assert body["status"] == "ok"
    assert body["offline_only"] is True
    assert "audit" in body


def test_issue_and_verify_proof(client):
    payload = {"statement": "has_role:admin", "witness": 42, "prover_node": "nodeA"}
    r = client.post("/api/security/zkp/proofs", json=payload)
    assert r.status_code == 200
    proof = r.json()
    assert proof["statement"] == "has_role:admin"
    assert proof["verified"] is False
    proof_id = proof["proof_id"]

    r2 = client.post("/api/security/zkp/verify", json={"proof_id": proof_id})
    assert r2.status_code == 200
    body = r2.json()
    assert body["verified"] is True
    assert body["proof_id"] == proof_id


def test_verify_inline_proof(client):
    payload = {"statement": "has_role:admin", "witness": 7, "prover_node": "nodeB"}
    r = client.post("/api/security/zkp/proofs", json=payload)
    proof = r.json()
    r2 = client.post("/api/security/zkp/verify", json={"proof": proof})
    assert r2.status_code == 200
    assert r2.json()["verified"] is True


def test_tampered_proof_rejected_by_endpoint(client):
    payload = {"statement": "has_role:admin", "witness": 42, "prover_node": "nodeA"}
    r = client.post("/api/security/zkp/proofs", json=payload)
    proof = r.json()
    orig = proof["response_b64"]
    proof["response_b64"] = orig[:-2] + ("AA" if not orig.endswith("AA") else "BB")
    r2 = client.post("/api/security/zkp/verify", json={"proof": proof})
    assert r2.status_code == 200
    assert r2.json()["verified"] is False


def test_list_proofs_and_groups(client):
    client.post(
        "/api/security/zkp/proofs", json={"statement": "s1", "witness": 1, "prover_node": "n1"}
    )
    client.post(
        "/api/security/zkp/proofs", json={"statement": "s2", "witness": 2, "prover_node": "n2"}
    )
    r = client.get("/api/security/zkp/proofs")
    assert r.status_code == 200
    assert r.json()["count"] == 2

    r2 = client.get("/api/security/zkp/groups")
    assert r2.status_code == 200
    assert r2.json()["count"] >= 1


def test_create_group_endpoint(client):
    r = client.post("/api/security/zkp/groups", json={"bits": 128})
    assert r.status_code == 200
    body = r.json()
    assert body["bits"] == 128
    assert body["offline_only"] is True


def test_audit_status_and_entries(client):
    client.post(
        "/api/security/zkp/proofs", json={"statement": "s1", "witness": 1, "prover_node": "n1"}
    )
    r = client.get("/api/security/zkp/audit/status")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["entries"] >= 1

    r2 = client.get("/api/security/zkp/audit/entries")
    assert r2.status_code == 200
    assert r2.json()["count"] >= 1


def test_audit_verify_endpoint(client):
    client.post(
        "/api/security/zkp/proofs", json={"statement": "s1", "witness": 1, "prover_node": "n1"}
    )
    r = client.post("/api/security/zkp/audit/verify")
    assert r.status_code == 200
    body = r.json()
    assert body["verified"] is True
    assert body["tampered"] is False


def test_zkp_ws_heartbeat(client):
    with client.websocket_connect("/api/security/zkp/ws") as ws:
        msg = ws.receive_json()
        assert "type" in msg
        assert msg["type"] == "heartbeat"
        assert "offline_only" in msg


def test_zkp_ws_receives_audit_events(client):
    with client.websocket_connect("/api/security/zkp/ws") as ws:
        ws.receive_json()  # drain heartbeat
        client.post(
            "/api/security/zkp/proofs", json={"statement": "s1", "witness": 1, "prover_node": "n1"}
        )
        seen = None
        for _ in range(10):
            msg = ws.receive_json()
            if msg.get("type") == "zk_proof_issued":
                seen = msg
                break
        assert seen is not None
        assert seen["actor"] == "n1"


def test_reset_endpoint(client):
    client.post(
        "/api/security/zkp/proofs", json={"statement": "s1", "witness": 1, "prover_node": "n1"}
    )
    r = client.post("/api/security/zkp/reset")
    assert r.status_code == 200
    assert r.json()["reset"] is True
    r2 = client.get("/api/security/zkp/proofs")
    assert r2.json()["count"] == 0
