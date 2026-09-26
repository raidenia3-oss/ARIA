# -*- coding: utf-8 -*-
"""AURA OS — Storage API Routes."""
from __future__ import annotations

from fastapi import APIRouter, Body, Query
from typing import Any, Dict, List, Optional

router = APIRouter(prefix="/api/storage", tags=["storage"])


@router.get("/status")
async def storage_status() -> Dict[str, Any]:
    from backend.storage.storage_manager import storage_manager
    from backend.config.storage_config import storage_config
    return {
        "summary": storage_manager.get_storage_summary(),
        "config": storage_config.to_dict(),
    }


@router.post("/offload")
async def offload_file(source_path: str = Body(...)) -> Dict[str, Any]:
    from backend.storage.usb_storage_manager import usb_storage_manager
    try:
        job = usb_storage_manager.offload_file(source_path)
        return {"success": True, "job": job.__dict__}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@router.get("/usb")
async def usb_status() -> Dict[str, Any]:
    from backend.storage.usb_storage_manager import usb_storage_manager
    return usb_storage_manager.get_usb_status()


@router.post("/cleanup")
async def cleanup_cache(directory: str = "data",
                        max_size_mb: int = Query(500, ge=10)) -> Dict[str, Any]:
    from backend.storage.storage_manager import storage_manager
    return storage_manager.cleanup_cache(max_size_mb=max_size_mb)


@router.post("/compress")
async def compress_videos(directory: str = "data") -> Dict[str, Any]:
    from backend.storage.storage_manager import storage_manager
    return storage_manager.compress_videos(directory=directory)


@router.post("/auto-cleanup")
async def auto_cleanup() -> Dict[str, Any]:
    from backend.storage.storage_manager import storage_manager
    return storage_manager.auto_cleanup()


@router.get("/offload/history")
async def offload_history(limit: int = Query(20, ge=1, le=100)) -> Dict[str, Any]:
    from backend.storage.usb_storage_manager import usb_storage_manager
    return {"history": usb_storage_manager.get_offload_history(limit)}
