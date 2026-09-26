"""BLOQUE 101 - REST + WebSocket para /api/ai/finetune. 100% offline."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from backend.ai.fine_tuning import (
    MAX_ADAPTER_RANK,
    MAX_DATASET_SAMPLES,
    get_engine,
    reset_engine,
)

router = APIRouter(prefix="/api/ai/finetune-lora", tags=["finetune-lora"])


class SynthesizeRequest(BaseModel):
    name: str = "dataset"
    entries: List[Dict[str, Any]] = Field(default_factory=list)


class AdapterRequest(BaseModel):
    base_model: str = "aura-local-llm"
    rank: int = Field(default=16, ge=1, le=MAX_ADAPTER_RANK)
    alpha: float = 32.0
    dataset_id: str = ""


class TrainRequest(BaseModel):
    steps: int = Field(default=50, ge=1, le=10_000)
    lr: float = Field(default=1e-3, gt=0)
    target_loss: float = 0.05


class OptimizeRequest(BaseModel):
    bits: int = Field(default=4, ge=2, le=16)


@router.get("/status")
async def ft_status() -> Dict[str, Any]:
    return get_engine().status()


@router.post("/dataset/synthesize")
async def ft_synthesize(req: SynthesizeRequest) -> Dict[str, Any]:
    res = get_engine().synthesizer.export(req.name, req.entries)
    if not res.get("dataset_id"):
        raise HTTPException(422, res.get("error", "no_valid_samples"))
    return res


@router.get("/dataset/list")
async def ft_list_datasets() -> Dict[str, Any]:
    ds = get_engine().synthesizer.list_datasets()
    return {"count": len(ds), "datasets": ds, "offline_only": True}


@router.post("/adapter/create")
async def ft_create_adapter(req: AdapterRequest) -> Dict[str, Any]:
    return get_engine().adapters.create_adapter(
        base_model=req.base_model, rank=req.rank, alpha=req.alpha,
        dataset_id=req.dataset_id)


@router.post("/adapter/{adapter_id}/train")
async def ft_train(adapter_id: str, req: TrainRequest) -> Dict[str, Any]:
    res = get_engine().adapters.train_adapter(
        adapter_id, steps=req.steps, lr=req.lr, target_loss=req.target_loss)
    if not res.get("trained"):
        raise HTTPException(400, res.get("error", "training_failed"))
    return res


@router.post("/adapter/{adapter_id}/activate")
async def ft_activate(adapter_id: str) -> Dict[str, Any]:
    res = get_engine().adapters.activate(adapter_id)
    if not res.get("activated"):
        raise HTTPException(400, res.get("error", "activation_failed"))
    return res


@router.post("/adapter/{adapter_id}/rollback")
async def ft_rollback(adapter_id: str) -> Dict[str, Any]:
    res = get_engine().adapters.rollback(adapter_id)
    if not res.get("rolled_back"):
        raise HTTPException(400, res.get("error", "rollback_failed"))
    return res


@router.post("/adapter/{adapter_id}/optimize")
async def ft_optimize(adapter_id: str, req: OptimizeRequest) -> Dict[str, Any]:
    res = get_engine().adapters.optimize_weights(adapter_id, bits=req.bits)
    if not res.get("optimized"):
        raise HTTPException(400, res.get("error", "optimization_failed"))
    return res


@router.get("/adapters")
async def ft_adapters() -> Dict[str, Any]:
    ads = get_engine().adapters.list_adapters()
    return {"count": len(ads), "adapters": ads, "offline_only": True}


@router.get("/adapter/{adapter_id}")
async def ft_get_adapter(adapter_id: str) -> Dict[str, Any]:
    ad = get_engine().adapters.get_adapter(adapter_id)
    if ad is None:
        raise HTTPException(404, "adapter_not_found")
    return ad


@router.post("/cycle")
async def ft_cycle(req: SynthesizeRequest) -> Dict[str, Any]:
    """Ciclo completo dataset -> adapter -> entrenamiento."""
    res = get_engine().run_cycle(req.entries, name=req.name)
    if not res.get("cycle"):
        raise HTTPException(400, res.get("error", "cycle_failed"))
    return res


@router.post("/reset")
async def ft_reset() -> Dict[str, Any]:
    reset_engine()
    get_engine()
    return {"reset": True, "offline_only": True}


class _WSConn:
    def __init__(self) -> None:
        self.active: set = set()


_ws = _WSConn()


@router.websocket("/ws")
async def finetune_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    _ws.active.add(websocket)
    try:
        while True:
            eng = get_engine()
            await websocket.send_json({"event": "finetune_heartbeat",
                                       "status": eng.status(),
                                       "offline_only": True})
            await asyncio.sleep(2.0)
    except (WebSocketDisconnect, Exception):
        _ws.active.discard(websocket)
