"""Swarm & GUI automation routes for AURA - Module 28."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Path, Query
from fastapi.responses import JSONResponse

from backend.agent_swarm import AgentRole, SubAgentTask, AgentSwarmManager
from backend.agents.agent_roles import (
    APEXAgentRole,
    RoleSpec,
    get_all_roles,
    get_role_spec,
    role_to_dict,
)
from backend.gui_automation_engine import ActionPayload, Coordinates, ComputerUseAgent

router = APIRouter(prefix="/api", tags=["swarm", "gui"])

swarm = AgentSwarmManager()
computer = ComputerUseAgent()


# --------------------------------------------------------------------------- #
#  Swarm Tasks                                                                 #
# --------------------------------------------------------------------------- #
@router.post("/swarm/tasks")
async def submit_task(
    payload: Dict[str, Any] = Body(
        ...,
        json_schema_extra={
            "example": {
                "description": "Plan and code a Python REST API. Review and evaluate the result.",
                "priority": "normal",
                "max_subtasks": 5,
                "execute": True,
            }
        },
    ),
) -> Dict[str, Any]:
    description = str(payload.get("description", ""))
    if not description:
        raise HTTPException(status_code=400, detail="description is required")

    priority = str(payload.get("priority", "normal"))
    max_subtasks = payload.get("max_subtasks")
    execute = bool(payload.get("execute", False))

    plan_result = await swarm.submit_task(description, priority=priority, max_subtasks=max_subtasks)

    if execute:
        plan_id = plan_result["plan_id"]
        exec_result = await swarm.execute_plan(plan_id, concurrent=True)
        return {
            "status": "executed",
            "plan_id": plan_id,
            "plan": plan_result,
            "execution": exec_result,
        }

    return {
        "status": "planned",
        "plan_id": plan_result["plan_id"],
        "task_count": plan_result["task_count"],
        "validation": plan_result["validation"],
        "tasks": plan_result["tasks"],
    }


@router.get("/swarm/tasks")
async def list_tasks(
    plan_id: Optional[str] = Query(None, description="Filter by plan ID"),
    limit: int = Query(50, ge=1, le=500),
) -> Dict[str, Any]:
    tasks = swarm.list_tasks(plan_id=plan_id, limit=limit)
    return {"count": len(tasks), "tasks": tasks}


@router.post("/swarm/tasks/{plan_id}/execute")
async def execute_plan(
    plan_id: str = Path(..., description="Plan ID to execute"),
    payload: Dict[str, Any] = Body(None, json_schema_extra={"example": {"concurrent": True}}),
) -> Dict[str, Any]:
    concurrent = bool((payload or {}).get("concurrent", True))
    if plan_id not in swarm.task_plans:
        raise HTTPException(status_code=404, detail="plan_not_found")
    result = await swarm.execute_plan(plan_id, concurrent=concurrent)
    return result


@router.get("/swarm/status")
async def swarm_status() -> Dict[str, Any]:
    return swarm.get_status()


# --------------------------------------------------------------------------- #
#  Local parallel infrastructure (Bloque 64)                                     #
# --------------------------------------------------------------------------- #

@router.post("/swarm/infra/start")
async def swarm_infra_start() -> Dict[str, Any]:
    return await swarm.start_infrastructure()


@router.post("/swarm/infra/stop")
async def swarm_infra_stop() -> Dict[str, Any]:
    return await swarm.stop_infrastructure()


@router.get("/swarm/infra/queue")
async def swarm_queue_status() -> Dict[str, Any]:
    return swarm.get_queue_status()


@router.post("/swarm/bus/publish")
async def swarm_bus_publish(payload: Dict[str, Any]) -> Dict[str, Any]:
    src = str(payload.get("src_agent", "aura"))
    topic = str(payload.get("topic", "system"))
    data = payload.get("payload") or {}
    dst = payload.get("dst_agent")
    return await swarm.publish(src, topic, data, dst)


@router.get("/swarm/bus/messages")
async def swarm_bus_messages(limit: int = Query(50, ge=1, le=500)) -> Dict[str, Any]:
    return {"count": len(swarm.get_bus_messages(limit)),
            "messages": swarm.get_bus_messages(limit)}


@router.post("/swarm/queue/enqueue")
async def swarm_queue_enqueue(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Enqueues a no-op coroutine task for testing the worker pool."""
    async def _noop(x: int) -> int:
        await asyncio.sleep(0.01)
        return x * 2

    val = int(payload.get("value", 1))
    priority = int(payload.get("priority", 0))
    task_id = await swarm.enqueue_task(_noop, val, priority=priority)
    return {"task_id": task_id, "value": val}


