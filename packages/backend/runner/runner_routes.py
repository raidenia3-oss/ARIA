"""BLOQUE 82 - Ecosystem Execution REST + WebSocket Handlers.

Endpoints REST para lanzar/supervisar misiones autonomas y canal WebSocket
para actualizaciones de progreso en tiempo real, alimentando el overlay/master.
100% offline."""
from __future__ import annotations

import asyncio
import threading
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.runner.ecosystem import MissionDirective
from backend.runner.orchestrator import get_ecosystem_orchestrator

router = APIRouter(prefix="/api/ecosystem", tags=["ecosystem"])


class ExecuteRequest(BaseModel):
    mission_id: str = ""
    title: str = "Autonoma"
    description: str = ""
    scopes: list = []
    priority: str = "normal"
    params: dict = {}
    background: bool = False
    interrupt_event: Optional[str] = None


@router.get("/status", tags=["ecosystem"])
async def ecosystem_status() -> Dict[str, Any]:
    orch = get_ecosystem_orchestrator()
    return {"online": True, "runner": "local", "checks": 0,
            "supported_scopes": list(orch.runner.SUPPORTED_SCOPES), "offline_only": True}


@router.get("/scopes", tags=["ecosystem"])
async def ecosystem_scopes() -> Dict[str, Any]:
    return {"scopes": list(get_ecosystem_orchestrator().runner.SUPPORTED_SCOPES)}


@router.post("/execute", tags=["ecosystem"])
async def execute_mission(req: ExecuteRequest, tasks: BackgroundTasks) -> Dict[str, Any]:
    orch = get_ecosystem_orchestrator()
    directive = MissionDirective(mission_id=req.mission_id, title=req.title,
                                 description=req.description, scopes=req.scopes,
                                 priority=req.priority, params=req.params)
    if not directive.scopes:
        directive.scopes = ["rag", "audit"]
    if req.background:
        return orch.launch(directive, background=True)
    return orch.launch(directive, background=False)


@router.get("/missions/{mission_id}", tags=["ecosystem"])
async def mission_detail(mission_id: str) -> Dict[str, Any]:
    run = get_ecosystem_orchestrator().runner.get_run(mission_id)
    if run is None:
        raise HTTPException(status_code=404, detail="mission not found")
    return run.to_dict()


@router.get("/history", tags=["ecosystem"])
async def mission_history(limit: int = 10) -> Dict[str, Any]:
    runs = get_ecosystem_orchestrator().runner.history(limit=limit)
    return {"count": len(runs), "runs": [r.to_dict() for r in runs]}


@router.post("/interrupt/{task_id}", tags=["ecosystem"])
async def interrupt_task(task_id: str) -> Dict[str, Any]:
    return get_ecosystem_orchestrator().interrupt(task_id)


class _WSConn:
    def __init__(self) -> None:
        self.active: set = set()


_ws = _WSConn()


@router.websocket("/ws/{mission_id}")
async def mission_ws(websocket: WebSocket, mission_id: str) -> None:
    await websocket.accept()
    _ws.active.add(websocket)
    try:
        while True:
            run = get_ecosystem_orchestrator().runner.get_run(mission_id)
            if run is not None:
                await websocket.send_json({"mission_id": mission_id, "status": run.status,
                                           "progress": len([r for r in run.results if r.status == "success"]),
                                           "total": len(run.steps)})
            await asyncio.sleep(0.5)
    except (WebSocketDisconnect, Exception):
        _ws.active.discard(websocket)
