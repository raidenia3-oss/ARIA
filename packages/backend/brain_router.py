"""
Brain endpoints for Persistent Brain module.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from backend.brain_orchestrator import brain
from backend.query_router import query_router, RouteTarget
from backend.treasury_manager import treasury_manager

router = APIRouter(prefix="/api/brain", tags=["brain"])


class BrainLearn(BaseModel):
    device: str
    role: str
    prompt: str
    response: str
    provider: str
    feedback: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


class BrainSync(BaseModel):
    state: Dict[str, Any]


class RouteQuery(BaseModel):
    query: str
    force_route: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


@router.get("/status")
async def brain_status() -> Dict[str, Any]:
    return brain.get_brain_status()


@router.post("/learn")
async def brain_learn(payload: BrainLearn) -> Dict[str, Any]:
    try:
        return brain.learn(
            device=payload.device,
            role=payload.role,
            prompt=payload.prompt,
            response=payload.response,
            provider=payload.provider,
            feedback=payload.feedback,
            extra=payload.extra,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/sync")
async def brain_sync(payload: BrainSync) -> Dict[str, Any]:
    try:
        return brain.sync_remote_state(payload.state)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/route/query")
async def smart_route_query(payload: RouteQuery) -> Dict[str, Any]:
    try:
        if payload.force_route:
            try:
                target = RouteTarget(payload.force_route)
            except ValueError:
                raise HTTPException(status_code=400, detail="force_route must be one of: server, pc, api, cache, queue")
            return {"route": target.value, "query": payload.query, "forced": True}

        response = query_router.get_response(payload.query, payload.context)
        route = response.get("route")
        if route == "cache":
            import asyncio
            asyncio.create_task(query_router.async_improvement(payload.query, response))
        return response
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/route/status")
async def routing_status() -> Dict[str, Any]:
    try:
        return query_router.get_status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/route/history")
async def routing_history(limit: int = 10) -> Dict[str, Any]:
    try:
        return {"history": query_router.get_history(limit=limit)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/treasury/status")
async def treasury_status() -> Dict[str, Any]:
    try:
        return treasury_manager.get_infrastructure_status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/treasury/allocation-history")
async def treasury_history(days: int = 7) -> Dict[str, Any]:
    try:
        return {"history": treasury_manager.daily_allocation_history[-days:]}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/treasury/forecast")
async def treasury_forecast(days: int = 7) -> Dict[str, Any]:
    try:
        return treasury_manager.get_allocation_forecast(days=days)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


class TreasuryOverride(BaseModel):
    apis: Optional[float] = None
    hosting: Optional[float] = None
    models: Optional[float] = None
    reserve: Optional[float] = None


@router.post("/treasury/override-allocation")
async def override_allocation(payload: TreasuryOverride) -> Dict[str, Any]:
    try:
        status = treasury_manager.override_allocation(
            apis=payload.apis,
            hosting=payload.hosting,
            models=payload.models,
            reserve=payload.reserve,
        )
        return {"message": "Allocation overridden", "new_status": status}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


from backend.federated_training import federated_trainer


class TrainingStart(BaseModel):
    queries: Optional[List[str]] = None


@router.post("/training/start")
async def start_training(payload: TrainingStart) -> Dict[str, Any]:
    try:
        return await federated_trainer.start_training_session(queries=payload.queries)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/training/status")
async def training_status() -> Dict[str, Any]:
    try:
        return federated_trainer.get_training_status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/training/checkpoint")
async def save_checkpoint_manual() -> Dict[str, Any]:
    try:
        cp = federated_trainer.checkpoint.save_checkpoint("server", 0.0)
        return {"checkpoint": cp}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/training/distillation-history")
async def distillation_history(limit: int = 20) -> Dict[str, Any]:
    try:
        return {"history": federated_trainer.distillation.distillation_log[-limit:]}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/training/sync")
async def manual_sync(source: str = "server") -> Dict[str, Any]:
    try:
        return federated_trainer.sync.sync_knowledge(source=source)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