@router.get("/swarm/queue/wait/{task_id}")
async def swarm_queue_wait(task_id: str,
                            timeout: float = Query(10.0, ge=0.1, le=60.0)) -> Dict[str, Any]:
    try:
        result = await swarm.wait_task(task_id, timeout=timeout)
        return {"task_id": task_id, "status": "completed", "result": result}
    except TimeoutError:
        raise HTTPException(status_code=408, detail="timeout")


@router.get("/swarm/agents/{agent_id}/status")
async def agent_status(agent_id: str) -> Dict[str, Any]:
    agent = swarm.agents.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="agent_not_found")
    return agent


# --------------------------------------------------------------------------- #
#  Swarm Agents                                                                #
# --------------------------------------------------------------------------- #
@router.get("/swarm/agents")
async def list_agents() -> Dict[str, Any]:
    agents = swarm.list_agents()
    roles_available = [r.value for r in AgentRole]
    return {"count": len(agents), "agents": agents, "available_roles": roles_available}


@router.post("/swarm/agents")
async def create_agent(
    payload: Dict[str, Any] = Body(
        ...,
        json_schema_extra={
            "example": {"role": "coder", "config": {"model": "gpt-3.5-turbo", "max_iterations": 5}},
        },
    ),
) -> Dict[str, Any]:
    role = str(payload.get("role", "planner"))
    if role not in [r.value for r in AgentRole]:
        return JSONResponse(
            status_code=400,
            content={"error": f"invalid_role: {role}", "valid_roles": [r.value for r in AgentRole]},
        )
    config = payload.get("config") or {}
    agent = swarm.create_agent(role=role, config=config)
    return {"status": "created", "agent": agent}


@router.get("/swarm/metrics")
async def swarm_metrics() -> Dict[str, Any]:
    """Aggregate dispatch counters for every registered swarm agent."""
    return {"server": "ARIA", **swarm.get_swarm_metrics()}


@router.get("/swarm/agents/status")
async def swarm_agent_status() -> Dict[str, Any]:
    """APEX dashboard feed: per-agent lifecycle, role_spec and counters.

    The response is shaped for the React ``AgentStatusDashboard``: each entry
    carries the hex color and icon the orbit needs, plus the counters the
    detail cards render. Agents with no APEX role fall back to a neutral
    grey so the UI never shows an undefined color.
    """
    agents = swarm.list_agent_status()
    roles = [role_to_dict(r) for r in APEXAgentRole]
    return {
        "server": "ARIA-Axum-8002",
        "count": len(agents),
        "agents": agents,
        "available_roles": [r.value for r in APEXAgentRole],
        "role_specs": {r.value: role_to_dict(r) for r in APEXAgentRole},
    }


@router.get("/swarm/agents/{agent_id}/status")
async def swarm_agent_status_by_id(agent_id: str) -> Dict[str, Any]:
    """Single-agent status snapshot for the dashboard detail card."""
    snapshot = swarm.get_agent_status(agent_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="agent_not_found")
    return snapshot


@router.post("/swarm/agents/{agent_id}/heartbeat")
async def swarm_agent_heartbeat(agent_id: str) -> Dict[str, Any]:
    """Refresh an agent's heartbeat so the dashboard can tell live from stale."""
    ok = swarm.touch_agent(agent_id)
    if not ok:
        raise HTTPException(status_code=404, detail="agent_not_found")
    return {"status": "ok", "agent_id": agent_id}


@router.get("/swarm/roles")
async def swarm_roles() -> Dict[str, Any]:
    """APEX role catalogue: 12 roles with color, icon, description, capabilities."""
    return {
        "server": "ARIA-Axum-8002",
        "count": len(APEXAgentRole),
        "roles": [role_to_dict(r) for r in APEXAgentRole],
    }


@router.get("/swarm/history")
async def execution_history(limit: int = Query(50, ge=1, le=500)) -> Dict[str, Any]:
    history = swarm.execution_history[-limit:]
    return {"count": len(history), "history": history}


# --------------------------------------------------------------------------- #
#  GUI Automation                                                              #
# --------------------------------------------------------------------------- #
@router.get("/gui/screen-state")
async def screen_state() -> Dict[str, Any]:
    return computer.get_state()


