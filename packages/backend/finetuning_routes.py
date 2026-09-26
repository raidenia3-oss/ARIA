"""Fine-tuning routes for AURA."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from backend.ab_testing_manager import ABTestingManager
from backend.model_manager import ModelManager, ModelType

router = APIRouter(prefix="/api/finetuning", tags=["finetuning"])

model_manager: Optional[ModelManager] = None
ab_testing: Optional[ABTestingManager] = None


def init_finetuning(db_session_factory) -> None:
    global model_manager, ab_testing
    model_manager = ModelManager(db_session_factory)
    ab_testing = ABTestingManager(db_session_factory)


@router.post("/jobs/create")
async def create_finetuning_job(
    model_type: str,
    dataset_id: str,
    genre: Optional[str] = None,
    language: Optional[str] = None,
    num_epochs: int = Query(3),
    use_lora: bool = Query(True),
) -> Dict[str, Any]:
    if model_manager is None:
        raise HTTPException(status_code=500, detail="Fine-tuning not initialized")
    mtype = ModelType(model_type.lower())
    job_id = await model_manager.create_fine_tune_job(
        model_type=mtype,
        dataset_id=dataset_id,
        genre=genre,
        language=language,
        num_epochs=num_epochs,
        use_lora=use_lora,
    )
    return {"job_id": job_id, "status": "started", "model_type": model_type, "use_lora": use_lora}


@router.get("/jobs/{job_id}/status")
async def get_job_status(job_id: str) -> Dict[str, Any]:
    if model_manager is None:
        raise HTTPException(status_code=500, detail="Fine-tuning not initialized")
    job = model_manager.training_jobs.get(job_id)
    if not job:
        return {"error": "Job not found"}
    return {
        "job_id": job_id,
        "stage": job["stage"],
        "progress": job["progress_percent"],
        "loss_history": job.get("loss_history", [])[-10:],
        "validation_loss": job.get("validation_loss"),
        "error": job.get("error_message"),
    }


@router.get("/models/active")
async def get_active_models() -> Dict[str, Any]:
    if model_manager is None:
        raise HTTPException(status_code=500, detail="Fine-tuning not initialized")
    models = await model_manager.get_active_models()
    return {"active_models": models, "count": len(models)}


@router.post("/models/{model_id}/activate")
async def activate_model(model_id: str) -> Dict[str, Any]:
    if model_manager is None:
        raise HTTPException(status_code=500, detail="Fine-tuning not initialized")
    success = await model_manager.activate_model(model_id)
    if not success:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"status": "activated", "model_id": model_id}


@router.post("/models/{model_id}/quantize")
async def quantize_model(model_id: str, bits: int = Query(4)) -> Dict[str, Any]:
    if model_manager is None:
        raise HTTPException(status_code=500, detail="Fine-tuning not initialized")
    path = await model_manager.quantize_model(model_id, bits)
    if not path:
        raise HTTPException(status_code=400, detail="Quantization failed")
    return {"status": "quantized", "model_id": model_id, "bits": bits, "path": path}


@router.post("/ensemble/create")
async def create_ensemble(model_ids: list) -> Dict[str, Any]:
    if model_manager is None:
        raise HTTPException(status_code=500, detail="Fine-tuning not initialized")
    ensemble_id = await model_manager.merge_ensemble(model_ids)
    return {"ensemble_id": ensemble_id, "models_merged": model_ids, "status": "created"}


@router.post("/abtest/create")
async def create_ab_test(
    model_a: str,
    model_b: str,
    metric: str = Query("engagement"),
    sample_size: int = Query(1000),
) -> Dict[str, Any]:
    if ab_testing is None:
        raise HTTPException(status_code=500, detail="A/B testing not initialized")
    test_id = await ab_testing.create_ab_test(model_a=model_a, model_b=model_b, metric=metric, sample_size=sample_size)
    return {"test_id": test_id, "model_a": model_a, "model_b": model_b, "status": "running"}


@router.get("/abtest/{test_id}/status")
async def get_ab_test_status(test_id: str) -> Dict[str, Any]:
    if ab_testing is None:
        raise HTTPException(status_code=500, detail="A/B testing not initialized")
    status = await ab_testing.get_test_status(test_id)
    if not status:
        raise HTTPException(status_code=404, detail="Test not found")
    return status


@router.get("/models/performance")
async def get_models_performance() -> Dict[str, Any]:
    if model_manager is None:
        raise HTTPException(status_code=500, detail="Fine-tuning not initialized")
    models = await model_manager.get_active_models()
    return {"models": models, "total": len(models)}


@router.post("/models/{model_id}/rollback")
async def rollback_model(model_id: str) -> Dict[str, Any]:
    if model_manager is None:
        raise HTTPException(status_code=500, detail="Fine-tuning not initialized")
    metadata = model_manager.model_registry.get(model_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Model not found")
    await model_manager.activate_model(model_id)
    return {"status": "rollback_completed", "current_model": model_id}
