"""BLOQUE 94 - Zero-Knowledge Proof & Sovereign Audit Trail REST + WebSocket.

Endpoints (prefix ``/api/security/zkp``):
- GET  /status
- POST /groups            create a new safe-prime group
- GET  /groups            list groups
- POST /proofs            issue a ZK proof (prover submits witness locally)
- GET  /proofs            list proofs
- POST /verify            verify a proof (by id or inline)
- GET  /audit/status      audit chain status
- GET  /audit/entries     list audit entries (filters + pagination)
- POST /audit/verify      verify chain integrity
- POST /reset             reset engine (dev/test)
- WS  /ws                 real-time ZKP/audit events

All operation is 100% local and offline.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.security.zk_audit import (
    FiatShamirSchnorr,
    ZKProof,
    get_zk_audit_engine,
    reset_zk_audit_engine,
)

router = APIRouter(prefix="/api/security/zkp", tags=["security-zkp-audit"])


class CreateGroupRequest(BaseModel):
    bits: int = 256


class ProveRequest(BaseModel):
    statement: str = ""
    witness: int = 0
    group_id: str = ""
    prover_node: str = "local"


class VerifyRequest(BaseModel):
    proof_id: str = ""
    proof: Dict[str, Any] = {}


class AuditQueryRequest(BaseModel):
    event_type: str = ""
    actor: str = ""
    limit: int = 50
    offset: int = 0


@router.get("/status")
async def zkp_status() -> Dict[str, Any]:
    e = get_zk_audit_engine()
    return {
        "status": "ok",
        "groups": len(e.list_groups()),
        "proofs": len(e.list_proofs()),
        "audit": e.audit_status(),
        "offline_only": True,
    }


@router.post("/groups")
async def create_group(req: CreateGroupRequest) -> Dict[str, Any]:
    try:
        g = get_zk_audit_engine().create_group(bits=req.bits)
        return g.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/groups")
async def list_groups() -> Dict[str, Any]:
    items = get_zk_audit_engine().list_groups()
    return {"count": len(items), "groups": [g.to_dict() for g in items],
            "offline_only": True}


@router.post("/proofs")
async def issue_proof(req: ProveRequest) -> Dict[str, Any]:
    try:
        proof = get_zk_audit_engine().prove(
            statement=req.statement, witness=req.witness,
            group_id=req.group_id, prover_node=req.prover_node)
        return proof.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/proofs")
async def list_proofs(limit: int = 50) -> Dict[str, Any]:
    items = get_zk_audit_engine().list_proofs(limit=limit)
    return {"count": len(items), "proofs": [p.to_dict() for p in items],
            "offline_only": True}


@router.post("/verify")
async def verify_proof(req: VerifyRequest) -> Dict[str, Any]:
    e = get_zk_audit_engine()
    proof: Optional[ZKProof] = None
    if req.proof_id:
        proof = e.get_proof(req.proof_id)
        if proof is None:
            raise HTTPException(status_code=404, detail="proof not found")
    elif req.proof:
        proof = ZKProof(**req.proof)
    else:
        raise HTTPException(status_code=422, detail="proof_id or proof required")
    ok = e.verify(proof)
    return {"verified": ok, "proof_id": proof.proof_id,
            "statement": proof.statement, "offline_only": True}


@router.get("/audit/status")
async def audit_status() -> Dict[str, Any]:
    return get_zk_audit_engine().audit_status()


@router.get("/audit/entries")
async def audit_entries(event_type: str = "", actor: str = "",
                       limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    items = get_zk_audit_engine().audit_entries(
        event_type=event_type, actor=actor, limit=limit, offset=offset)
    return {"count": len(items), "entries": [e.to_dict() for e in items],
            "offline_only": True}


@router.post("/audit/verify")
async def audit_verify() -> Dict[str, Any]:
    return get_zk_audit_engine().audit_verify().to_dict()


@router.post("/reset")
async def zkp_reset() -> Dict[str, Any]:
    reset_zk_audit_engine()
    return {"reset": True, "offline_only": True}


@router.websocket("/ws")
async def zkp_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    e = get_zk_audit_engine()
    queue: asyncio.Queue = asyncio.Queue()
    e.audit.on_event(queue.put_nowait) if hasattr(e.audit, "on_event") else None
    try:
        while True:
            try:
                evt = await asyncio.wait_for(queue.get(), timeout=1.0)
                await websocket.send_json(evt)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "heartbeat", **e.audit_status()})
    except (WebSocketDisconnect, Exception):
        pass