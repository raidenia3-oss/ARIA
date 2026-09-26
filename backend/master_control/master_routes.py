"""BLOQUE 79 - Master Dashboard REST Endpoints (/api/orchestrator/master)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, WebSocket
from pydantic import BaseModel

from backend.master_control.master import get_master_orchestrator

router = APIRouter(prefix="/api/orchestrator/master", tags=["master-dashboard"])


class EventRequest(BaseModel):
    source: str
    kind: str
    level: str = "info"
    payload: Optional[Dict[str, Any]] = None


class PipelineRequest(BaseModel):
    name: str
    steps: List[Dict[str, Any]] = []


@router.get("/status", response_model=Dict[str, Any])
async def master_status():
    return get_master_orchestrator().status()


@router.get("/modules", response_model=List[Dict[str, Any]])
async def master_modules():
    orch = get_master_orchestrator()
    return [s.to_dict() for s in orch.collect_status()]


@router.post("/modules/{name}/check", response_model=Dict[str, Any])
async def master_module_check(name: str):
    return get_master_orchestrator().module_health(name).to_dict()


@router.post("/events", response_model=Dict[str, Any])
async def emit_event(req: EventRequest):
    ev = get_master_orchestrator().emit_event(req.source, req.kind, req.level, req.payload)
    return ev.to_dict()


@router.get("/events", response_model=List[Dict[str, Any]])
async def list_events(limit: Optional[int] = None, level: Optional[str] = None,
                      source: Optional[str] = None):
    return [e.to_dict() for e in get_master_orchestrator().events(limit=limit, level=level, source=source)]


@router.post("/pipeline", response_model=Dict[str, Any])
async def run_pipeline(req: PipelineRequest):
    run = get_master_orchestrator().run_pipeline(req.name, req.steps)
    return run.to_dict()


@router.get("/pipelines", response_model=List[Dict[str, Any]])
async def list_pipelines(limit: Optional[int] = None):
    return [p.to_dict() for p in get_master_orchestrator().pipelines(limit=limit)]


@router.post("/cycle", response_model=Dict[str, Any])
async def run_cycle():
    return get_master_orchestrator().run_cycle()


@router.get("/health", response_model=Dict[str, Any])
async def master_health():
    st = get_master_orchestrator().status()
    return {"ok": True, "cycles": st["cycles"], "offline_only": True,
            "modules_registered": len(st["modules_registered"])}


@router.websocket("/ws")
async def master_ws(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = await ws.receive_text()
            if data.strip() == "status":
                await ws.send_json(get_master_orchestrator().status())
            elif data.strip() == "cycle":
                await ws.send_json(get_master_orchestrator().run_cycle())
            else:
                await ws.send_json({"type": "ack"})
    except Exception:
        await ws.close()