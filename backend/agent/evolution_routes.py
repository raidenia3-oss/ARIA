"""AURA Self-Evolution Engine REST endpoints (Bloque 60).

Auto-parcheo, dataset builder y LoRA scheduler (100% offline).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.agent.evolution import (
    DatasetSplit,
    EvolutionEngine,
    FineTuneJob,
    PatchRecord,
    get_evolution_engine,
)

logger = logging.getLogger("AURA.Agent.Evolution.Routes")

router = APIRouter(prefix="/api/agent/evolution", tags=["agent-evolution"])


def _engine() -> EvolutionEngine:
    return get_evolution_engine()


class GeneratePatchRequest(BaseModel):
    target_file: str = Field(..., min_length=1, max_length=500)
    old_snippet: str = Field(..., min_length=1, max_length=20000)
    new_snippet: str = Field(..., min_length=1, max_length=20000)
    description: str = Field(default="")
    metadata: Optional[Dict[str, Any]] = None


class BuildDatasetRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="")
    entries: List[Dict[str, Any]] = Field(..., min_items=1, max_items=5000)
    splits: Optional[List[str]] = None
    quality_threshold: float = Field(default=0.0, ge=0.0, le=1.0)


class ScheduleLoraRequest(BaseModel):
    dataset_id: str = Field(..., min_length=1, max_length=100)
    base_model: str = Field(default="local-base", min_length=1, max_length=200)
    priority: str = Field(default="normal")
    max_checkpoints: int = Field(default=3, ge=1, le=20)
    estimated_minutes: int = Field(default=60, ge=1, le=10000)


class CheckpointRequest(BaseModel):
    metrics: Optional[Dict[str, Any]] = None


class CompleteJobRequest(BaseModel):
    metrics: Optional[Dict[str, Any]] = None


class FailJobRequest(BaseModel):
    error: str = Field(..., min_length=1, max_length=500)



@router.post("/patch/generate")
async def generate_patch(payload: GeneratePatchRequest) -> Dict[str, Any]:
    engine = _engine()
    try:
        record = engine.generate_patch(
            target_file=payload.target_file,
            old_snippet=payload.old_snippet,
            new_snippet=payload.new_snippet,
            description=payload.description,
            metadata=payload.metadata,
        )
        return record.to_dict()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/patch/{patch_id}/apply")
async def apply_patch(patch_id: str, run_sandbox: bool = True) -> Dict[str, Any]:
    engine = _engine()
    try:
        record = engine.apply_patch(patch_id, run_sandbox=run_sandbox)
        return record.to_dict()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/patch/{patch_id}/rollback")
async def rollback_patch(patch_id: str) -> Dict[str, Any]:
    engine = _engine()
    try:
        return engine.rollback_patch(patch_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/patches")
async def list_patches(status: Optional[str] = None) -> Dict[str, Any]:
    engine = _engine()
    status_enum = None
    if status:
        try:
            from backend.agent.evolution import PatchStatus
            status_enum = PatchStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Status invalido: " + status)
    patches = engine.list_patches(status=status_enum)
    return {"count": len(patches), "patches": [p.to_dict() for p in patches]}


@router.get("/patch/{patch_id}")
async def get_patch(patch_id: str) -> Dict[str, Any]:
    engine = _engine()
    record = engine.get_patch(patch_id)
    if not record:
        raise HTTPException(status_code=404, detail="patch_not_found")
    return record.to_dict()


@router.post("/dataset/build")
async def build_dataset(payload: BuildDatasetRequest) -> Dict[str, Any]:
    engine = _engine()
    splits = None
    if payload.splits:
        splits = [DatasetSplit(s) for s in payload.splits]
    try:
        return engine.build_dataset(
            name=payload.name,
            entries=payload.entries,
            description=payload.description,
            splits=splits,
            quality_threshold=payload.quality_threshold,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/datasets")
async def list_datasets() -> Dict[str, Any]:
    engine = _engine()
    datasets = engine.list_datasets()
    return {"count": len(datasets), "datasets": datasets}


@router.get("/dataset/{dataset_id}")
async def get_dataset(dataset_id: str) -> Dict[str, Any]:
    engine = _engine()
    manifest = engine.get_dataset(dataset_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="dataset_not_found")
    return manifest


@router.post("/dataset/{dataset_id}/export")
async def export_dataset(dataset_id: str, fmt: str = "jsonl") -> Dict[str, Any]:
    engine = _engine()
    try:
        return engine.export_dataset(dataset_id, fmt=fmt)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))




@router.post("/lora/schedule")
async def schedule_lora(payload: ScheduleLoraRequest) -> Dict[str, Any]:
    engine = _engine()
    try:
        job = engine.lora_scheduler.schedule_job(
            dataset_id=payload.dataset_id,
            base_model=payload.base_model,
            priority=payload.priority,
            max_checkpoints=payload.max_checkpoints,
            estimated_minutes=payload.estimated_minutes,
        )
        return job.to_dict()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/lora/{job_id}/start")
async def start_lora_job(job_id: str) -> Dict[str, Any]:
    engine = _engine()
    try:
        return engine.lora_scheduler.start_job(job_id).to_dict()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/lora/{job_id}/checkpoint")
async def checkpoint_lora_job(job_id: str, payload: CheckpointRequest) -> Dict[str, Any]:
    engine = _engine()
    try:
        return engine.lora_scheduler.checkpoint_job(job_id, metrics=payload.metrics)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/lora/{job_id}/complete")
async def complete_lora_job(job_id: str, payload: CompleteJobRequest) -> Dict[str, Any]:
    engine = _engine()
    try:
        return engine.lora_scheduler.complete_job(job_id, metrics=payload.metrics).to_dict()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/lora/{job_id}/fail")
async def fail_lora_job(job_id: str, payload: FailJobRequest) -> Dict[str, Any]:
    engine = _engine()
    try:
        return engine.lora_scheduler.fail_job(job_id, error=payload.error).to_dict()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/lora/jobs")
async def list_lora_jobs() -> Dict[str, Any]:
    engine = _engine()
    jobs = engine.lora_scheduler.list_jobs()
    return {"count": len(jobs), "jobs": [j.to_dict() for j in jobs]}


@router.get("/lora/{job_id}/estimate")
async def estimate_lora(job_id: str) -> Dict[str, Any]:
    engine = _engine()
    job = engine.lora_scheduler.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job_not_found")
    try:
        return engine.lora_scheduler.estimate_resources(job.dataset_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/status")
async def evolution_status() -> Dict[str, Any]:
    engine = _engine()
    return engine.get_status()


@router.get("/logs")
async def evolution_logs(event: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
    engine = _engine()
    logs = engine.list_logs(event=event, limit=limit)
    return {"count": len(logs), "logs": logs}


__all__ = ["router"]
