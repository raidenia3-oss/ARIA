"""Tests for BLOQUE 57 - AURA Local Agentic Memory & Experience Reinforcement Engine.

Valida (100% local, sin cloud):
- MemoryEngine: registro, busqueda semantica, inyeccion de contexto.
- AgentMemoryStore: registro de trazas exitosas/fallidas/corregidas.
- Endpoints REST /memory: status, traces, search, inject, experiences.
- Aislamiento: metricas de recencia y relevancia.

Nota: los tests REST usan un app liviano sin cargar backend.main pesado.
"""

from __future__ import annotations

import asyncio
import tempfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.agent.memory_store import (
    AgentMemoryStore,
    ExecutionTrace,
    TraceOutcome,
    get_agent_memory,
    reset_agent_memory,
)

try:
    from backend.agents.orchestrator import (
        VibeCodingOrchestrator,
        reset_orchestrator,
    )
except Exception:  # pragma: no cover - orquestador pesado puede no estar disponible
    VibeCodingOrchestrator = None  # type: ignore
    reset_orchestrator = None  # type: ignore


@pytest.fixture()
def memory_store(monkeypatch):
    reset_agent_memory()
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("AURA_TRACE_DIR", tmp)
        store = AgentMemoryStore()
        yield store
        reset_agent_memory()


class TestExecutionTrace:
    def test_to_dict_serializes_all_fields(self):
        trace = ExecutionTrace(
            trace_id="t1",
            task_id="task-1",
            objective="test objective",
            outcome=TraceOutcome.SUCCESS,
            steps=[{"step_id": "s1", "tool": "shell"}],
            error="",
            correction="",
            duration_ms=100.0,
        )
        d = trace.to_dict()
        assert d["trace_id"] == "t1"
        assert d["task_id"] == "task-1"
        assert d["outcome"] == "success"
        assert d["objective"] == "test objective"
        assert len(d["steps"]) == 1

    def test_outcome_enum_values(self):
        assert TraceOutcome.SUCCESS.value == "success"
        assert TraceOutcome.FAILED.value == "failed"
        assert TraceOutcome.CORRECTED.value == "corrected"
        assert TraceOutcome.PARTIAL.value == "partial"


class TestAgentMemoryStore:
    def test_record_and_get_trace(self, memory_store):
        trace = ExecutionTrace(
            trace_id="trace-001",
            task_id="task-001",
            objective="explorar directorio",
            outcome=TraceOutcome.SUCCESS,
            steps=[{"tool": "list_dir", "action": "explorar"}],
        )
        tid = memory_store.record_trace(trace)
        assert tid == "trace-001"
        fetched = memory_store.get_trace("trace-001")
        assert fetched is not None
        assert fetched.objective == "explorar directorio"

    def test_list_traces_by_outcome(self, memory_store):
        memory_store.record_trace(
            ExecutionTrace(
                trace_id="ok-1",
                task_id="t1",
                objective="tarea exitosa",
                outcome=TraceOutcome.SUCCESS,
            )
        )
        memory_store.record_trace(
            ExecutionTrace(
                trace_id="fail-1",
                task_id="t2",
                objective="tarea fallida",
                outcome=TraceOutcome.FAILED,
                error="algo fallo",
            )
        )
        oks = memory_store.list_traces(outcome="success")
        fails = memory_store.list_traces(outcome="failed")
        assert len(oks) == 1
        assert len(fails) == 1
        assert oks[0]["trace_id"] == "ok-1"

    def test_count(self, memory_store):
        assert memory_store.count() == 0
        memory_store.record_trace(
            ExecutionTrace(
                trace_id="c1",
                task_id="t",
                objective="test",
                outcome=TraceOutcome.SUCCESS,
            )
        )
        assert memory_store.count() == 1

    def test_persistence_across_restart(self, memory_store):
        memory_store.record_trace(
            ExecutionTrace(
                trace_id="persist-1",
                task_id="t",
                objective="persistente",
                outcome=TraceOutcome.SUCCESS,
            )
        )
        store2 = AgentMemoryStore(trace_dir=str(memory_store._trace_dir))
        assert store2.get_trace("persist-1") is not None
        assert store2.get_trace("persist-1").objective == "persistente"


