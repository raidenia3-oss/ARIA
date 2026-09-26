"""BLOQUE 78 - Mesh Network Management REST Endpoints (/api/network/mesh)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.network.mesh import (
    MeshNode,
    MeshOrchestrator,
    MeshPacket,
    P2PMeshEngine,
    SwarmStateSnapshot,
    get_mesh_orchestrator,
    reset_mesh_orchestrator,
)

router = APIRouter(prefix="/api/network/mesh", tags=["mesh"])


class NodeAddRequest(BaseModel):
    node_id: str
    host: str = "127.0.0.1"
    port: int = 48178
    shared_secret: str = ""


class SyncRequest(BaseModel):
    knowledge: Dict[str, Any] = {}
    tasks: List[Dict[str, Any]] = []
    directives: List[Dict[str, Any]] = []


class PacketRequest(BaseModel):
    payload: str
    dst: str = ""
    msg_type: str = "data"


def _node_dict(n: MeshNode) -> Dict[str, Any]:
    return n.to_dict()


@router.get("/status", response_model=Dict[str, Any])
async def mesh_status():
    return get_mesh_orchestrator().status()


@router.get("/nodes", response_model=List[Dict[str, Any]])
async def mesh_nodes():
    return [_node_dict(n) for n in get_mesh_orchestrator().list_nodes()]


@router.post("/nodes", response_model=Dict[str, Any])
async def mesh_add_node(req: NodeAddRequest):
    orch = get_mesh_orchestrator()
    if orch.get_node(req.node_id):
        raise HTTPException(status_code=409, detail="node already exists")
    node = MeshNode(node_id=req.node_id, host=req.host,
                    port=req.port, shared_secret=req.shared_secret)
    orch.add_node(node)
    return _node_dict(node)


@router.delete("/nodes/{node_id}", response_model=Dict[str, Any])
async def mesh_remove_node(node_id: str):
    ok = get_mesh_orchestrator().remove_node(node_id)
    if not ok:
        raise HTTPException(status_code=404, detail="node not found")
    return {"node_id": node_id, "removed": True}


@router.post("/sync", response_model=Dict[str, Any])
async def mesh_sync(req: SyncRequest):
    orch = get_mesh_orchestrator()
    snap = orch.engine.update_state(
        knowledge=req.knowledge or None,
        tasks=req.tasks or None,
        directives=req.directives or None,
    )
    return snap.to_dict()


@router.post("/packet/encode", response_model=Dict[str, Any])
async def mesh_encode_packet(req: PacketRequest):
    orch = get_mesh_orchestrator()
    data = orch.engine.encode_packet(
        req.payload.encode("utf-8"), dst=req.dst, msg_type=req.msg_type,
    )
    return {"encoded_hex": data.hex(), "size": len(data)}


@router.post("/packet/decode", response_model=Dict[str, Any])
async def mesh_decode_packet(req: PacketRequest):
    orch = get_mesh_orchestrator()
    try:
        raw = bytes.fromhex(req.payload)
    except ValueError:
        raise HTTPException(status_code=400, detail="payload must be hex")
    pkt = orch.engine.decode_packet(raw)
    if pkt is None:
        raise HTTPException(status_code=400, detail="invalid packet or HMAC mismatch")
    return {
        "src_node_id": pkt.src_node_id,
        "dst_node_id": pkt.dst_node_id,
        "msg_type": pkt.msg_type,
        "seq": pkt.seq,
        "payload": pkt.payload.decode("utf-8", "replace"),
    }


@router.get("/health", response_model=Dict[str, Any])
async def mesh_health():
    st = get_mesh_orchestrator().status()
    return {"ok": True, "node_id": st.get("node_id"),
            "peers": st.get("peers"), "offline_only": True}


@router.post("/reset", response_model=Dict[str, Any])
async def mesh_reset():
    reset_mesh_orchestrator()
    return {"reset": True}