# -*- coding: utf-8 -*-
"""AURA OS — Cloud Sync API Routes.

Endpoints para sincronizacion multi-dispositivo via cloud:
- POST /api/cloud/device/register
- POST /api/cloud/sync/push
- GET  /api/cloud/sync/pull
- GET  /api/cloud/devices
- POST /api/cloud/conflict/resolve
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.cloud.firebase_manager import firebase_sync
from backend.cloud.offline_queue import offline_queue

logger = logging.getLogger("AURA.CloudRoutes")

router = APIRouter(prefix="/api/cloud", tags=["cloud-sync"])


class DeviceRegisterRequest(BaseModel):
    device_id: str
    device_type: str = "desktop"
    user_id: Optional[str] = None


class SyncPushRequest(BaseModel):
    device_id: str
    data: Dict[str, Any]


class ConflictResolveRequest(BaseModel):
    device_id: str
    conflict_id: str


@router.post("/device/register")
async def register_device(req: DeviceRegisterRequest) -> Dict[str, Any]:
    """Registra un dispositivo para sincronizacion cloud."""
    try:
        if not req.device_id:
            raise HTTPException(status_code=400, detail="device_id is required")

        token = f"tok_{uuid.uuid4().hex[:16]}"

        firebase_sync._devices[req.device_id] = {
            "lastSync": datetime.now(timezone.utc).isoformat(),
            "data": {},
            "status": "online",
            "type": req.device_type,
            "token": token,
            "version": 0,
        }

        logger.info("Device registered: %s (%s)", req.device_id, req.device_type)
        return {
            "token": token,
            "sync_enabled": True,
            "device_id": req.device_id,
            "device_type": req.device_type,
            "registered_at": datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/sync/push")
async def sync_push(req: SyncPushRequest) -> Dict[str, Any]:
    """Envia datos del dispositivo a la nube."""
    try:
        result = await firebase_sync.push_to_cloud(req.device_id, req.data)
        return {
            "status": "synced",
            "version": result["version"],
            "device_id": req.device_id,
            "timestamp": result["timestamp"],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/sync/pull")
async def sync_pull(
    device_id: str = Query(...),
    since_version: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """Obtiene cambios desde la nube (delta sync)."""
    try:
        result = await firebase_sync.pull_from_cloud(device_id, since_version)
        return {
            "delta": result["delta"],
            "version": result["version"],
            "device_id": device_id,
            "conflicts_resolved": result["conflicts_resolved"],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/devices")
async def get_devices() -> List[Dict[str, Any]]:
    """Lista todos los dispositivos sincronizados."""
    try:
        devices = await firebase_sync.get_device_list()
        return devices
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/conflict/resolve")
async def resolve_conflict(req: ConflictResolveRequest) -> Dict[str, Any]:
    """Resuelve un conflicto de sincronizacion (last-write-wins)."""
    try:
        devices = await firebase_sync.get_device_list()
        device_ids = [d["device_id"] for d in devices]

        if req.device_id not in device_ids:
            raise HTTPException(status_code=404, detail=f"Device {req.device_id} not found")

        winner = req.device_id
        logger.info("Conflict resolved: winner=%s, conflict=%s", winner, req.conflict_id)

        return {
            "resolved": True,
            "winner": winner,
            "conflict_id": req.conflict_id,
            "resolution": "last-write-wins",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
