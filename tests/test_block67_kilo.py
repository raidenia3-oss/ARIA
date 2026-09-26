"""BLOQUE 67 - Kilo integration tests: /api/automation/scheduler REST."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.automation.scheduler import reset_scheduler, router


@pytest.fixture
def client(tmp_path):
    reset_scheduler()
    import backend.automation.scheduler as mod

    mod._scheduler = None
    import os

    os.environ["AURA_SCHEDULER_DIR"] = str(tmp_path)
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        yield c
    reset_scheduler()
    mod._scheduler = None
    os.environ.pop("AURA_SCHEDULER_DIR", None)


def test_router_paths():
    paths = [rt.path for rt in router.routes]
    assert router.prefix == "/api/automation/scheduler"
    for p in (
        "/api/automation/scheduler/status",
        "/api/automation/scheduler/tasks",
        "/api/automation/scheduler/tick",
        "/api/automation/scheduler/start",
        "/api/automation/scheduler/stop",
    ):
        assert p in paths, p


def test_status_default(client):
    r = client.get("/api/automation/scheduler/status")
    assert r.status_code == 200
    data = r.json()
    assert data["running"] is False
    assert data["tasks_total"] == 0


def test_create_and_list(client):
    r = client.post(
        "/api/automation/scheduler/tasks",
        json={
            "task_id": "t1",
            "name": "n",
            "kind": "k",
            "trigger": "interval",
            "interval_seconds": 10,
        },
    )
    assert r.status_code == 200
    listed = client.get("/api/automation/scheduler/tasks").json()["tasks"]
    assert len(listed) == 1
    assert listed[0]["task_id"] == "t1"


def test_get_task(client):
    client.post(
        "/api/automation/scheduler/tasks",
        json={
            "task_id": "t1",
            "name": "n",
            "kind": "k",
        },
    )
    r = client.get("/api/automation/scheduler/tasks/t1")
    assert r.status_code == 200
    assert r.json()["task"]["name"] == "n"


def test_update_task(client):
    client.post(
        "/api/automation/scheduler/tasks",
        json={
            "task_id": "t1",
            "name": "n",
            "kind": "k",
        },
    )
    r = client.put("/api/automation/scheduler/tasks/t1", json={"name": "n2"})
    assert r.status_code == 200
    assert client.get("/api/automation/scheduler/tasks/t1").json()["task"]["name"] == "n2"


def test_delete_task(client):
    client.post(
        "/api/automation/scheduler/tasks",
        json={
            "task_id": "t1",
            "name": "n",
            "kind": "k",
        },
    )
    r = client.delete("/api/automation/scheduler/tasks/t1")
    assert r.status_code == 200
    assert client.get("/api/automation/scheduler/tasks").json()["tasks"] == []


def test_pause_resume_enable(client):
    client.post(
        "/api/automation/scheduler/tasks",
        json={
            "task_id": "t1",
            "name": "n",
            "kind": "k",
        },
    )
    assert client.post("/api/automation/scheduler/tasks/t1/pause").status_code == 200
    assert client.get("/api/automation/scheduler/tasks/t1").json()["task"]["status"] == "paused"
    assert client.post("/api/automation/scheduler/tasks/t1/resume").status_code == 200
    assert (
        client.post(
            "/api/automation/scheduler/tasks/t1/enable", params={"enabled": False}
        ).status_code
        == 200
    )
    assert client.get("/api/automation/scheduler/tasks/t1").json()["task"]["enabled"] is False


def test_tick(client):
    client.post(
        "/api/automation/scheduler/tasks",
        json={
            "task_id": "t1",
            "name": "n",
            "kind": "k",
            "trigger": "interval",
            "interval_seconds": 1,
        },
    )
    # force next_run in the past
    import time

    import backend.automation.scheduler as mod

    s = mod.get_scheduler()
    t = s.get_task("t1")
    t.next_run = time.time() - 1
    r = client.post("/api/automation/scheduler/tick")
    assert r.status_code == 200
    assert len(r.json()["fired"]) == 1


def test_start_stop(client):
    assert client.post("/api/automation/scheduler/start").status_code == 200
    assert client.get("/api/automation/scheduler/status").json()["running"] is True
    client.post("/api/automation/scheduler/stop")
    assert client.get("/api/automation/scheduler/status").json()["running"] is False


def test_list_runs(client):
    client.post(
        "/api/automation/scheduler/tasks",
        json={
            "task_id": "t1",
            "name": "n",
            "kind": "k",
            "trigger": "interval",
            "interval_seconds": 1,
        },
    )
    import time

    import backend.automation.scheduler as mod

    s = mod.get_scheduler()
    t = s.get_task("t1")
    t.next_run = time.time() - 1
    client.post("/api/automation/scheduler/tick")
    r = client.get("/api/automation/scheduler/tasks/t1/runs")
    assert r.status_code == 200
    assert len(r.json()["runs"]) >= 1


def test_no_cloud_deps():
    import backend.automation.scheduler as mod

    src = open(mod.__file__, encoding="utf-8-sig").read()
    for bad in (
        "apscheduler",
        "celery",
        "datadog",
        "newrelic",
        "sentry_sdk",
        "aws_eventbridge",
        "google_cloud_scheduler",
        "access_token=",
        "api_key=",
        "secret=",
    ):
        assert bad not in src, f"cloud dep/token found in scheduler: {bad}"
