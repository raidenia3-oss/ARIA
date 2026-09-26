"""BLOQUE 91 - REST + WS tests for /api/evolution/patch (offline)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.evolution.patcher import reset_engine, router


@pytest.fixture
def client():
    reset_engine()
    app = FastAPI(title="AURA Evolution Test", version="test")
    app.include_router(router)
    with TestClient(app) as c:
        yield c
    reset_engine()


def test_status(client):
    r = client.get("/api/evolution/patch/status")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_audit_endpoint(client):
    r = client.get("/api/evolution/patch/audit", params={"root": "backend/evolution"})
    assert r.status_code == 200


def test_propose_apply_rollback(client):
    p = client.post(
        "/api/evolution/patch/propose",
        json={
            "target_file": "backend/evolution/models.py",
            "old_snippet": "",
            "new_snippet": "X_REFACTOR = 1\n",
            "description": "noop patch",
        },
    )
    assert p.status_code == 200
    pid = p.json()["patch_id"]
    a = client.post(f"/api/evolution/patch/{pid}/apply")
    assert a.json()["status"] in ("applied", "rejected")
    r = client.post(f"/api/evolution/patch/{pid}/rollback")
    assert r.json()["status"] == "rolled_back"


def test_patches_list(client):
    client.post(
        "/api/evolution/patch/propose",
        json={
            "target_file": "backend/evolution/models.py",
            "old_snippet": "",
            "new_snippet": "Y = 1\n",
            "description": "test",
        },
    )
    assert client.get("/api/evolution/patch/patches").json()["count"] >= 1