@router.get("/gui/screen-describe")
async def describe_screen() -> Dict[str, Any]:
    analysis = await computer.describe_screen()
    return {"description": analysis, "timestamp": datetime.utcnow().isoformat() + "Z"}


@router.post("/gui/execute-action")
async def execute_action(
    payload: Dict[str, Any] = Body(
        ...,
        json_schema_extra={
            "example": {
                "action_type": "click",
                "coordinates": {"x": 1920 / 2, "y": 1080 / 2},
                "duration": 0.5,
                "delay": 0.0,
            }
        },
    ),
) -> Dict[str, Any]:
    action_type = str(payload.get("action_type", ""))
    if not action_type:
        raise HTTPException(status_code=400, detail="action_type is required")

    coords_data = payload.get("coordinates")
    coords = Coordinates(**coords_data) if isinstance(coords_data, dict) else None

    action = ActionPayload(
        action_type=action_type,
        coordinates=coords,
        text=payload.get("text"),
        key=payload.get("key"),
        key_combination=payload.get("key_combination"),
        scroll_amount=int(payload.get("scroll_amount", 0)),
        duration=float(payload.get("duration", 0.0)),
        delay=float(payload.get("delay", 0.0)),
        confirm=bool(payload.get("confirm", False)),
    )

    result = await computer.action_executor.execute(action)
    return {"status": "executed" if result.get("executed") else "failed", "result": result}


@router.post("/gui/command")
async def execute_command(
    payload: Dict[str, Any] = Body(
        ...,
        json_schema_extra={"example": {"command": "click 1920 1080"}},
    ),
) -> Dict[str, Any]:
    command = str(payload.get("command", ""))
    if not command:
        raise HTTPException(status_code=400, detail="command is required")
    result = await computer.execute_command(command)
    return result


# --------------------------------------------------------------------------- #
#  Unified Swarm Orchestrator + Self-Healing                                   #
# --------------------------------------------------------------------------- #
from backend.services.swarm_orchestrator import orchestrator as swarm_orchestrator
from backend.self_healing import self_healing, process_monitor, silent_reconnector


@router.get("/swarm/status")
async def swarm_status_unified() -> Dict[str, Any]:
    swarm_state = swarm.get_status()
    orchestrator_state = swarm_orchestrator.get_status()
    health = self_healing.health_report()
    process_status = process_monitor.status()
    return {
        "swarm": swarm_state,
        "orchestrator": orchestrator_state,
        "self_healing": health,
        "process_monitor": process_status,
    }


@router.post("/swarm/recover")
async def swarm_recover(module: str = "self_healing", reason: str = "manual_trigger") -> Dict[str, Any]:
    result = await self_healing.heal(module, reason=reason)
    return result


@router.post("/swarm/context")
async def update_swarm_context(payload: Dict[str, Any]) -> Dict[str, Any]:
    key = str(payload.get("key", ""))
    value = payload.get("value")
    if not key:
        raise HTTPException(status_code=400, detail="key is required")
    if key in ("memory", "vision", "actions"):
        swarm_orchestrator.append_context(key, value)
    else:
        swarm_orchestrator.update_context(key, value)
    return {"status": "ok", "key": key, "context": swarm_orchestrator.build_system_prompt()}


@router.get("/swarm/prompt")
async def get_swarm_prompt() -> Dict[str, Any]:
    prompt = swarm_orchestrator.build_system_prompt()
    return {"prompt": prompt, "length": len(prompt)}


@router.post("/swarm/model/fallback")
async def swarm_model_fallback(latency_hint: Optional[float] = None) -> Dict[str, Any]:
    model = await swarm_orchestrator.select_model(latency_hint=latency_hint)
    return {"selected_model": model}


@router.post("/swarm/ws/reconnect")
async def swarm_ws_reconnect(endpoint: str = "") -> Dict[str, Any]:
    if not endpoint:
        raise HTTPException(status_code=400, detail="endpoint is required")
    delay = silent_reconnector.next_delay(endpoint)
    success = False
    try:
        import requests as req
        latency_start = time.perf_counter()
        resp = req.get(endpoint, timeout=10)
        latency = time.perf_counter() - latency_start
        success = resp.status_code < 400
        process_monitor.record_ws_reconnect(endpoint, success, latency)
        if success:
            silent_reconnector.reset(endpoint)
    except Exception:
        process_monitor.record_ws_reconnect(endpoint, False, -1.0)
    return {"endpoint": endpoint, "success": success, "next_delay_sec": delay}

