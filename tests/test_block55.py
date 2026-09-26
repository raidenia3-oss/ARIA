"""Tests for BLOQUE 55 - AURA Local Autonomous Task Orchestrator & Reasoning Loop."""

import pytest
from fastapi.testclient import TestClient

from backend.agents.orchestrator import (
    TaskStatus,
    ToolConnector,
    ToolResult,
    ToolResultStatus,
    VibeCodingOrchestrator,
    reset_orchestrator,
    vibe_orchestrator,
)
from backend.main import app


def test_tool_result_status_enum():
    assert ToolResultStatus.SUCCESS.value == "success"
    assert ToolResultStatus.FAILED.value == "failed"


def test_task_status_enum():
    assert TaskStatus.RUNNING.value == "running"
    assert TaskStatus.COMPLETED.value == "completed"


def test_create_and_plan_task():
    orch = VibeCodingOrchestrator()
    t = orch.create_task(" crear proyecto test ", max_iterations=5)
    orch.plan_task(t)
    assert t.plan
    assert t.status == TaskStatus.PLANNING
    assert orch.get_task(t.task_id) is t


def test_run_task_simple():
    orch = VibeCodingOrchestrator()
    t = orch.create_task("explorar directorio actual", max_iterations=5)
    orch.plan_task(t)
    import asyncio

    asyncio.run(orch.run_task(t.task_id))
    assert t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
    assert t.steps


def test_list_tasks():
    orch = VibeCodingOrchestrator()
    orch.create_task("tarea A", max_iterations=3)
    orch.create_task("tarea B", max_iterations=3)
    assert len(orch.list_tasks()) >= 2


def test_delete_task():
    orch = VibeCodingOrchestrator()
    t = orch.create_task("tarea a borrar", max_iterations=3)
    assert orch.delete_task(t.task_id) is True
    assert orch.get_task(t.task_id) is None
    assert orch.delete_task(t.task_id) is False


def test_status_endpoint():
    c = TestClient(app)
    r = c.get("/api/agent/status")
    assert r.status_code == 200
    assert "tasks_total" in r.json()


def test_create_task_endpoint():
    c = TestClient(app)
    r = c.post(
        "/api/agent/tasks",
        json={"objective": "explorar directorio actual", "execute": True, "max_iterations": 5},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("completed", "failed")
    assert "steps" in data


def test_list_tasks_endpoint():
    c = TestClient(app)
    r = c.get("/api/agent/tasks")
    assert r.status_code == 200
    assert "tasks" in r.json()


def test_get_task_endpoint():
    c = TestClient(app)
    create = c.post(
        "/api/agent/tasks",
        json={"objective": "explorar directorio actual", "execute": True, "max_iterations": 5},
    )
    tid = create.json()["task_id"]
    r = c.get(f"/api/agent/tasks/{tid}")
    assert r.status_code == 200
    assert r.json()["task_id"] == tid


def test_get_task_not_found():
    c = TestClient(app)
    r = c.get("/api/agent/tasks/does-not-exist")
    assert r.status_code == 404


def test_cancel_task_endpoint():
    c = TestClient(app)
    create = c.post(
        "/api/agent/tasks", json={"objective": "explorar directorio actual", "max_iterations": 5}
    )
    tid = create.json()["task_id"]
    r = c.post(f"/api/agent/tasks/{tid}/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


def test_delete_task_endpoint():
    c = TestClient(app)
    create = c.post(
        "/api/agent/tasks", json={"objective": "explorar directorio actual", "max_iterations": 5}
    )
    tid = create.json()["task_id"]
    r = c.delete(f"/api/agent/tasks/{tid}")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_persist_and_restore():
    import json
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        orch = VibeCodingOrchestrator(state_dir=d)
        t = orch.create_task("tarea persistente", max_iterations=3)
        orch.plan_task(t)
        orch2 = VibeCodingOrchestrator(state_dir=d)
        found = [x for x in orch2.list_tasks() if x.task_id == t.task_id]
        assert len(found) == 1
        assert found[0].plan == t.plan


def test_tool_connector_read_write_file(tmp_path):
    tc = ToolConnector()
    p = tmp_path / "hola.txt"
    r = tc._write_file({"path": str(p), "content": "hola mundo"})
    assert r.status == ToolResultStatus.SUCCESS
    r2 = tc._read_file({"path": str(p)})
    assert r2.status == ToolResultStatus.SUCCESS
    assert "hola mundo" in r2.output
