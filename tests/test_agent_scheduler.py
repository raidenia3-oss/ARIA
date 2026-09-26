"""Tests for the AURA Agent Scheduler (BackgroundDaemon, JanReflectionEngine, AsyncEventDispatcher).

Valida:
- Registro y ejecución de tareas programadas (async).
- Start/Stop del daemon.
- get_status y toggle de tareas.
- ReflectionEngine con mock (sin Jan real).
- AsyncEventDispatcher hacia el WebSocket Gateway.
- Endpoints REST del scheduler.
"""

from __future__ import annotations

import asyncio
import os
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from backend.agent_scheduler import (
    AsyncEventDispatcher,
    BackgroundDaemon,
    JanReflectionEngine,
    get_agent_scheduler,
    reset_agent_scheduler,
)


@pytest.fixture(autouse=True)
def _reset_scheduler():
    """Resetea el singleton antes y después de cada test."""
    reset_agent_scheduler()
    yield
    reset_agent_scheduler()


class TestBackgroundDaemon:
    """Tests para BackgroundDaemon (registro, ejecución, start/stop)."""

    def test_register_and_list_tasks(self):
        daemon = BackgroundDaemon()

        async def dummy_task():
            return "ok"

        task_id = daemon.register_task("test_task", interval=5, func=dummy_task)
        assert task_id in daemon.tasks
        assert daemon.tasks[task_id].name == "test_task"
        assert daemon.tasks[task_id].enabled is True
        assert daemon.tasks[task_id].run_count == 0

    def test_unregister_task(self):
        daemon = BackgroundDaemon()

        async def dummy():
            return None

        task_id = daemon.register_task("t1", interval=5, func=dummy)
        assert daemon.unregister_task(task_id) is True
        assert task_id not in daemon.tasks

    def test_enable_disable_task(self):
        daemon = BackgroundDaemon()

        async def dummy():
            return None

        task_id = daemon.register_task("t1", interval=5, func=dummy)
        assert daemon.enable_task(task_id, enabled=False) is True
        assert daemon.tasks[task_id].enabled is False
        assert daemon.enable_task(task_id, enabled=True) is True
        assert daemon.tasks[task_id].enabled is True

    @pytest.mark.asyncio
    async def test_run_task_executes_func(self):
        daemon = BackgroundDaemon()
        executed = []

        async def my_task():
            executed.append("ran")

        task_id = daemon.register_task("t1", interval=5, func=my_task)
        await daemon._run_task(daemon.tasks[task_id])
        assert executed == ["ran"]
        assert daemon.tasks[task_id].run_count == 1

    @pytest.mark.asyncio
    async def test_run_task_handles_error(self):
        daemon = BackgroundDaemon()

        async def failing_task():
            raise ValueError("boom")

        task_id = daemon.register_task("t1", interval=5, func=failing_task)
        await daemon._run_task(daemon.tasks[task_id])
        assert "boom" in daemon.tasks[task_id].last_error

    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        daemon = BackgroundDaemon()

        async def dummy():
            return None

        daemon.register_task("t1", interval=5, func=dummy)
        daemon.start()
        assert daemon._running is True
        assert daemon._main_loop_task is not None
        await asyncio.sleep(0.1)
        await daemon.stop()
        assert daemon._running is False
        assert daemon._main_loop_task is None

    @pytest.mark.asyncio
    async def test_default_tasks_scheduled(self):
        daemon = BackgroundDaemon()
        daemon.start()
        task_names = [t.name for t in daemon.tasks.values()]
        assert "coherence_audit" in task_names
        assert "jan_reflection" in task_names
        assert "plot_summary" in task_names
        assert "cache_cleanup" in task_names
        assert "vault_backup" in task_names
        await daemon.stop()

    def test_get_status(self):
        daemon = BackgroundDaemon()

        async def dummy():
            return None

        daemon.register_task("t1", interval=5, func=dummy)
        status = daemon.get_status()
        assert status["running"] is False
        assert status["task_count"] == 1
        assert len(status["tasks"]) == 1
        assert status["tasks"][0]["name"] == "t1"


