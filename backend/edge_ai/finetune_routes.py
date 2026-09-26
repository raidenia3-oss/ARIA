"""BLOQUE 86 - Edge-AI Fine-Tune REST + WebSocket (/api/ai/finetune)."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.edge_ai.dataset import DatasetFormatter
from backend.edge_ai.engine import get_edge_trainer

router = APIRouter(prefix="/api/ai/finetune", tags=["edge-finetune"])
_fmt = DatasetFormatter()


class BuildDatasetRequest(BaseModel):
    records: List[Dict[str, Any]] = []
    min_score: float = 0.5


class TrainRequest(BaseModel):
    records: List[Dict[str, Any]] = []
    rank: int = 8
    epochs: int = 2
    base_model: str = "aura-slm-local"


@router.get("/status")
async def finetune_status() -> Dict[str, Any]:
    eng = get_edge_trainer()
    active = eng.active()
    return {"online": True, "runner": "local",
            "runs": len(eng.runs()), "adapters": len(eng.adapters()),
            "active_adapter": (active.adapter_id if active else None),
            "offline_only": True}


@router.post("/dataset/build")
async def build_dataset(req: BuildDatasetRequest) -> Dict[str, Any]:
    examples = _fmt.synthesize(req.records, req.min_score)
    return {"count": len(examples),
            "examples": [e.to_dict() for e in examples[:200]],
            "jsonl_lines": len(examples), "offline_only": True}


@router.post("/train")
async def train_adapter(req: TrainRequest) -> Dict[str, Any]:
    examples = _fmt.synthesize(req.records)
    if not examples:
        raise HTTPException(status_code=422, detail="dataset vacio tras limpieza")
    try:
        return await asyncio.to_thread(
            get_edge_trainer().train, examples, req.rank, req.epochs, req.base_model)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/adapters")
async def list_adapters() -> Dict[str, Any]:
    ads = get_edge_trainer().adapters()
    return {"count": len(ads), "adapters": [a.to_dict() for a in ads]}


@router.post("/adapters/{adapter_id}/evaluate")
async def evaluate_adapter(adapter_id: str) -> Dict[str, Any]:
    return get_edge_trainer().evaluate(adapter_id)


@router.post("/adapters/{adapter_id}/activate")
async def activate_adapter(adapter_id: str) -> Dict[str, Any]:
    out = get_edge_trainer().hot_swap(adapter_id)
    if not out.get("swapped"):
        raise HTTPException(status_code=409, detail=out.get("reason", "swap failed"))
    return out


@router.post("/rollback")
async def rollback_active() -> Dict[str, Any]:
    out = get_edge_trainer().rollback()
    if not out.get("rolled_back"):
        raise HTTPException(status_code=409, detail=out.get("reason", "rollback failed"))
    return out


@router.websocket("/ws")
async def finetune_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    queue: asyncio.Queue = asyncio.Queue()
    get_edge_trainer().on_event(queue.put_nowait)
    try:
        while True:
            try:
                evt = await asyncio.wait_for(queue.get(), timeout=1.0)
                await websocket.send_json({"event": evt.get("type", "event"), **evt})
            except asyncio.TimeoutError:
                eng = get_edge_trainer()
                active = eng.active()
                await websocket.send_json({
                    "event": "heartbeat", "runs": len(eng.runs()),
                    "adapters": len(eng.adapters()),
                    "active_adapter": (active.adapter_id if active else None),
                    "offline_only": True})
    except (WebSocketDisconnect, Exception):
        pass
