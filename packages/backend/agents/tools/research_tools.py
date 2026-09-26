from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.agent.deep_research import get_research_engine


def _engine():
    return get_research_engine()


def _start_research(
    question: str,
    sources: Optional[List[str]] = None,
    seed_texts: Optional[List[str]] = None,
    max_refine_depth: Optional[int] = None,
) -> dict:
    """Inicia una mision de investigacion autonoma (Bloque 63)."""
    engine = _engine()
    mission = engine.start_mission(
        question=question,
        sources=sources or [],
        seed_texts=seed_texts or [],
        max_refine_depth=max_refine_depth,
        metadata={"origin": "kilo_tool"},
    )
    d = mission.to_dict()
    return {
        "mission_id": d["mission_id"],
        "question": d["question"],
        "status": d["status"],
        "sub_questions": d["sub_questions"],
        "knowledge_map": d["knowledge_map"],
        "memory_ids": d["memory_ids"],
        "error": d["error"],
    }


def _get_research(mission_id: str) -> dict:
    """Consulta el detalle y el mapa de conocimiento de una mision."""
    mission = _engine().get_mission(mission_id)
    if not mission:
        return {"found": False, "mission_id": mission_id}
    d = mission.to_dict()
    return {
        "found": True,
        "mission_id": d["mission_id"],
        "question": d["question"],
        "status": d["status"],
        "sub_questions": d["sub_questions"],
        "sources_indexed": d["knowledge_map"].get("sources_indexed", 0),
        "concept_count": d["knowledge_map"].get("concept_count", 0),
        "coverage": d["knowledge_map"].get("coverage", 0.0),
        "summary": d["knowledge_map"].get("summary", ""),
        "memory_ids": d["memory_ids"],
    }


def _list_research(limit: int = 20, status: str = "") -> dict:
    """Lista las misiones de investigacion y su estado (historial de aprendizaje)."""
    missions = _engine().list_missions(status=status or None, limit=limit)
    return {"count": len(missions), "missions": missions}


def _research_status() -> dict:
    """Estado global del motor de investigacion y memoria aprendida."""
    return _engine().get_status()


TOOLS = {
    "research.missions.start": {
        "description": (
            "Inicia una mision de investigacion autonoma sobre cualquier tema, "
            "descomponiendola en sub-consultas, explorando fuentes y absorbiendo "
            "el conocimiento en la memoria de largo plazo. Devuelve mapa de conocimiento."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Pregunta o tema complejo a investigar."},
                "sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                    "description": "URLs publicas opcionales a indexar.",
                },
                "seed_texts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                    "description": "Textos locales opcionales a sintetizar.",
                },
                "max_refine_depth": {"type": "integer", "default": 2},
            },
            "required": ["question"],
        },
        "category": "research",
        "risk": "safe",
        "func": _start_research,
    },
    "research.missions.get": {
        "description": "Consulta el detalle y mapa de conocimiento de una mision de investigacion ya realizada.",
        "parameters": {
            "type": "object",
            "properties": {"mission_id": {"type": "string"}},
            "required": ["mission_id"],
        },
        "category": "research",
        "risk": "safe",
        "func": _get_research,
    },
    "research.missions.list": {
        "description": "Lista las misiones de investigacion realizadas y su estado (historial de aprendizaje).",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 20},
                "status": {"type": "string", "default": "", "description": "Filtro opcional por estado."},
            },
            "required": [],
        },
        "category": "research",
        "risk": "safe",
        "func": _list_research,
    },
    "research.engine.status": {
        "description": "Estado global del motor de investigacion autonoma y de la memoria de conocimiento aprendido.",
        "parameters": {"type": "object", "properties": {}, "required": []},
        "category": "research",
        "risk": "safe",
        "func": _research_status,
    },
}