class TestJanReflectionEngine:
    """Tests para JanReflectionEngine (con mocks)."""

    @pytest.mark.asyncio
    async def test_reflect_on_work_no_canon_returns_none(self):
        engine = JanReflectionEngine()
        with mock.patch.object(engine, "_get_recent_canon", return_value=[]):
            result = await engine.reflect_on_work("work_no_events")
            assert result is None

    @pytest.mark.asyncio
    async def test_reflect_on_work_with_jan_response(self):
        engine = JanReflectionEngine()
        fake_events = [{"event_id": "e1", "description": "El héroe nace"}]
        with mock.patch.object(engine, "_get_recent_canon", return_value=fake_events):
            mock_jan = mock.AsyncMock(
                return_value='{"analysis": "OK", "gaps": [], "plot_twists": ["g1"]}'
            )
            with mock.patch.object(engine, "_query_jan", side_effect=mock_jan):
                result = await engine.reflect_on_work("test_work")
                assert result is not None
                assert result["analysis"] == "OK"
                assert result["plot_twists"] == ["g1"]

    @pytest.mark.asyncio
    async def test_reflect_on_work_fallback_to_router(self):
        engine = JanReflectionEngine(ai_router=mock.MagicMock())
        fake_events = [{"event_id": "e1", "description": "El héroe nace"}]
        with mock.patch.object(engine, "_get_recent_canon", return_value=fake_events):
            with mock.patch.object(
                engine, "_query_jan", new_callable=mock.AsyncMock, return_value=None
            ):
                with mock.patch.object(
                    engine,
                    "_query_router",
                    new_callable=mock.AsyncMock,
                    return_value="Fallback analysis text",
                ):
                    result = await engine.reflect_on_work("test_work")
                    assert result is not None
                    assert "Fallback" in result["analysis"]

    @pytest.mark.asyncio
    async def test_reflect_on_work_invalid_json(self):
        engine = JanReflectionEngine()
        fake_events = [{"event_id": "e1", "description": "Evento"}]
        with mock.patch.object(engine, "_get_recent_canon", return_value=fake_events):
            with mock.patch.object(
                engine, "_query_jan", new_callable=mock.AsyncMock, return_value="not json"
            ):
                with mock.patch.object(
                    engine, "_query_router", new_callable=mock.AsyncMock, return_value=None
                ):
                    result = await engine.reflect_on_work("test_work")
                    assert "not json" in result["analysis"]

    @pytest.mark.asyncio
    async def test_summarize_work_no_canon_returns_none(self):
        engine = JanReflectionEngine()
        with mock.patch.object(engine, "_get_recent_canon", return_value=[]):
            result = await engine.summarize_work("work_no_events")
            assert result is None


class TestAsyncEventDispatcher:
    """Tests para AsyncEventDispatcher."""

    @pytest.mark.asyncio
    async def test_dispatch_to_websocket_calls_gateway(self):
        mock_ws = mock.MagicMock()
        with mock.patch("backend.websocket_manager.ws_gateway") as mocked_gateway:
            mocked_gateway.broadcast = mock.AsyncMock(return_value=1)
            sent = await AsyncEventDispatcher.dispatch_to_websocket(
                "canon_event", {"work_id": "w1"}, work_id="w1"
            )
            assert sent == 1
            mocked_gateway.broadcast.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_archive_to_discord_vault(self):
        with mock.patch(
            "backend.discord_diagnostics.record_canon_event", return_value=True
        ) as mocked:
            result = await AsyncEventDispatcher.archive_to_discord_vault(
                "w1", "reflection", {"analysis": "test"}
            )
            assert result is True
            mocked.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_reflection_both_channels(self):
        with (
            mock.patch("backend.websocket_manager.ws_gateway") as mocked_gateway,
            mock.patch(
                "backend.discord_diagnostics.record_canon_event", return_value=True
            ) as mocked_record,
        ):
            mocked_gateway.broadcast = mock.AsyncMock(return_value=1)
            await AsyncEventDispatcher.dispatch_reflection(
                "w1",
                {
                    "analysis": "great story",
                    "gaps": ["gap1"],
                    "plot_twists": ["twist1"],
                },
            )
            mocked_gateway.broadcast.assert_awaited()
            mocked_record.assert_called_once()


class TestAgentSchedulerAPI:
    """Tests para los endpoints REST del scheduler."""

    @pytest.fixture()
    def client(self) -> TestClient:
        from backend.main import app

        return TestClient(app)

    def test_get_scheduler_status(self, client: TestClient):
        resp = client.get("/api/agent/scheduler/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "running" in data
        assert "task_count" in data
        assert "tasks" in data
        assert isinstance(data["tasks"], list)

    def test_run_task_by_name_not_found(self, client: TestClient):
        resp = client.post("/api/agent/scheduler/run/nonexistent_task")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"

    def test_toggle_task_not_found(self, client: TestClient):
        resp = client.post("/api/agent/scheduler/enable/nonexistent_task", json={"enabled": False})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"

    def test_reflection_no_work_returns_error(self, client: TestClient):
        resp = client.post("/api/agent/reflection/nonexistent_work")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"

    def test_summary_no_work_returns_error(self, client: TestClient):
        resp = client.post("/api/agent/summary/nonexistent_work")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"


class TestSingletonAndReset:
    def test_get_scheduler_creates_singleton(self):
        daemon = get_agent_scheduler()
        daemon2 = get_agent_scheduler()
        assert daemon is daemon2

    def test_reset_clears_singleton(self):
        get_agent_scheduler()
        reset_agent_scheduler()
        daemon = get_agent_scheduler()
        assert daemon is not None
        reset_agent_scheduler()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
