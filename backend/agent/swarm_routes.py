"""AURA Local Multi-Agent Swarm REST endpoints (Bloque 64).

Router complementario bajo el prefijo contractual ``/api/agent/swarm``: expone
el ``AgentSwarmManager`` local para iniciar, sincronizar y supervisar en tiempo
real los sub-agentes paralelos (colas async, bus inter-agente y estado).

Sin dependencias de orquestacion cloud (Kubernetes/AWS ECS/etc.): todo funciona
en hilos/processos locales sobre el hardware del usuario.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.agent_swarm import AgentSwarmManager, get_swarm_manager

logger = logging.getLogger("AURA.Agent.Swarm.Routes")

router = APIRouter(prefix="/api/agent/swarm", tags=["agent-swarm"])


def _mgr() -> AgentSwarmManager:
    return get_swarm_manager()


class SubmitSwarmRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=4000)
    priority: str = Field(default="normal", pattern="^(low|normal|high|critical)$")
    max_subtasks: Optional[int] = Field(default=None, ge=1, le=20)
    execute: bool = False


class PublishRequest(BaseModel):
    src_agent: str = Field(..., min_length=1, max_length=100)
    topic: str = Field(..., min_length=1, max_length=200)
    payload: Dict[str, Any] = Field(default_factory=dict)
    dst_agent: Optional[str] = None


@router.post("/tasks")
async def submit_swarm_task(payload: SubmitSwarmRequest) -> Dict[str, Any]:
    """Inicia una mision de enjambre: descompone la descripcion y opcionalmente
    ejecuta el plan en paralelo."""
    mgr = _mgr()
    try:
        plan = await mgr.submit_task(
            description=payload.description,
            priority=payload.priority,
            max_subtasks=payload.max_subtasks,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not payload.execute:
        return plan
    exec_result = await mgr.execute_plan(plan["plan_id"], concurrent=True)
    return {
        "status": "executed",
        "plan_id": plan["plan_id"],
        "plan": plan,
        "execution": exec_result,
    }


@router.get("/tasks")
async def list_swarm_tasks(
    plan_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
) -> Dict[str, Any]:
    tasks = _mgr().list_tasks(plan_id=plan_id, limit=limit)
    return {"count": len(tasks), "tasks": tasks}


@router.post("/tasks/{plan_id}/execute")
async def execute_swarm_plan(
    plan_id: str,
    concurrent: bool = True,
) -> Dict[str, Any]:
    """Sincroniza y ejecuta el plan en paralelo (muro de agentes)."""
    result = await _mgr().execute_plan(plan_id, concurrent=concurrent)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail="plan_not_found")
    return result


@router.get("/agents")
async def list_swarm_agents() -> Dict[str, Any]:
    """Supervisa los sub-agentes activos del enjambre."""
    agents = _mgr().list_agents()
    return {"active_agents": len(agents), "agents": agents}


@router.get("/status")
async def swarm_status() -> Dict[str, Any]:
    """Estado de actividad del enjambre en tiempo real (cola, bus, tareas)."""
    return _mgr().get_status()


@router.get("/bus")
async def swarm_bus_messages(limit: int = Query(50, ge=1, le=500)) -> Dict[str, Any]:
    messages = _mgr().get_bus_messages(limit=limit)
    return {"count": len(messages), "messages": messages}


@router.post("/publish")
async def swarm_publish(payload: PublishRequest) -> Dict[str, Any]:
    """Publica un mensaje en el bus inter-agente (sincronizacion)."""
    try:
        published = await _mgr().publish(
            payload.src_agent,
            payload.topic,
            payload.payload,
            dst_agent=payload.dst_agent,
        )
        return {"status": "published", "message": published}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/infrastructure/start")
async def swarm_infrastructure_start() -> Dict[str, Any]:
    return await _mgr().start_infrastructure()


@router.post("/infrastructure/stop")
async def swarm_infrastructure_stop() -> Dict[str, Any]:
    return await _mgr().stop_infrastructure()


__all__ = ["router"]