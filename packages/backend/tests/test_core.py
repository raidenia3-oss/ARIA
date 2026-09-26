# -*- coding: utf-8 -*-
"""AURA OS - Chunk 3: Tests del nucleo (Chunks 1-3).

Escenarios:
  - Chat simple (flujo completo input -> analyzer -> decision)
  - Decision multi-paso (orquestador asigna y ejecuta agentes)
  - Error handling (input vacio, plan invalido, errores de agentes)
  - Memoria (corto/medio/largo, busqueda, patrones)
  - Seguridad (credenciales, auditoria)
"""
from __future__ import annotations

import asyncio
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.core_routes import router as core_router, ws_router
from backend.core.decision_engine import reset_decision_engine
from backend.core.event_bus import get_event_bus, reset_event_bus
from backend.core.models import Decision, DecisionStep, DecisionType
from backend.core.orchestrator import get_orchestrator, reset_orchestrator
from backend.memory.memory_manager import get_memory_manager, reset_memory_manager

# Aislar datos de test
os.environ.setdefault("AURA_DATA_DIR", "data/memory_test")


@pytest.fixture(autouse=True)
def _reset_all():
    reset_memory_manager()
    reset_orchestrator()
    reset_decision_engine()
    reset_event_bus()
    yield
    reset_memory_manager()
    reset_orchestrator()
    reset_decision_engine()
    reset_event_bus()


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(core_router)
    app.include_router(ws_router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Escenario 1: chat simple (Chunk 1 + flujo unificado)
# ---------------------------------------------------------------------------

def test_chat_simple_flujo_completo(client: TestClient) -> None:
    resp = client.post("/api/core/process", json={"input": "Hola", "type": "chat"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["flow"] == ["input", "analyzer", "decision_engine"]
    assert body["decision"]["engine"] in {"jan", "local_fallback"}
    types = {e["type"] for e in body["events"]}
    assert "input" in types and "result" in types


def test_chat_simple_status_ok(client: TestClient) -> None:
    client.post("/api/core/process", json={"input": "Hola", "type": "chat"})
    resp = client.get("/api/core/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok" and body["chunk"] == 1


# ---------------------------------------------------------------------------
# Escenario 2: decision multi-paso (Chunk 2, orquestador + agentes)
# ---------------------------------------------------------------------------

def test_decision_multi_paso_orquestador() -> None:
    o = get_orchestrator()
    dec = Decision(type=DecisionType.PLAN, plan=[
        DecisionStep(step=1, description="buscar en memoria", agent="rag_agent", tool="memory"),
        DecisionStep(step=2, description="ejecutar accion", agent="executor_agent", tool="execute"),
    ], agents=["rag_agent", "executor_agent"], priority=0.7)
    r = asyncio.run(o.execute_decision(dec, "s-multi"))
    assert r["status"] == "completed"
    assert len(r["steps"]) == 2
    assert all(s["status"] == "completed" for s in r["steps"])
    st = o.get_status("s-multi")
    assert st["completed"] == 2 and st["progress"] == 100.0


def test_decision_multi_paso_emite_eventos() -> None:
    reset_event_bus()
    bus = get_event_bus()
    o = get_orchestrator()
    dec = Decision(type=DecisionType.PLAN, plan=[
        DecisionStep(step=1, description="paso uno", agent="executor_agent", tool="execute"),
    ], agents=["executor_agent"])
    asyncio.run(o.execute_decision(dec, "s-events"))
    types = [e.type for e in bus._history]
    assert "action" in types
    assert "agent_start" in types
    assert "agent_end" in types
    assert "complete" in types


# ---------------------------------------------------------------------------
# Escenario 3: error handling
# ---------------------------------------------------------------------------

def test_error_input_vacio(client: TestClient) -> None:
    resp = client.post("/api/core/process", json={"input": "  ", "type": "chat"})
    assert resp.status_code == 400


def test_error_agente_inexistente_degrada() -> None:
    o = get_orchestrator()
    dec = Decision(type=DecisionType.PLAN, plan=[
        DecisionStep(step=1, description="paso con agente fantasma", agent="agente_fantasma"),
    ], agents=[])
    r = asyncio.run(o.execute_decision(dec, "s-err"))
    assert r["steps"][0]["status"] == "completed"


def test_error_reset_limpia_todo(client: TestClient) -> None:
    client.post("/api/core/process", json={"input": "Hola", "type": "chat"})
    assert get_event_bus().recent(10)
    resp = client.post("/api/core/reset")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert get_event_bus().recent(10) == []


# ---------------------------------------------------------------------------
# Chunk 3: memoria
# ---------------------------------------------------------------------------

def test_memoria_corto_mediano_largo() -> None:
    mm = get_memory_manager()
    mm.set_session("test-mem")
    for i in range(3):
        mm.add_short_term("user", f"mensaje {i}")
    assert len(mm.get_short_term()) == 3

    from backend.memory.memory_manager import ConversationEntry
    mm.add_medium_term(ConversationEntry(role="user", content="persistido"))
    assert any("persistido" in d.get("content", "") for d in mm.get_medium_term("test-mem"))

    mm.add_long_term_pattern("cuando pide hora", "responde hora")
    pats = mm.get_long_term_patterns(top_k=5)
    assert pats and pats[0].frequency >= 1


def test_memoria_busqueda_semantica() -> None:
    mm = get_memory_manager()
    mm.set_session("test-search")
    mm.add_short_term("user", "como esta el clima hoy")
    mm.add_short_term("assistant", "el clima esta soleado")
    hits = mm.search("clima", top_k=3)
    assert hits
    assert all(h["similarity"] >= 0.0 for h in hits)
    ctx = mm.get_context("clima")
    assert "hits" in ctx and "short_term_size" in ctx


def test_memoria_limite_short_term() -> None:
    mm = get_memory_manager()
    mm.set_session("test-limit")
    for i in range(25):  # limite 20
        mm.add_short_term("user", f"m{i}")
    assert len(mm.get_short_term()) == 20
    assert mm.get_short_term()[0].content == "m5"


# ---------------------------------------------------------------------------
# Chunk 3: seguridad (auditoria)
# ---------------------------------------------------------------------------

def test_seguridad_audit_logger() -> None:
    from backend.core.security import AuditLogger
    al = AuditLogger()
    al.log_event("test_event", {"detail": "prueba"})
    events = al.get_events(limit=10)
    assert any(e.get("type") == "test_event" for e in events)
    chain = al.verify_chain()
    assert chain.get("valid") is True


# ---------------------------------------------------------------------------
# Endpoint generate-code (autoprompteo, Chunk 1/4)
# ---------------------------------------------------------------------------

def test_generate_code_prompt_legacy(client: TestClient) -> None:
    resp = client.get("/api/core/generate-code",
                      params={"description": "resumen de documentos", "kind": "prompt"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "prompt"
    assert "resumen de documentos" in body["prompt"]
    assert body["target_path"].startswith("backend/")


def test_generate_code_route_legacy(client: TestClient) -> None:
    resp = client.get("/api/core/generate-code",
                      params={"description": "Resumen de Documentos", "kind": "route", "name": "resumen_docs"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["target_path"] == "backend/api/resumen_docs_routes.py"
    assert "APIRouter" in body["code"]
    assert "ResumenDocs" in body["code"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))