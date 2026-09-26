"""BLOQUE 63 — Kilo integration tests: research tools + REST routes.

Verifica que Kilo/AME puedan invocar las herramientas de investigacion
(research.missions.start / get / list / engine.status) y los endpoints
/api/agent/research, usando un motor ligero (sin dependencias vectoriales
pesadas) para mantener la suite rapida.

Aislamiento: este archivo se mantiene separado de tests/test_block63.py para no
solaparse con ediciones concurrentes del archivo principal.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.agent.deep_research import (
    DeepResearchEngine,
    SourceFetcher,
    reset_research_engine,
)

# --------------------------------------------------------------------------- #
# Doble de memoria ligera
# --------------------------------------------------------------------------- #


class FakeMemory:
    def __init__(self) -> None:
        self.records: List[Dict[str, Any]] = []

    def remember(
        self, text, memory_type="episodic", source="user", session_id="", metadata=None
    ) -> Dict[str, Any]:
        mid = f"mem_{len(self.records)}"
        self.records.append(
            {
                "memory_id": mid,
                "text": text,
                "memory_type": memory_type,
                "source": source,
                "metadata": metadata or {},
            }
        )
        return {"status": "ok", "memory_id": mid, "type": memory_type}

    def search(self, query, max_results=5, min_relevance=0.1) -> Dict[str, Any]:
        q = query.lower()
        results = [r for r in self.records if q in r["text"].lower()][:max_results]
        return {"status": "ok", "count": len(results), "results": results}

    def get_status(self) -> Dict[str, Any]:
        return {"total_memories": len(self.records)}


def _offline_fetch(url, timeout=10) -> Optional[str]:
    return None  # Sin red: el pipeline usa seed_texts inyectados.


def _build_engine(tmp_path) -> DeepResearchEngine:
    return DeepResearchEngine(
        memory_engine=FakeMemory(),
        fetcher=SourceFetcher(fetch=_offline_fetch),
        storage_dir=str(tmp_path / "research"),
    )


@pytest.fixture
def engine(tmp_path):
    reset_research_engine()
    yield _build_engine(tmp_path)
    reset_research_engine()


# --------------------------------------------------------------------------- #
# Tools registradas en el DynamicToolRegistry
# --------------------------------------------------------------------------- #


def test_research_tools_are_registered_by_scan(tmp_path):
    from backend.agents.tools_registry import DynamicToolRegistry, reset_tools_registry

    reset_tools_registry()
    try:
        reg = DynamicToolRegistry()
        reg.scan()
        names = {t["name"] for t in reg.list_tools()}
        assert "research.missions.start" in names
        assert "research.missions.get" in names
        assert "research.missions.list" in names
        assert "research.engine.status" in names
    finally:
        reset_tools_registry()


def test_research_tools_module_exposes_tools_dict():
    from backend.agents.tools import research_tools

    tools = research_tools.TOOLS
    assert isinstance(tools, dict)
    assert set(tools) >= {"research.missions.start", "research.missions.get"}
    for entry in tools.values():
        assert callable(entry["func"])
        assert entry["risk"] == "safe"
        assert isinstance(entry["parameters"], dict)


# --------------------------------------------------------------------------- #
# Ejecucion de tools (motor inyectado)
# --------------------------------------------------------------------------- #


def test_start_tool_completes_mission(tmp_path, monkeypatch):
    import backend.agents.tools.research_tools as mod

    eng = _build_engine(tmp_path)
    monkeypatch.setattr(mod, "get_research_engine", lambda: eng)
    out = mod._start_research(
        question="Aprendizaje automatico y su historia",
        seed_texts=[
            "El aprendizaje automatico es una subdisciplina clave de la inteligencia artificial."
        ],
    )
    assert out["status"] == "completed"
    assert out["mission_id"]
    assert out["knowledge_map"]["coverage"] is not None


def test_get_and_list_tools(tmp_path, monkeypatch):
    import backend.agents.tools.research_tools as mod

    eng = _build_engine(tmp_path)
    monkeypatch.setattr(mod, "get_research_engine", lambda: eng)
    mid = mod._start_research(question="Redes neuronales profundas importadas a la AI")[
        "mission_id"
    ]
    g = mod._get_research(mid)
    assert g["found"] is True
    assert g["mission_id"] == mid
    lst = mod._list_research(status="completed")
    assert lst["count"] >= 1
    st = mod._research_status()
    assert "total_missions" in st


# --------------------------------------------------------------------------- #
# Endpoints REST contra el motor ampliado
# --------------------------------------------------------------------------- #


def test_rest_flows(tmp_path, monkeypatch):
    import backend.agent.research_routes as rr
    from backend.agent.research_routes import router

    eng = _build_engine(tmp_path)
    monkeypatch.setattr(rr, "get_research_engine", lambda: eng)

    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        created = client.post(
            "/api/agent/research/missions",
            json={
                "question": "Historia del aprendizaje automatico",
                "seed_texts": [
                    "El aprendizaje automatico evoluciono con las redes neuronales profundas."
                ],
            },
        )
        assert created.status_code == 200
        mid = created.json()["mission_id"]

        detail = client.get(f"/api/agent/research/missions/{mid}")
        assert detail.status_code == 200
        assert detail.json()["mission_id"] == mid

        k = client.get(f"/api/agent/research/missions/{mid}/knowledge")
        assert k.status_code == 200
        assert "knowledge_map" in k.json()

        lst = client.get("/api/agent/research/missions?status=completed")
        assert lst.status_code == 200
        assert lst.json()["count"] >= 1

        hist = client.get("/api/agent/research/history")
        assert hist.status_code == 200
        assert hist.json()["count"] >= 1

        st = client.get("/api/agent/research/status")
        assert st.status_code == 200
        assert "missions_by_status" in st.json()

        miss404 = client.get("/api/agent/research/missions/not-exist")
        assert miss404.status_code == 404


# --------------------------------------------------------------------------- #
# Higiene: sin cloud, sin tokens
# --------------------------------------------------------------------------- #


def test_no_cloud_or_tokens_in_research_tools():
    import backend.agents.tools.research_tools as mod

    src = open(mod.__file__, encoding="utf-8").read()
    for bad in (
        "boto3",
        "azure",
        "google.cloud",
        "sentry_sdk",
        "openai",
        "groq",
        "access_token=",
        "api_key=",
        "secret=",
    ):
        assert bad not in src, f"found forbidden token/dependency: {bad}"


def test_deep_research_compatible_with_kilo_engine(tmp_path):
    """Confirmamos que los campos usados por las tools siguen presentes en el
    motor ampliado por Kilo (delete_mission, refinement_rounds en el mapa)."""
    import inspect

    from backend.agent import deep_research

    sig = inspect.signature(deep_research.DeepResearchEngine.start_mission)
    params = set(sig.parameters)
    assert {"question", "sources", "seed_texts", "max_refine_depth"} <= params
    assert hasattr(deep_research.DeepResearchEngine, "delete_mission")
