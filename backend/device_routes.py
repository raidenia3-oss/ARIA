"""Device routes for AURA."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, WebSocket
from fastapi.responses import JSONResponse

from backend.app_generator import AppGenerator
from backend.device_orchestrator import DeviceCapability, DeviceOrchestrator, DeviceType, DistributedTask

router = APIRouter(prefix="/api/devices", tags=["devices"])

orchestrator: Optional[DeviceOrchestrator] = None
app_generator: Optional[AppGenerator] = None


def init_device_modules(db_session_factory) -> None:
    global orchestrator, app_generator
    orchestrator = DeviceOrchestrator(db_session_factory)
    app_generator = AppGenerator(db_session_factory)


@router.post("/register")
async def register_device(device_type: str, device_name: str, ip_address: str) -> Dict[str, Any]:
    device_id = str(uuid.uuid4())
    profile = await orchestrator.register_device(
        device_id=device_id,
        device_type=device_type,
        device_name=device_name,
        ip_address=ip_address,
    )
    return {
        "device_id": device_id,
        "status": "registered",
        "profile": {
            "cpu_cores": profile.cpu_cores,
            "ram_gb": profile.ram_gb,
            "capabilities": profile.capabilities,
        },
    }


@router.get("/cluster/status")
async def get_cluster_status() -> Dict[str, Any]:
    if orchestrator is None:
        return {"online_devices": 0, "total_devices": 0, "devices": []}
    return await orchestrator.get_cluster_status()


@router.post("/tasks/submit")
async def submit_task(task_type: str, priority: int = 5, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    capability_map = {
        "narrative": DeviceCapability.NARRATIVE.value,
        "mobile": DeviceCapability.MOBILE_AUTO.value,
        "analytics": DeviceCapability.ANALYTICS.value,
        "training": DeviceCapability.TRAINING.value,
    }
    task = DistributedTask(
        task_id=str(uuid.uuid4()),
        task_type=task_type,
        priority=priority,
        required_capability=capability_map.get(task_type, DeviceCapability.ANALYTICS.value),
        status="pending",
        assigned_device=None,
        created_at=datetime.now().isoformat(),
        started_at=None,
        completed_at=None,
        result=None,
        payload=payload or {},
    )
    task_id = await orchestrator.submit_task(task)
    return {"task_id": task_id, "status": "submitted", "position_in_queue": len(orchestrator.task_queue)}


@router.post("/apps/generate")
async def generate_app(app_type: str, app_name: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if app_generator is None:
        raise JSONResponse(status_code=500, content={"error": "App generator not initialized"})
    config = config or {}
    if app_type == "apk":
        path = await app_generator.generate_android_apk(app_name, config)
    elif app_type == "exe":
        path = await app_generator.generate_windows_exe(app_name, config)
    elif app_type == "web":
        path = await app_generator.generate_web_app(app_name, config)
    else:
        return {"error": "Invalid app type"}
    return {
        "app_type": app_type,
        "app_name": app_name,
        "download_url": f"/api/devices/apps/{app_name}/download",
        "generated_at": datetime.now().isoformat(),
    }


@router.get("/apps/{app_name}/download")
async def download_app(app_name: str) -> Dict[str, Any]:
    if app_generator is None:
        return {"error": "App generator not initialized"}
    if app_name not in app_generator.generated_apps:
        return {"error": "App not found"}
    app_path = app_generator.generated_apps[app_name]["path"]
    return {"download_url": app_path}
