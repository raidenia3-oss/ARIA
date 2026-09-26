"""Task routes for AURA/AME automation."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from backend.task_manager import task_manager
from backend.task_models import TaskModel, TaskStatus, TaskOrigin

router = APIRouter()
logger = logging.getLogger("AURATasks")


@router.post("/tasks")
async def create_task(payload: Dict[str, Any]) -> Dict[str, Any]:
    name = str(payload.get("name", "")).strip()
    action_type = str(payload.get("action_type", "")).strip()
    goal = str(payload.get("goal", "")).strip()
    origin = TaskOrigin(payload.get("origin", "aura"))
    parameters = payload.get("parameters", {})
    session_id = payload.get("session_id")
    metadata = payload.get("metadata", {})
    if not name or not action_type or not goal:
        raise HTTPException(status_code=422, detail="name, action_type and goal are required")
    task = await task_manager.create_task(
        name=name,
        action_type=action_type,
        goal=goal,
        origin=origin,
        parameters=parameters,
        session_id=session_id,
        metadata=metadata,
    )
    return task.model_dump()


@router.get("/tasks")
async def list_tasks(status: Optional[str] = None, origin: Optional[str] = None) -> Dict[str, Any]:
    st = TaskStatus(status) if status else None
    ori = TaskOrigin(origin) if origin else None
    tasks = await task_manager.list_tasks(status=st, origin=ori)
    return {"tasks": [t.model_dump() for t in tasks]}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str) -> Dict[str, Any]:
    task = await task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task_not_found")
    return task.model_dump()


@router.post("/tasks/{task_id}/start")
async def start_task(task_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    task = await task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task_not_found")
    steps = payload.get("steps") if payload else None
    ok = await task_manager.start_task(task_id, steps=steps)
    if not ok:
        raise HTTPException(status_code=400, detail="cannot_start_task")
    return {"started": True, "task_id": task_id}


@router.post("/tasks/{task_id}/pause")
async def pause_task(task_id: str) -> Dict[str, Any]:
    task = await task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task_not_found")
    ok = await task_manager.pause_task(task_id)
    if not ok:
        raise HTTPException(status_code=400, detail="cannot_pause_task")
    return {"paused": True, "task_id": task_id}


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str) -> Dict[str, Any]:
    task = await task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task_not_found")
    ok = await task_manager.cancel_task(task_id)
    if not ok:
        raise HTTPException(status_code=400, detail="cannot_cancel_task")
    return {"cancelled": True, "task_id": task_id}


@router.get("/automation/procedures")
async def list_procedures() -> Dict[str, Any]:
    procs = await task_manager.get_learned_procedures()
    return {"procedures": procs}


@router.post("/automation/procedures")
async def create_procedure(payload: Dict[str, Any]) -> Dict[str, Any]:
    name = str(payload.get("name", "")).strip()
    goal = str(payload.get("goal", "")).strip()
    steps = payload.get("steps", [])
    if not name or not steps:
        raise HTTPException(status_code=422, detail="name and steps are required")
    proc = await task_manager.learn_procedure(name=name, steps=steps, goal=goal)
    return proc


@router.get("/automation/procedures/search")
async def search_procedures(q: str = "") -> Dict[str, Any]:
    if not q:
        return {"results": []}
    results = await task_manager.search_procedures(q)
    return {"results": results}


@router.post("/automation/procedures/capture")
async def capture_procedure(payload: Dict[str, Any]) -> Dict[str, Any]:
    task_id = str(payload.get("task_id", "")).strip()
    name = str(payload.get("name", "")).strip()
    goal = str(payload.get("goal", "")).strip() or None
    if not task_id or not name:
        raise HTTPException(status_code=422, detail="task_id and name are required")
    try:
        proc = await task_manager.capture_task_to_procedure(task_id, name, goal)
        return proc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/automation/procedures/{proc_id}")
async def get_procedure(proc_id: str) -> Dict[str, Any]:
    proc = await task_manager.get_procedure(proc_id)
    if not proc:
        raise HTTPException(status_code=404, detail="procedure_not_found")
    return proc


@router.post("/automation/procedures/{proc_id}/run")
async def run_procedure(proc_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    params = (payload or {}).get("params", {}) if payload else {}
    try:
        result = await task_manager.run_procedure(proc_id, params_override=params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result


@router.post("/automation/workflows")
async def create_workflow(payload: Dict[str, Any]) -> Dict[str, Any]:
    name = str(payload.get("name", "")).strip()
    procedure_ids = payload.get("procedure_ids", [])
    goal = str(payload.get("goal", "")).strip()
    if not name or not procedure_ids:
        raise HTTPException(status_code=422, detail="name and procedure_ids are required")
    try:
        wf_id = await task_manager.create_workflow(name, procedure_ids, goal)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"workflow_id": wf_id, "name": name, "procedure_ids": procedure_ids}


@router.post("/automation/workflows/{workflow_id}/run")
async def run_workflow(workflow_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    params = (payload or {}).get("params", {}) if payload else {}
    try:
        result = await task_manager.run_workflow(workflow_id, params_override=params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result
