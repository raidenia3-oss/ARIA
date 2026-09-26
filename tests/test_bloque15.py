"""Tests for BLOQUE 15 — Ejecución de procedimientos, workflows y extensión Chrome."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.discord_diagnostics import run_diagnostics
from backend.main import app
from backend.services.action_engine import ActionEngine
from backend.task_manager import task_manager


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_procedure():
    import time as _time

    proc_id = f"test-proc-{int(_time.time() * 1000)}"
    proc = {
        "procedure_id": proc_id,
        "name": "daily_routine_test",
        "goal": "Automate morning routine",
        "steps": [
            {
                "step_id": "s1",
                "name": "status check",
                "tool": "system.status",
                "params": {},
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
    def test_get_procedure_by_id(self, client, sample_procedure):
        resp = client.get(f"/automation/procedures/{sample_procedure}")
        assert resp.status_code == 200
        proc = resp.json()
        assert proc["procedure_id"] == sample_procedure
        assert proc["name"] == "daily_routine_test"

    def test_get_nonexistent_procedure_404(self, client):
        resp = client.get("/automation/procedures/does-not-exist")
        assert resp.status_code == 404


class TestRunProcedure:
    def test_run_procedure(self, client, sample_procedure):
        resp = client.post(f"/automation/procedures/{sample_procedure}/run")
        assert resp.status_code == 200
        result = resp.json()
        assert "task_id" in result
        assert result["procedure_id"] == sample_procedure

    def test_run_nonexistent_procedure_400(self, client):
        resp = client.post("/automation/procedures/nonexistent/run")
        assert resp.status_code == 400


class TestWorkflow:
    def test_create_workflow(self, client, sample_procedure):
        resp = client.post(
            "/automation/workflows",
            json={
                "name": "test_wf",
                "procedure_ids": [sample_procedure],
            },
        )
        assert resp.status_code == 200
        wf_id = resp.json()["workflow_id"]
        assert task_manager.tasks.get(wf_id) is not None

    def test_run_workflow(self, client, sample_procedure):
        resp = client.post(
            "/automation/workflows",
            json={
                "name": "test_wf2",
                "procedure_ids": [sample_procedure],
            },
        )
        wf_id = resp.json()["workflow_id"]
        resp2 = client.post(f"/automation/workflows/{wf_id}/run")
        assert resp2.status_code == 200
        assert resp2.json()["task_id"] == wf_id

    def test_create_workflow_unknown_proc_400(self, client, sample_procedure):
        resp = client.post(
            "/automation/workflows",
            json={
                "name": "bad",
                "procedure_ids": [sample_procedure, "nonexistent"],
            },
        )
        assert resp.status_code == 400

    def test_create_workflow_missing_fields_422(self, client):
        resp = client.post("/automation/workflows", json={"name": "x"})
        assert resp.status_code == 422


class TestWebsocketProcedure:
    def test_ws_run_procedure(self, client, sample_procedure):
        with client.websocket_connect("/api/mobile/sync/test-ws-proc-b15") as ws:
            ws.send_json({"type": "auth", "token": "test-token"})
            resp = ws.receive_json()
            assert resp.get("auth") == "accepted"

            ws.send_json(
                {
                    "action": "run_procedure",
                    "eventId": "evt-b15-001",
                    "data": {"procedure_id": sample_procedure, "params": {}},
                }
            )
            resp = ws.receive_json()
            assert resp["status"] == "ok"
            assert resp["action"] == "run_procedure"
            assert "task_id" in resp["data"]
            assert resp["eventId"] == "evt-b15-001"

    def test_ws_run_procedure_not_found(self, client):
        with client.websocket_connect("/api/mobile/sync/test-ws-proc-b15b") as ws:
            ws.send_json({"type": "auth", "token": "test-token"})
            resp = ws.receive_json()
            assert resp.get("auth") == "accepted"

            ws.send_json(
                {
                    "action": "run_procedure",
                    "data": {"procedure_id": "nonexistent"},
                }
            )
            resp = ws.receive_json()
            assert resp["status"] == "error"

    def test_ws_unknown_action_falls_through(self, client):
        with client.websocket_connect("/api/mobile/sync/test-ws-proc-b15c") as ws:
            ws.send_json({"type": "auth", "token": "test-token"})
            resp = ws.receive_json()
            assert resp.get("auth") == "accepted"

            ws.send_json({"action": "ping"})
            resp = ws.receive_json()
            assert resp.get("status") == "ok" and resp.get("action") == "ping"


class TestBrowserTools:
    def test_browser_tools_registered(self):
        engine = ActionEngine()
        for tool_name in [
            "browser.extension_status",
            "browser.active_tab",
            "browser.read_visible",
            "browser.open_url",
            "browser.click",
            "browser.type",
            "browser.select",
            "browser.screenshot",
            "browser.stop",
        ]:
            tool = engine.get_tool(tool_name)
            assert tool is not None, f"Tool {tool_name} not registered"
            assert tool.category == "browser"

    def test_browser_extension_status_tool(self):
        engine = ActionEngine()
        result = engine.execute("browser.extension_status", {})
        assert result.success
        assert result.output["status"] == "ok"

    def test_browser_stop_requires_confirmation(self):
        engine = ActionEngine()
        result = engine.execute("browser.stop", {})
        assert not result.success
        assert result.requires_confirmation


class TestActionEngineBrowserDispatch:
    def test_browser_tool_dispatch(self):
        engine = ActionEngine()
        result = engine.execute("browser.active_tab", {})
        assert result.success or (not result.success and result.error)


class TestDiscordDiagnostics:
    def test_diagnostics_no_secrets(self):
        result = run_diagnostics()
        assert "status" in result
        assert "checks" in result
        checks = result["checks"]
        assert "token_validation" in checks
        assert "token_masked" in checks
        assert "client_id_validation" in checks
        assert "backend_available" in checks
        assert "backend_url" in checks
        assert "redis_available" in checks
        assert "redis_url" in checks
        assert "bot_process_running" in checks
        assert "last_connection" in checks
        assert "configuration_source" in checks
        assert checks["token_masked"] in ("[ausente]", "****") or "****" in checks["token_masked"]
        assert checks["token_validation"] in ("configured", "absent", "invalid")
        assert isinstance(checks["backend_available"], bool)
        assert isinstance(checks["redis_available"], bool)
        assert isinstance(checks["bot_process_running"], bool)

    def test_diagnostics_endpoint(self, client):
        resp = client.get("/api/discord/diagnostics")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "checks" in data
        checks = data["checks"]
        assert "token_masked" in checks
        assert "configuration_source" in checks
        assert data["status"] in ("healthy", "degraded", "not_configured", "offline", "error")

    def test_browser_tasks_endpoint(self, client):
        resp = client.get("/api/browser/tasks")
        assert resp.status_code == 200
        assert "tasks" in resp.json()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
