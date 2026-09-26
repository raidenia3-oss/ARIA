"""Tests for BLOQUE 14 — Autoaprendizaje: captura de tareas a procedimientos."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.task_manager import task_manager
from backend.task_models import TaskStatus, TaskStep


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def completed_task():
    task = task_manager.create_task.__self__ and task_manager
    task_id = task_manager.tasks  # use in-memory
    import time as _time

    from backend.task_manager import TaskModel

    task_model = TaskModel(
        task_id=f"test-cap-{int(_time.time() * 1000)}",
        origin="aura",
        name="preparar mi jornada test",
        action_type="automation",
        goal="Preparar entorno de trabajo",
        status=TaskStatus.PENDING,
    )
    task_model.steps = [
        TaskStep(
            step_id="s1",
            name="check system",
            tool="system.status",
            params={},
            status=TaskStatus.COMPLETED,
            result={"cpu_percent": 15.0},
        ),
        TaskStep(
            step_id="s2",
            name="get weather",
            tool="web.weather",
            params={"query": "Madrid"},
            status=TaskStatus.COMPLETED,
            result={"temp": 22},
        ),
    ]
    task_model.status = TaskStatus.COMPLETED
    task_manager.tasks[task_model.task_id] = task_model
    task_manager._save_tasks()
    yield task_model.task_id
    task_manager.tasks.pop(task_model.task_id, None)
    task_manager._save_tasks()


class TestAutomationCapture:
    """Tests for capturing completed tasks as learned procedures."""

    def test_capture_completed_task_as_procedure(self, client, completed_task):
        task_id = completed_task
        resp = client.post(
            "/automation/procedures/capture",
            json={
                "task_id": task_id,
                "name": "preparar mi jornada",
                "goal": "Automatizar preparacion matutina",
            },
        )
        assert resp.status_code == 200
        proc = resp.json()
        assert proc["procedure_id"].startswith("proc-")
        assert proc["name"] == "preparar mi jornada"
        assert proc["goal"] == "Automatizar preparacion matutina"
        assert proc["source_task_id"] == task_id
        assert proc["captured_from"] == "preparar mi jornada test"
        assert len(proc["steps"]) == 2
        assert proc["steps"][0]["tool"] == "system.status"
        assert proc["steps"][1]["tool"] == "web.weather"

    def test_get_captured_procedure(self, client, completed_task):
        task_id = completed_task
        resp = client.post(
            "/automation/procedures/capture",
            json={
                "task_id": task_id,
                "name": "daily_routine",
            },
        )
        assert resp.status_code == 200
        proc_id = resp.json()["procedure_id"]

        resp2 = client.get("/automation/procedures")
        assert resp2.status_code == 200
        procs = resp2.json()["procedures"]
        assert any(p["procedure_id"] == proc_id for p in procs)

    def test_capture_nonexistent_task_fails(self, client):
        resp = client.post(
            "/automation/procedures/capture",
            json={
                "task_id": "does-not-exist",
                "name": "x",
            },
        )
        assert resp.status_code == 400
        assert "not found" in resp.json()["detail"]

    def test_search_captured_procedure(self, client, completed_task):
        task_id = completed_task
        client.post(
            "/automation/procedures/capture",
            json={
                "task_id": task_id,
                "name": "preparar mi jornada",
            },
        )
        resp = client.get("/automation/procedures/search?q=preparar")
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert any("preparar" in p["name"].lower() for p in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
