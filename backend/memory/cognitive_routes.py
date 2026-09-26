"""BLOQUE 88 - Cognitive Graph REST + WebSocket (/api/memory/cognitive)."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.memory.cognitive_graph import get_cognitive_graph

router = APIRouter(prefix="/api/memory/cognitive", tags=["cognitive-graph"])


class IngestRequest(BaseModel):
    text: str = ""
    source: str = "interaction"
    kind: str = "concept"
    summary: str = ""
    metadata: Dict[str, Any] = {}


class ConsolidateRequest(BaseModel):
    force: bool = False


@router.get("/status")
async def cognitive_status() -> Dict[str, Any]:
    return get_cognitive_graph().stats()


@router.post("/ingest")
async def ingest_text(req: IngestRequest) -> Dict[str, Any]:
    if not req.text:
        raise HTTPException(status_code=422, detail="text requerido")
    nodes = get_cognitive_graph().ingest(req.text, req.source, req.kind,
                                         req.summary, req.metadata)
    return {"count": len(nodes), "nodes": [n.to_dict() for n in nodes],
            "offline_only": True}


@router.post("/consolidate")
async def consolidate_memory(req: ConsolidateRequest) -> Dict[str, Any]:
    sums = get_cognitive_graph().consolidate(req.force)
    return {"count": len(sums), "summaries": [s.to_dict() for s in sums],
            "offline_only": True}


@router.get("/search")
async def search_nodes(q: str = "", limit: int = 20) -> Dict[str, Any]:
    nodes = get_cognitive_graph().search(q, limit=min(200, max(1, limit)))
    return {"count": len(nodes), "nodes": [n.to_dict() for n in nodes],
            "offline_only": True}


@router.get("/clusters")
async def list_clusters() -> Dict[str, Any]:
    clusters = get_cognitive_graph().clusters()
    return {"count": len(clusters), "clusters": clusters, "offline_only": True}


@router.get("/summaries")
async def list_summaries(limit: int = 50) -> Dict[str, Any]:
    items = get_cognitive_graph().summaries(limit=min(200, max(1, limit)))
    return {"count": len(items), "summaries": [s.to_dict() for s in items],
            "offline_only": True}


@router.get("/nodes/{node_id}")
async def node_detail(node_id: str) -> Dict[str, Any]:
    n = get_cognitive_graph().get(node_id)
    if n is None:
        raise HTTPException(status_code=404, detail="node not found")
    return n.to_dict()


@router.get("/nodes/{node_id}/neighbors")
async def node_neighbors(node_id: str, limit: int = 20) -> Dict[str, Any]:
    pairs = get_cognitive_graph().neighbors(node_id, limit=min(200, max(1, limit)))
    return {"count": len(pairs),
            "edges": [e.to_dict() for e, _ in pairs],
            "nodes": [n.to_dict() for _, n in pairs],
            "offline_only": True}


@router.post("/reset")
async def cognitive_reset() -> Dict[str, Any]:
    get_cognitive_graph().reset()
    return {"reset": True, "offline_only": True}


@router.websocket("/ws")
async def cognitive_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    queue: asyncio.Queue = asyncio.Queue()
    get_cognitive_graph().on_event(queue.put_nowait)
    try:
        while True:
            try:
                evt = await asyncio.wait_for(queue.get(), timeout=1.0)
                await websocket.send_json(evt)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "heartbeat",
                                           **get_cognitive_graph().stats()})
    except (WebSocketDisconnect, Exception):
        pass