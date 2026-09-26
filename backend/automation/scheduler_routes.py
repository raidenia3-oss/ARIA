"""AURA Autonomous Scheduler REST endpoints (Bloque 67).

Programar, pausar, listar y auditar tareas autonomas recurrentes bajo
``/api/automation/scheduler``. Los handlers se registran en codigo
(``register_handler``); REST nunca recibe codigo arbitrario.

Autostart: el bucle del scheduler arranca con la app salvo que
``AURA_SCHEDULER_AUTOSTART=0`` (util en pruebas).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.automation.scheduler import (
    SchedulerEngine,
    get_scheduler,
    reset_scheduler,
    validate_cron,
)

logger = logging.getLogger("AURA.Automation.Scheduler.Routes")

router = APIRouter(
    prefix="/api/automation/scheduler",
    tags=["automation", "scheduler"],
    on_startup=[],
    on_shutdown=[],
)


def _engine() -> SchedulerEngine:
    return get_scheduler()


class RegisterTaskRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    kind: str = Field(default="noop", min_length=1, max_length=100)
    trigger: str = Field(default="interval", pattern="^(cron|interval)$")
    cron: str = Field(default="", max_length=100)
    interval_seconds: float = Field(default=60.0, ge=1, le=31_536_000)
    priority: int = Field(default=5, ge=0, le=99)
    overlap_policy: str = Field(default="skip", pattern="^(skip|queue)$")
    resources: Optional[List[str]] = Field(default=None, max_items=10)
    metadata: Optional[Dict[str, Any]] = None
    enabled: bool = True


class TaskFlagRequest(BaseModel):
    enabled: bool = True


@router.get("/status")
async def scheduler_status() -> Dict[str, Any]:
    return _engine().get_status()


@router.get("/handlers")
async def scheduler_handlers() -> Dict[str, Any]:
    return {"handlers": _engine().list_handlers()}


@router.post("/tasks")
async def register_task(payload: RegisterTaskRequest) -> Dict[str, Any]:
    if payload.trigger == "cron" and not validate_cron(payload.cron):
        raise HTTPException(status_code=422, detail=f"cron invalido: {payload.cron!r}")
    try:
        task = _engine().add_task(
            name=payload.name,
            kind=payload.kind,
            trigger=payload.trigger,
            cron=payload.cron,
            interval_seconds=payload.interval_seconds,
            priority=payload.priority,
            overlap_policy=payload.overlap_policy,
            resources=payload.resources,
            metadata=payload.metadata,
            enabled=payload.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"status": "registered", "task": task.to_dict()}


@router.get("/tasks")
async def list_tasks(enabled: Optional[bool] = None,
                     status: Optional[str] = None,
                     limit: int = 200) -> Dict[str, Any]:
    tasks = _engine().list_tasks(enabled=enabled, status=status, limit=limit)
    return {"count": len(tasks), "tasks": tasks}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str) -> Dict[str, Any]:
    task = _engine().get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task_not_found")
    return task.to_dict()


@router.post("/tasks/{task_id}/pause")
async def pause_task(task_id: str) -> Dict[str, Any]:
    if not _engine().set_enabled(task_id, False):
        raise HTTPException(status_code=404, detail="task_not_found")
    return {"status": "paused", "task_id": task_id}


@router.post("/tasks/{task_id}/resume")
async def resume_task(task_id: str) -> Dict[str, Any]:
    if not _engine().set_enabled(task_id, True):
        raise HTTPException(status_code=404, detail="task_not_found")
    return {"status": "resumed", "task_id": task_id}


@router.post("/tasks/{task_id}/run-now")
async def run_task_now(task_id: str) -> Dict[str, Any]:
    if not _engine().run_task_now(task_id):
        raise HTTPException(status_code=404, detail="task_not_found")
    return {"status": "queued_for_immediate_run", "task_id": task_id}


@router.delete("/tasks/{task_id}")
async def remove_task(task_id: str) -> Dict[str, Any]:
    if not _engine().remove_task(task_id):
        raise HTTPException(status_code=404, detail="task_not_found")
    return {"status": "removed", "task_id": task_id}


@router.get("/audit")
async def scheduler_audit(limit: int = 50) -> Dict[str, Any]:
    events = _engine().audit(limit=limit)
    return {"count": len(events), "events": events}


@router.get("/locks")
async def scheduler_locks() -> Dict[str, Any]:
    return {"busy_resources": _engine().busy_resources()}


@router.post("/engine/start")
async def engine_start() -> Dict[str, Any]:
    return await _engine().start()


@router.post("/engine/stop")
async def engine_stop() -> Dict[str, Any]:
    return await _engine().stop()


_startup_registered = False


async def _autostart() -> None:
    if os.getenv("AURA_SCHEDULER_AUTOSTART", "1") != "0":
        await _engine().start()


async def _autostop() -> None:
    await _engine().stop()


def enable_autostart() -> None:
    """Registra los hooks on_startup/on_shutdown en el router (idempotente)."""
    global _startup_registered
    if _startup_registered:
        return
    router.on_startup.append(_autostart)
    router.on_shutdown.append(_autostop)
    _startup_registered = True


__all__ = ["router", "enable_autostart"]