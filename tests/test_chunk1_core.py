"""Chunk 1 — Núcleo básico: receiver hub, context analyzer, decision engine,
event bus, modelos Pydantic v2 y rutas /api/core/*.

100% local y soberano. No requiere Jan en marcha: el DecisionEngine
degrada a planner local (fallback) si http://localhost:1337/v1 no responde.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.core_routes import router as core_router
from backend.core.context_analyzer import get_context_analyzer, reset_context_analyzer
from backend.core.decision_engine import reset_decision_engine
from backend.core.event_bus import get_event_bus, reset_event_bus
from backend.core.models import Decision, DecisionStep, DecisionType, UnifiedInput
from backend.core.receiver_hub import get_receiver_hub, reset_receiver_hub


@pytest.fixture(autouse=True)
def _reset_core():
    """Aísla cada test: singletons limpios antes y después."""
    reset_receiver_hub()
    reset_context_analyzer()
    reset_decision_engine()
    reset_event_bus()
    yield
    reset_receiver_hub()
    reset_context_analyzer()
    reset_decision_engine()
    reset_event_bus()


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(core_router)
    return TestClient(app)


# ------------------------------------------------------------------
# GET /api/core/status
# ------------------------------------------------------------------


def test_status_devuelve_200_y_ok(client: TestClient) -> None:
    resp = client.get("/api/core/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["chunk"] == 1
    assert set(body["modules"]) == {
        "receiver_hub",
        "context_analyzer",
        "decision_engine",
        "event_bus",
        "models",
    }
    assert "jan" in body and "available" in body["jan"]


# ------------------------------------------------------------------
# POST /api/core/process
# ------------------------------------------------------------------


def test_process_chat_responde_y_recorre_flujo(client: TestClient) -> None:
    resp = client.post(
        "/api/core/process",
        json={"input": "Hola", "type": "chat", "session_id": "s1"},
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["ok"] is True
    assert body["flow"] == ["input", "analyzer", "decision_engine"]
    assert body["input_id"]
    assert body["session_id"] == "s1"

    analysis = body["analysis"]
    assert analysis["tipo"]
    assert analysis["dominio"]
    assert 0.0 <= float(analysis["urgencia"]) <= 1.0

    decision = body["decision"]
    assert decision["plan"], "el plan no puede estar vacío"
    assert decision["engine"] in {"jan", "local_fallback"}
    assert isinstance(decision["agents"], list)

    # el bus debe haber registrado input/decision/result
    types = {e["type"] for e in body["events"]}
    assert {"input", "result"} <= types


def test_process_input_vacio_devuelve_400(client: TestClient) -> None:
    resp = client.post("/api/core/process", json={"input": "   ", "type": "chat"})
    assert resp.status_code == 400
    assert "input" in resp.json()["detail"]


def test_process_deja_eventos_en_el_bus(client: TestClient) -> None:
    client.post("/api/core/process", json={"input": "estado del sistema", "type": "command"})
    events = get_event_bus().recent(50)
    assert events
    assert {e["type"] for e in events} & {"input", "thought", "decision", "result"}


# ------------------------------------------------------------------
# GET /api/core/generate-code (autoprompteo)
# ------------------------------------------------------------------


def test_generate_code_prompt(client: TestClient) -> None:
    resp = client.get(
        "/api/core/generate-code",
        params={"description": "motor de resumen de documentos", "kind": "prompt"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "prompt"
    assert "motor de resumen de documentos" in body["prompt"]
    assert body["code"] == ""
    assert body["target_path"].startswith("backend/")


def test_generate_code_route_devuelve_scaffolding(client: TestClient) -> None:
    resp = client.get(
        "/api/core/generate-code",
        params={"description": "Resumen de Documentos", "kind": "route", "name": "resumen_docs"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "route"
    assert body["target_path"] == "backend/api/resumen_docs_routes.py"
    assert "APIRouter" in body["code"]
    assert "<<SLUG>>" not in body["code"]
    assert "ResumenDocs" in body["code"]


def test_generate_code_kind_invalido_devuelve_400(client: TestClient) -> None:
    resp = client.get("/api/core/generate-code", params={"description": "algo", "kind": "nope"})
    assert resp.status_code == 400


# ------------------------------------------------------------------
# GET /api/core/events y POST /api/core/reset
# ------------------------------------------------------------------


def test_events_filtra_por_tipo(client: TestClient) -> None:
    client.post("/api/core/process", json={"input": "Hola", "type": "chat"})
    resp = client.get("/api/core/events", params={"event_type": "input"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] >= 1
    assert all(e["type"] == "input" for e in body["events"])


def test_reset_limpia_singletons(client: TestClient) -> None:
    client.post("/api/core/process", json={"input": "Hola", "type": "chat"})
    assert get_event_bus().recent(10)
    resp = client.post("/api/core/reset")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert get_event_bus().recent(10) == []


# ------------------------------------------------------------------
# Modelos, receiver hub, analyzer y decision engine
# ------------------------------------------------------------------


def test_modelos_pydantic_v2() -> None:
    inp = UnifiedInput(type="chat", content="hola", session_id="s")
    assert inp.input_id
    assert inp.to_event_data()["content"] == "hola"

    step = DecisionStep(step=1, description="hacer algo", agent="a", tool="execute")
    dec = Decision(type=DecisionType.PLAN, plan=[step], agents=["a"], priority=0.9)
    dumped = dec.model_dump()
    assert dumped["type"] == "plan"
    assert dumped["priority"] == 0.9
    # Pydantic v2 valida el rango (no recorta silenciosamente)
    with pytest.raises(Exception):
        Decision(priority=1.5)


def test_receiver_hub_unifica_canales_y_deduplica() -> None:
    hub = get_receiver_hub()
    evt_chat = hub.receive_chat("Hola mundo", session_id="s1")
    evt_voice = hub.receive_voice("abre el navegador", session_id="s1")
    evt_gesture = hub.receive_gesture("swipe_derecha", session_id="s1")
    evt_command = hub.receive_command("status", session_id="s1")
    evt_file = hub.receive_file("C:/tmp/a.txt", session_id="s1")

    assert [e.data["type"] for e in (evt_chat, evt_voice, evt_gesture, evt_command, evt_file)] == [
        "chat",
        "voice",
        "gesture",
        "command",
        "file",
    ]

    # duplicado inmediato se marca
    dup = hub.receive_chat("Hola mundo", session_id="s1")
    assert dup.data["duplicate"] is True

    stats = hub.stats()
    assert stats["total"] == 6
    assert stats["by_type"]["chat"] == 2
    assert len(hub.recent(5)) == 5


def test_context_analyzer_clasifica_urgencia_tipo_y_dominio() -> None:
    analyzer = get_context_analyzer()

    critico = analyzer.analyze("URGENTE! el servidor esta caido, error critico", "s2")
    assert critico["urgencia_nivel"] in {"high", "critical"}
    assert critico["dominio"] == "system"
    assert critico["contexto"]["enriched_prompt"]
    assert critico["context_size"] > 0

    archivo = analyzer.analyze("lee el archivo C:/tmp/a.txt", "s2")
    assert archivo["dominio"] == "files"

    web = analyzer.analyze("busca en internet el clima de hoy", "s2")
    assert web["dominio"] == "web"

    suave = analyzer.analyze("hola, buenos dias", "s2")
    assert suave["urgencia_nivel"] == "low"
    assert analyzer.last_analysis("s2") is not None


def test_decision_engine_siempre_produce_plan() -> None:
    """Con o sin Jan, el motor debe devolver un plan ejecutable."""
    from backend.core.decision_engine import get_decision_engine

    engine = get_decision_engine()
    out = engine.decide("analiza este documento y resume los puntos clave", {}, "s3")

    assert out["plan"]
    assert out["engine"] in {"jan", "local_fallback"}
    assert out["latency_ms"] >= 0.0
    for step in out["plan"]:
        assert step["step"] >= 1
        assert step["description"]
