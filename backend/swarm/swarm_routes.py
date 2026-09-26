"""BLOQUE 93 - REST + WebSocket para /api/swarm/marketplace."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.swarm.specialization import get_swarm_engine, reset_swarm_engine

router = APIRouter(prefix="/api/swarm/marketplace", tags=["swarm"])


class RegisterRequest(BaseModel):
    node_id: str
    roles: List[str] = []
    skills: List[str] = []
    hardware: Dict[str, Any] = {}
    software: List[str] = []


class PublishRequest(BaseModel):
    name: str
    category: str
    description: str = ""
    version: str = "1.0.0"
    owner: str = "local"
    payload: Dict[str, Any] = {}
    requires: List[str] = []


class RateRequest(BaseModel):
    rating: float


@router.get("/status", tags=["swarm"])
async def swarm_status() -> Dict[str, Any]:
    return get_swarm_engine().status()


@router.post("/register", tags=["swarm"])
async def swarm_register(req: RegisterRequest) -> Dict[str, Any]:
    p = get_swarm_engine().registry.register(
        req.node_id, req.roles, req.skills, req.hardware, req.software)
    return p.to_dict()


@router.get("/nodes", tags=["swarm"])
async def swarm_nodes(role: Optional[str] = None, skill: Optional[str] = None) -> Dict[str, Any]:
    eng = get_swarm_engine()
    if role:
        items = eng.registry.find_by_role(role)
    elif skill:
        items = eng.registry.find_by_skill(skill)
    else:
        items = eng.registry.list_all()
    return {"count": len(items), "nodes": [p.to_dict() for p in items]}


@router.post("/publish", tags=["swarm"])
async def swarm_publish(req: PublishRequest) -> Dict[str, Any]:
    m = get_swarm_engine().marketplace.publish(
        req.name, req.category, req.description, req.version, req.owner,
        req.payload, req.requires)
    return m.to_dict()


@router.get("/skills", tags=["swarm"])
async def swarm_discover(category: Optional[str] = None, query: str = "") -> Dict[str, Any]:
    items = get_swarm_engine().marketplace.discover(category=category, query=query)
    return {"count": len(items), "skills": [m.to_dict() for m in items]}


@router.get("/skills/{skill_id}", tags=["swarm"])
async def swarm_download(skill_id: str) -> Dict[str, Any]:
    m = get_swarm_engine().marketplace.download(skill_id)
    if m is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="skill not found")
    return m.to_dict()


@router.post("/skills/{skill_id}/rate", tags=["swarm"])
async def swarm_rate(skill_id: str, req: RateRequest) -> Dict[str, Any]:
    m = get_swarm_engine().marketplace.rate(skill_id, req.rating)
    if m is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="skill not found")
    return m.to_dict()


@router.post("/assign", tags=["swarm"])
async def swarm_assign(task_id: str, node_id: str, role: str,
                        metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    a = get_swarm_engine().assign_role(task_id, node_id, role, metadata)
    if a is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="node or role not available")
    return a.to_dict()


@router.get("/assignments", tags=["swarm"])
async def swarm_assignments(node_id: Optional[str] = None) -> Dict[str, Any]:
    items = get_swarm_engine().list_assignments(node_id=node_id)
    return {"count": len(items), "assignments": [a.to_dict() for a in items]}


@router.post("/reset", tags=["swarm"])
async def swarm_reset() -> Dict[str, Any]:
    reset_swarm_engine()
    get_swarm_engine()
    return {"reset": True}


class _WSConn:
    def __init__(self) -> None:
        self.active: set = set()


_ws = _WSConn()


@router.websocket("/ws")
async def swarm_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    _ws.active.add(websocket)
    try:
        while True:
            e = get_swarm_engine()
            await websocket.send_json({"event": "heartbeat", "status": e.status(), "offline_only": True})
            await asyncio.sleep(2.0)
    except (WebSocketDisconnect, Exception):
        _ws.active.discard(websocket)
