"""BLOQUE 93 - REST + WS tests for /api/swarm/marketplace (offline)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.swarm.swarm_routes import reset_swarm_engine, router


@pytest.fixture
def client():
    reset_swarm_engine()
    app = FastAPI(title="AURA Swarm Test", version="test")
    app.include_router(router)
    with TestClient(app) as c:
        yield c
    reset_swarm_engine()


def test_status(client):
    r = client.get("/api/swarm/marketplace/status")
    assert r.status_code == 200 and r.json()["nodes"] == 0


def test_register_and_nodes(client):
    p = client.post(
        "/api/swarm/marketplace/register",
        json={"node_id": "n1", "roles": ["analyst"], "skills": ["code"]},
    )
    assert p.status_code == 200
    nodes = client.get("/api/swarm/marketplace/nodes?role=analyst").json()
    assert nodes["count"] == 1


def test_publish_and_discover(client):
    p = client.post(
        "/api/swarm/marketplace/publish",
        json={"name": "CodeScan", "category": "security", "description": "scans"},
    )
    assert p.status_code == 200
    skills = client.get("/api/swarm/marketplace/skills?category=security").json()
    assert skills["count"] == 1
    dl = client.get(f"/api/swarm/marketplace/skills/{p.json()['skill_id']}").json()
    assert dl["downloads"] == 1


def test_assign_and_assignments(client):
    client.post("/api/swarm/marketplace/register", json={"node_id": "n1", "roles": ["analyst"]})
    a = client.post(
        "/api/swarm/marketplace/assign",
        params={"task_id": "t1", "node_id": "n1", "role": "analyst"},
    )
    assert a.status_code == 200 and a.json()["role"] == "analyst"
    lst = client.get("/api/swarm/marketplace/assignments").json()
    assert lst["count"] == 1
