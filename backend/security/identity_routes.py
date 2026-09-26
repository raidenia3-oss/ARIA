"""BLOQUE 90 - Identity & Zero-Trust REST + WebSocket (/api/security/identity)."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.security.identity_engine import (
    get_identity_engine,
    reset_identity_engine,
)

router = APIRouter(prefix="/api/security/identity", tags=["security-identity"])


class RegisterRequest(BaseModel):
    label: str = ""
    role: str = "peer"
    force: bool = False


class CertRequest(BaseModel):
    subject_node: str = ""
    signing_node: str = "local"
    role: str = "peer"
    ttl_s: float = 86400.0


class SignRequest(BaseModel):
    node_id: str = ""
    payload: Dict[str, Any] = {}
    include_pubkey: bool = True


class EphemeralRequest(BaseModel):
    node_id: str = ""
    scope: str = "swarm"
    ttl_s: float = 600.0


class EphemeralValidateRequest(BaseModel):
    token: str = ""
    node_id: str = ""
    scope: Optional[str] = None


@router.get("/status")
async def identity_status() -> Dict[str, Any]:
    return get_identity_engine().status()


@router.post("/register")
async def register_node(req: RegisterRequest) -> Dict[str, Any]:
    try:
        return get_identity_engine().register(req.label, req.role, req.force).to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/nodes")
async def list_nodes(limit: int = 100) -> Dict[str, Any]:
    items = get_identity_engine().list_nodes(limit=min(500, max(1, limit)))
    return {"count": len(items), "nodes": [n.to_dict() for n in items],
            "offline_only": True}


@router.get("/nodes/{node_id}")
async def get_node(node_id: str) -> Dict[str, Any]:
    n = get_identity_engine().get(node_id)
    if n is None:
        raise HTTPException(status_code=404, detail="node not found")
    return n.to_dict()


@router.post("/certs")
async def issue_cert(req: CertRequest) -> Dict[str, Any]:
    try:
        return get_identity_engine().issue_cert(
            req.subject_node, req.signing_node, req.role, req.ttl_s).to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/certs")
async def list_certs(limit: int = 100) -> Dict[str, Any]:
    items = get_identity_engine().list_certs(limit=min(500, max(1, limit)))
    return {"count": len(items), "certs": [c.to_dict() for c in items],
            "offline_only": True}


@router.post("/sign")
async def sign_payload(req: SignRequest) -> Dict[str, Any]:
    try:
        return get_identity_engine().sign(
            req.node_id, req.payload, req.include_pubkey).to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/verify")
async def verify_payload(signed: Dict[str, Any]) -> Dict[str, Any]:
    sp = signed
    ok = get_identity_engine().verify(sp)
    return {"verified": ok, "offline_only": True}


@router.post("/ephemeral")
async def issue_ephemeral(req: EphemeralRequest) -> Dict[str, Any]:
    try:
        return get_identity_engine().issue_ephemeral(
            req.node_id, req.scope, req.ttl_s)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/ephemeral/validate")
async def validate_ephemeral(req: EphemeralValidateRequest) -> Dict[str, Any]:
    ok = get_identity_engine().validate_ephemeral(
        req.token, req.node_id, req.scope)
    return {"valid": ok, "offline_only": True}


@router.post("/ephemeral/revoke")
async def revoke_ephemeral(node_id: str) -> Dict[str, Any]:
    ok = get_identity_engine().revoke_ephemeral(node_id)
    return {"revoked": ok, "offline_only": True}


@router.post("/reset")
async def identity_reset() -> Dict[str, Any]:
    reset_identity_engine()
    return {"reset": True, "offline_only": True}


@router.websocket("/ws")
async def identity_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    queue: asyncio.Queue = asyncio.Queue()
    get_identity_engine().on_event(queue.put_nowait)
    try:
        while True:
            try:
                evt = await asyncio.wait_for(queue.get(), timeout=1.0)
                await websocket.send_json(evt)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "heartbeat",
                                           **get_identity_engine().status()})
    except (WebSocketDisconnect, Exception):
        pass