"""BLOQUE 95 - REST + WebSocket para /api/daemon/sync."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.daemon.cross_device import get_sync_engine, reset_sync_engine

router = APIRouter(prefix="/api/daemon/sync", tags=["daemon-sync"])


class PeerRequest(BaseModel):
    peer_id: str
    display_name: str = ""
    ip_address: str = ""
    port: int = 8000
    capabilities: List[str] = []


class SyncRequest(BaseModel):
    peer_id: str
    state_data: Dict[str, Any] = {}


@router.get("/status", tags=["daemon-sync"])
async def sync_status() -> Dict[str, Any]:
    return get_sync_engine().get_status()


@router.get("/peers", tags=["daemon-sync"])
async def sync_peers(trusted_only: bool = False) -> Dict[str, Any]:
    peers = get_sync_engine().synchronizer.list_peers(trusted_only=trusted_only)
    return {"count": len(peers), "peers": [p.to_dict() for p in peers]}


@router.post("/peers/register", tags=["daemon-sync"])
async def sync_register_peer(req: PeerRequest) -> Dict[str, Any]:
    p = get_sync_engine().synchronizer.register_peer(
        req.peer_id, req.display_name, req.ip_address, req.port, req.capabilities)
    return p.to_dict()


@router.delete("/peers/{peer_id}", tags=["daemon-sync"])
async def sync_unregister_peer(peer_id: str) -> Dict[str, Any]:
    result = get_sync_engine().synchronizer.unregister_peer(peer_id)
    return {"removed": result, "peer_id": peer_id}


@router.post("/sync", tags=["daemon-sync"])
async def sync_with_peer(req: SyncRequest) -> Dict[str, Any]:
    return get_sync_engine().synchronizer.sync_with_peer(req.peer_id, req.state_data)


@router.get("/health", tags=["daemon-sync"])
async def sync_health() -> Dict[str, Any]:
    return get_sync_engine().health()


@router.post("/daemon/start", tags=["daemon-sync"])
async def daemon_start() -> Dict[str, Any]:
    ok = get_sync_engine().start_daemon()
    return {"started": ok}


@router.post("/daemon/stop", tags=["daemon-sync"])
async def daemon_stop() -> Dict[str, Any]:
    ok = get_sync_engine().stop_daemon()
    return {"stopped": ok}


@router.post("/daemon/restart", tags=["daemon-sync"])
async def daemon_restart() -> Dict[str, Any]:
    ok = get_sync_engine().restart_daemon()
    return {"restarted": ok}


@router.post("/daemon/simulate-interruption", tags=["daemon-sync"])
async def daemon_simulate_interrupt() -> Dict[str, Any]:
    return get_sync_engine().daemon.simulate_interruption()


@router.post("/reset", tags=["daemon-sync"])
async def sync_reset() -> Dict[str, Any]:
    reset_sync_engine()
    return {"reset": True}


class _WSConn:
    def __init__(self) -> None:
        self.active: set = set()


_ws = _WSConn()


@router.websocket("/ws")
async def sync_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    _ws.active.add(websocket)
    try:
        while True:
            e = get_sync_engine()
            await websocket.send_json({"event": "heartbeat", "status": e.get_status(), "offline_only": True})
            await asyncio.sleep(2.0)
    except (WebSocketDisconnect, Exception):
        _ws.active.discard(websocket)
