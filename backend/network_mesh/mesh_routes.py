"""BLOQUE 78 - Mesh Network Management REST Endpoints (/api/network/mesh)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, WebSocket
from pydantic import BaseModel

from backend.network_mesh.mesh import MeshConfig, get_mesh_engine

router = APIRouter(prefix="/api/network/mesh", tags=["mesh"])


class KeySetRequest(BaseModel):
    key: str
    value: Any


@router.get("/status", response_model=Dict[str, Any])
async def mesh_status():
    return get_mesh_engine().status()


@router.get("/nodes", response_model=List[Dict[str, Any]])
async def mesh_nodes():
    return get_mesh_engine().peers_serializable()


@router.post("/announce", response_model=Dict[str, Any])
async def mesh_announce():
    engine = get_mesh_engine()
    delivered = engine.announce()
    return {"node_id": engine.config.node_id, "announce_sent": True, "delivered": delivered}


@router.post("/key/set", response_model=Dict[str, Any])
async def key_set(req: KeySetRequest):
    engine = get_mesh_engine()
    ok = engine.set_key(req.key, req.value)
    return {"key": req.key, "set": ok, "value": engine.get_key(req.key)}


@router.get("/key/{key}", response_model=Dict[str, Any])
async def key_get(key: str):
    engine = get_mesh_engine()
    return {"key": key, "value": engine.get_key(key)}


@router.get("/keys", response_model=Dict[str, Any])
async def key_all():
    return get_mesh_engine().kv_snapshot()


@router.post("/sync", response_model=Dict[str, Any])
async def mesh_sync():
    engine = get_mesh_engine()
    sent = engine.sync_all()
    return {"node_id": engine.config.node_id, "sync_sent": True, "packets": sent}


@router.get("/health", response_model=Dict[str, Any])
async def mesh_health():
    engine = get_mesh_engine()
    return {"ok": True, "node_id": engine.config.node_id, "peer_count": engine.status()["peer_count"],
            "offline_only": True}


@router.websocket("/ws")
async def mesh_ws(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = await ws.receive_text()
            if data.strip() == "status":
                await ws.send_json(get_mesh_engine().status())
            else:
                await ws.send_json({"type": "ack", "node_id": get_mesh_engine().config.node_id})
    except Exception:
        await ws.close()