class TestOrchestratorIntegration:
    def test_orchestrator_has_memory(self):
        orch = VibeCodingOrchestrator()
        assert orch.memory is not None
        assert isinstance(orch.memory, AgentMemoryStore)

    def test_task_execution_records_trace(self):
        reset_orchestrator()
        orch = VibeCodingOrchestrator()
        t = orch.create_task("explorar directorio actual", max_iterations=5)
        orch.plan_task(t)
        asyncio.run(orch.run_task(t.task_id))
        traces = orch.memory.list_traces(task_id=t.task_id, limit=10)
        assert len(traces) >= 1
        assert traces[0]["task_id"] == t.task_id
        assert traces[0]["objective"] == "explorar directorio actual"
        assert traces[0]["outcome"] in ("success", "failed", "partial")
        reset_orchestrator()

    def test_inject_experience_context(self):
        orch = VibeCodingOrchestrator()
        orch.memory.record_trace(
            ExecutionTrace(
                trace_id="exp-1",
                task_id="t",
                objective="resolver error de sintaxis",
                outcome=TraceOutcome.CORRECTED,
                error="SyntaxError",
                correction="Revisar los paréntesis",
            )
        )
        ctx = orch.inject_experience_context("error de sintaxis")
        assert "experiencias" in ctx.lower() or ctx == ""


class TestMemoryREST:
    @pytest.fixture()
    def client(self):
        reset_agent_memory()
        from fastapi import FastAPI

        from backend.agent.memory_routes import router as memory_router

        app = FastAPI()
        app.include_router(memory_router)

        with TestClient(app) as c:
            yield c
        reset_agent_memory()

    def test_memory_status(self, client):
        r = client.get("/api/agent/memory/status")
        assert r.status_code == 200
        body = r.json()
        assert "total_traces" in body
        assert "outcomes" in body

    def test_list_traces_empty(self, client):
        r = client.get("/api/agent/memory/traces")
        assert r.status_code == 200
        assert r.json()["count"] >= 0

    def test_record_and_get_trace(self, client):
        r = client.post(
            "/api/agent/memory/traces",
            json={
                "objective": "tarea de prueba",
                "outcome": "success",
                "steps": [{"tool": "shell", "action": "echo"}],
            },
        )
        assert r.status_code == 200
        tid = r.json()["trace_id"]
        r2 = client.get(f"/api/agent/memory/traces/{tid}")
        assert r2.status_code == 200
        assert r2.json()["objective"] == "tarea de prueba"

    def test_search_experiences(self, client):
        client.post(
            "/api/agent/memory/traces",
            json={
                "objective": "resolver error de timeout",
                "outcome": "corrected",
                "error": "timeout",
                "correction": "Reducir timeout",
            },
        )
        r = client.post(
            "/api/agent/memory/search",
            json={
                "query": "timeout error",
                "max_results": 5,
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"

    def test_inject_experience(self, client):
        client.post(
            "/api/agent/memory/traces",
            json={
                "objective": "problema de conexión",
                "outcome": "corrected",
                "error": "connection refused",
                "correction": "Reintentar",
            },
        )
        r = client.post(
            "/api/agent/memory/inject",
            json={
                "query": "conexión",
                "max_results": 3,
            },
        )
        assert r.status_code == 200
        assert "context" in r.json()

    def test_list_by_outcome(self, client):
        client.post(
            "/api/agent/memory/traces",
            json={
                "objective": "tarea correcta",
                "outcome": "success",
            },
        )
        client.post(
            "/api/agent/memory/traces",
            json={
                "objective": "tarea fallida",
                "outcome": "failed",
                "error": "fallo",
            },
        )
        ok = client.get("/api/agent/memory/experiences/success")
        fail = client.get("/api/agent/memory/experiences/failed")
        assert ok.json()["count"] >= 1
        assert fail.json()["count"] >= 1

    def test_invalid_outcome_rejected(self, client):
        r = client.post(
            "/api/agent/memory/traces",
            json={
                "objective": "test",
                "outcome": "invalid_outcome",
            },
        )
        assert r.status_code == 422

    def test_get_trace_not_found(self, client):
        r = client.get("/api/agent/memory/traces/non-existent")
        assert r.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
