"""Tests for BLOQUE 15 — Ejecución de procedimientos y workflows compuestos."""

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
def sample_procedure():
    """Crea un procedimiento de ejemplo directamente."""
    import time as _time

    proc_id = f"test-proc-{int(_time.time() * 1000)}"
    proc = {
        "procedure_id": proc_id,
        "name": "preparar_mi_jornada_test",
        "goal": "Automatizar preparacion matutina",
        "steps": [
            {
                "step_id": "s1",
                "name": "check system",
                "tool": "system.status",
                "params": {},
                "result": {},
            },
            {
                "step_id": "s2",
                "name": "get weather",
                "tool": "web.weather",
                "params": {"query": "Madrid"},
                "result": {},
            },
        ],
        "created_at": "2026-09-05T14:00:00",
        "execution_count": 0,
        "last_executed": None,
        "last_error": None,
    }
    task_manager._learned_procedures[proc_id] = proc
    task_manager._save_learned()
    yield proc_id
    task_manager._learned_procedures.pop(proc_id, None)
    task_manager._save_learned()


class TestGetProcedure:
    """Tests for GET /automation/procedures/{proc_id}."""

    def test_get_procedure_by_id(self, client, sample_procedure):
        proc_id = sample_procedure
        resp = client.get(f"/automation/procedures/{proc_id}")
        assert resp.status_code == 200
        proc = resp.json()
        assert proc["procedure_id"] == proc_id
        assert proc["name"] == "preparar_mi_jornada_test"
        assert len(proc["steps"]) == 2

    def test_get_nonexistent_procedure_returns_404(self, client):
        resp = client.get("/automation/procedures/does-not-exist")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "procedure_not_found"


class TestRunProcedure:
    """Tests for POST /automation/procedures/{proc_id}/run."""

    def test_run_procedure_creates_task(self, client, sample_procedure):
        proc_id = sample_procedure
        resp = client.post(f"/automation/procedures/{proc_id}/run")
        assert resp.status_code == 200
        result = resp.json()
        assert "task_id" in result
        assert result["procedure_id"] == proc_id
        task = task_manager.tasks.get(result["task_id"])
        assert task is not None
        assert task.status in (TaskStatus.RUNNING, TaskStatus.COMPLETED, TaskStatus.FAILED)

    def test_run_procedure_with_params_override(self, client, sample_procedure):
        proc_id = sample_procedure
        resp = client.post(
            f"/automation/procedures/{proc_id}/run", json={"params": {"query": "Barcelona"}}
        )
        assert resp.status_code == 200
        task_id = resp.json()["task_id"]
        task = task_manager.tasks.get(task_id)
        weather_step = next(s for s in task.steps if s.tool == "web.weather")
        assert weather_step.params["query"] == "Barcelona"

    def test_run_nonexistent_procedure_returns_400(self, client):
        resp = client.post("/automation/procedures/nonexistent/run")
        assert resp.status_code == 400


class TestWorkflow:
    """Tests for workflow compuesto."""

    def test_create_and_run_workflow(self, client, sample_procedure):
        proc_id = sample_procedure
        resp = client.post(
            "/automation/workflows",
            json={
                "name": "mi_dia_test",
                "procedure_ids": [proc_id],
                "goal": "Preparar dia completo",
            },
        )
        assert resp.status_code == 200
        wf_id = resp.json()["workflow_id"]
        assert task_manager.tasks.get(wf_id) is not None

        resp2 = client.post(f"/automation/workflows/{wf_id}/run")
        assert resp2.status_code == 200
        assert resp2.json()["task_id"] == wf_id

    def test_create_workflow_unknown_procedure_returns_400(self, client, sample_procedure):
        resp = client.post(
            "/automation/workflows",
            json={
                "name": "bad_wf",
                "procedure_ids": [sample_procedure, "nonexistent"],
            },
        )
        assert resp.status_code == 400

    def test_create_workflow_missing_fields_returns_422(self, client):
        resp = client.post("/automation/workflows", json={"name": "x"})
        assert resp.status_code == 422


class TestWebsocketProcedure:
    """Tests for run_procedure action over WebSocket."""

    def test_ws_run_procedure(self, client, sample_procedure):
        proc_id = sample_procedure
        with client.websocket_connect("/api/mobile/sync/test-ws-proc") as ws:
            ws.send_json({"type": "auth", "token": "test-token"})
            resp = ws.receive_json()
            assert resp.get("auth") == "accepted"

            ws.send_json(
                {
                    "action": "run_procedure",
                    "eventId": "evt-test-001",
                    "data": {"procedure_id": proc_id, "params": {}},
                }
            )
            resp = ws.receive_json()
            assert resp["status"] == "ok"
            assert resp["action"] == "run_procedure"
            assert "task_id" in resp["data"]
            assert resp["eventId"] == "evt-test-001"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
