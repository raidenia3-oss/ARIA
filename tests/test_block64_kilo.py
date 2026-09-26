"""BLOQUE 64 — Kilo integration tests: /api/agent/swarm REST endpoints against the
AgentSwarmManager local.

Verifica el router complementario bajo el prefijo contractual /api/agent/swarm:
inicio, sincronizacion y supervision de sub-agentes paralelos (cola async,
bus inter-agente y estado en tiempo real).

Aislamiento: archivo separado de tests/test_block64.py (ediciones concurrentes).
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.agent.swarm_routes import router
from backend.agent_swarm import (
    AgentSwarmManager,
    get_swarm_manager,
    reset_swarm_manager,
)


@pytest.fixture
def client():
    reset_swarm_manager()
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        yield c
    reset_swarm_manager()


def test_router_has_expected_paths():
    paths = [r.path for r in router.routes]
    assert "/api/agent/swarm/tasks" in paths
    assert "/api/agent/swarm/tasks/{plan_id}/execute" in paths
    assert "/api/agent/swarm/agents" in paths
    assert "/api/agent/swarm/status" in paths
    assert "/api/agent/swarm/bus" in paths
    assert "/api/agent/swarm/publish" in paths
    assert "/api/agent/swarm/infrastructure/start" in paths
    assert "/api/agent/swarm/infrastructure/stop" in paths
    assert router.prefix == "/api/agent/swarm"
    assert "agent-swarm" in router.tags


def test_submit_plan_and_execute(client):
    r = client.post(
        "/api/agent/swarm/tasks",
        json={
            "description": "Plan and code a hello world application",
            "priority": "normal",
            "execute": True,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "executed"
    assert data["plan_id"]
    assert data["execution"]["status"] == "completed"
    assert data["execution"]["tasks_executed"] >= 1


def test_submit_plan_only(client):
    r = client.post(
        "/api/agent/swarm/tasks",
        json={
            "description": "Research and evaluate a paper on swarm intelligence",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "planned"
    assert data["task_count"] >= 1


def test_submit_requires_description(client):
    r = client.post("/api/agent/swarm/tasks", json={})
    assert r.status_code == 422


def test_submit_validates_priority(client):
    r = client.post(
        "/api/agent/swarm/tasks",
        json={
            "description": "Build a small tool",
            "priority": "impossible",
        },
    )
    assert r.status_code == 422


def test_list_tasks(client):
    client.post("/api/agent/swarm/tasks", json={"description": "Build a rest api"})
    r = client.get("/api/agent/swarm/tasks")
    assert r.status_code == 200
    assert r.json()["count"] >= 1


def test_execute_unknown_plan_404(client):
    r = client.post("/api/agent/swarm/tasks/nope/execute")
    assert r.status_code == 404


def test_agents_supervision(client):
    r = client.get("/api/agent/swarm/agents")
    assert r.status_code == 200
    assert "active_agents" in r.json()
    assert "agents" in r.json()


def test_status_realtime(client):
    client.post(
        "/api/agent/swarm/tasks",
        json={
            "description": "Plan code review and evaluate features",
        },
    )
    r = client.get("/api/agent/swarm/status")
    assert r.status_code == 200
    data = r.json()
    assert "agents_total" in data
    assert "queue" in data
    assert "bus_messages" in data
    assert "tasks_total" in data


def test_bus_and_publish(client):
    p = client.post(
        "/api/agent/swarm/publish",
        json={
            "src_agent": "planner-1",
            "topic": "events",
            "payload": {"n": 1},
        },
    )
    assert p.status_code == 200
    assert p.json()["status"] == "published"
    b = client.get("/api/agent/swarm/bus")
    assert b.status_code == 200
    assert b.json()["count"] >= 1


def test_infrastructure_start_stop(client):
    s = client.post("/api/agent/swarm/infrastructure/start")
    assert s.status_code == 200
    assert s.json()["status"] == "started"
    st = client.post("/api/agent/swarm/infrastructure/stop")
    assert st.status_code == 200
    assert st.json()["status"] == "stopped"


def test_get_swarm_manager_integrates_with_engine():
    reset_swarm_manager()
    mgr = get_swarm_manager()
    assert isinstance(mgr, AgentSwarmManager)
    assert get_swarm_manager() is mgr
    reset_swarm_manager()


# --------------------------------------------------------------------------- #
# Higiene: sin cloud, sin tokens
# --------------------------------------------------------------------------- #


def test_no_cloud_deps_in_swarm_routes():
    from backend.agent import swarm_routes

    src = open(swarm_routes.__file__, encoding="utf-8").read()
    for bad in (
        "boto3",
        "azure",
        "google.cloud",
        "kubernetes",
        "ecs",
        "eks",
        "access_token=",
        "api_key=",
        "secret=",
    ):
        assert bad not in src, f"forbidden dep/token in swarm_routes: {bad}"
