"""BLOQUE 88 - Cognitive Graph REST + WebSocket (/api/memory/cognitive)."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.cognitive_graph import get_cognitive_engine

router = APIRouter(prefix="/api/memory/cognitive", tags=["cognitive"])


class IngestRequest(BaseModel):
    text: str = ""
    kind: str = "concept"


class ConsolidateRequest(BaseModel):
    history: List[str] = []
    label: str = ""


@router.get("/status")
async def cog_status() -> Dict[str, Any]:
    eng = get_cognitive_engine()
    q = eng.query("", limit=1)
    return {"online": True, "runner": "local", "nodes": q.get("count", 0),
            "summaries": len(eng.summaries()), "offline_only": True}


@router.post("/ingest")
async def cog_ingest(req: IngestRequest) -> Dict[str, Any]:
    return get_cognitive_engine().ingest(req.text, req.kind)


@router.post("/consolidate")
async def cog_consolidate(req: ConsolidateRequest) -> Dict[str, Any]:
    return get_cognitive_engine().consolidate(req.history, req.label)


@router.get("/query")
async def cog_query(term: str = "", limit: int = 20) -> Dict[str, Any]:
    return get_cognitive_engine().query(term, limit)


@router.get("/clusters")
async def cog_clusters() -> Dict[str, Any]:
    return get_cognitive_engine().clusters()


@router.websocket("/ws")
async def cog_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            eng = get_cognitive_engine()
            await websocket.send_json({"event": "heartbeat",
                                       "nodes": eng.query("", limit=1)["count"],
                                       "offline_only": True})
            await asyncio.sleep(2.0)
    except (WebSocketDisconnect, Exception):
        pass
