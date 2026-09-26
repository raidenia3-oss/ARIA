"""AURA Local Autonomous Task Orchestrator — REST + WebSocket endpoints (Bloque 55)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from backend.agents.orchestrator import TaskStatus, VibeCodingOrchestrator, vibe_orchestrator

logger = logging.getLogger("AURA.Agent.Orchestrator.Routes")

router = APIRouter(prefix="/api/agent", tags=["agent-orchestrator"])


def _check_api_key(provided: Optional[str]) -> None:
    expected = os.getenv("AURA_API_KEY", "")
    if expected and provided != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


def _summary(task_id: str) -> Optional[Dict[str, Any]]:
    task = vibe_orchestrator.get_task(task_id)
    if not task:
        return None
    return vibe_orchestrator.status_dict(task)


class CreateTaskRequest(BaseModel):
    objective: str = Field(..., min_length=1, max_length=2000)
    context: Dict[str, Any] = Field(default_factory=dict)
    max_iterations: int = Field(10, ge=1, le=50)
    execute: bool = Field(False)


@router.get("/status")
async def orchestrator_status(x_api_key: Optional[str] = None) -> Dict[str, Any]:
    return vibe_orchestrator.status()


@router.post("/tasks")
async def create_task(
    payload: CreateTaskRequest,
    x_api_key: Optional[str] = None,
) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    task = vibe_orchestrator.create_task(
        objective=payload.objective,
        context=payload.context,
        max_iterations=payload.max_iterations,
    )
    vibe_orchestrator.plan_task(task)
    if payload.execute:
        await vibe_orchestrator.run_task(task.task_id)
    return _summary(task.task_id) or {}


@router.get("/tasks")
async def list_tasks(
    status: Optional[str] = None,
    limit: int = 50,
    x_api_key: Optional[str] = None,
) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    tasks = vibe_orchestrator.list_tasks(status=status)[:limit]
    return {"count": len(tasks), "tasks": [_summary(t.task_id) for t in tasks if t.task_id]}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, x_api_key: Optional[str] = None) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    summary = _summary(task_id)
    if not summary:
        raise HTTPException(status_code=404, detail="task_not_found")
    return summary


@router.post("/tasks/{task_id}/run")
async def run_task(task_id: str, x_api_key: Optional[str] = None) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    try:
        await vibe_orchestrator.run_task(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="task_not_found")
    return _summary(task_id) or {}


@router.post("/tasks/{task_id}/pause")
async def pause_task(task_id: str, x_api_key: Optional[str] = None) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    ok = await vibe_orchestrator.pause_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="task_not_found_or_not_running")
    return _summary(task_id) or {}


@router.post("/tasks/{task_id}/resume")
async def resume_task(task_id: str, x_api_key: Optional[str] = None) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    ok = await vibe_orchestrator.resume_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="task_not_found_or_not_paused")
    return _summary(task_id) or {}


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str, x_api_key: Optional[str] = None) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    ok = await vibe_orchestrator.cancel_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="task_not_found")
    return _summary(task_id) or {}


@router.post("/tasks/{task_id}/retry")
async def retry_task(
    task_id: str,
    max_iterations: Optional[int] = None,
    x_api_key: Optional[str] = None,
) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    ok = await vibe_orchestrator.retry_task(task_id, max_iterations=max_iterations)
    if not ok:
        raise HTTPException(status_code=404, detail="task_not_found")
    return _summary(task_id) or {}


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, x_api_key: Optional[str] = None) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    ok = vibe_orchestrator.delete_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="task_not_found")
    return {"status": "ok", "task_id": task_id}


@router.websocket("/stream")
async def agent_stream_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        await websocket.send_json({"event": "connected", "status": vibe_orchestrator.status()})
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                await websocket.send_json({"event": "ping"})
                continue
            except WebSocketDisconnect:
                break
            try:
                data = json.loads(msg) if isinstance(msg, str) else msg
            except Exception:
                data = {"raw": msg}
            cmd = data.get("action") or data.get("cmd") or ""
            if cmd == "create":
                task = vibe_orchestrator.create_task(
                    objective=str(data.get("objective", "")),
                    context=data.get("context") or {},
                    max_iterations=int(data.get("max_iterations", 10)),
                )
                vibe_orchestrator.plan_task(task)
                await vibe_orchestrator.run_task(task.task_id)
                await websocket.send_json({"event": "task_done", "summary": _summary(task.task_id)})
            elif cmd == "run":
                tid = str(data.get("task_id", ""))
                await vibe_orchestrator.run_task(tid)
                await websocket.send_json({"event": "task_done", "summary": _summary(tid)})
            elif cmd == "status":
                await websocket.send_json({"event": "status", "status": vibe_orchestrator.status()})
            elif cmd == "pause":
                await vibe_orchestrator.pause_task(str(data.get("task_id", "")))
            elif cmd == "resume":
                await vibe_orchestrator.resume_task(str(data.get("task_id", "")))
            elif cmd == "cancel":
                await vibe_orchestrator.cancel_task(str(data.get("task_id", "")))
            elif cmd == "retry":
                await vibe_orchestrator.retry_task(str(data.get("task_id", "")))
            elif cmd == "delete":
                vibe_orchestrator.delete_task(str(data.get("task_id", "")))
            else:
                await websocket.send_json({"event": "ack", "received": data})
    except WebSocketDisconnect:
        pass