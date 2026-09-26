"""BLOQUE 92 - REST + WS tests for /api/planner/goals (offline)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.planner.planner_routes import reset_planner, router


@pytest.fixture
def client():
    reset_planner()
    app = FastAPI(title="AURA Planner Test", version="test")
    app.include_router(router)
    with TestClient(app) as c:
        yield c
    reset_planner()


def test_status(client):
    r = client.get("/api/planner/goals/status")
    assert r.status_code == 200 and r.json()["goals_total"] == 0


def test_decompose_and_list(client):
    p = client.post(
        "/api/planner/goals/decompose",
        json={
            "title": "Build AURA",
            "description": "desc",
            "milestones": [{"title": "Plan"}, {"title": "Code"}],
        },
    )
    assert p.status_code == 200
    gid = p.json()["goal_id"]
    lst = client.get("/api/planner/goals/list").json()
    assert lst["count"] >= 1
    g = client.get(f"/api/planner/goals/{gid}").json()
    assert g["title"] == "Build AURA"
    assert len(g["milestones"]) == 2


def test_milestone_update(client):
    p = client.post(
        "/api/planner/goals/decompose", json={"title": "G", "milestones": [{"title": "M1"}]}
    )
    gid = p.json()["goal_id"]
    mid = p.json()["milestones"][0]["milestone_id"]
    u = client.post(f"/api/planner/goals/{gid}/milestone/{mid}", json={"progress": 75.0})
    assert u.status_code == 200 and u.json()["progress"] == 75.0


def test_replan(client):
    p = client.post("/api/planner/goals/decompose", json={"title": "G"})
    gid = p.json()["goal_id"]
    r = client.post(f"/api/planner/goals/{gid}/replan", params={"reason": "context_change"})
    assert r.json()["replanned"] is True
