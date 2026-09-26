# -*- coding: utf-8 -*-
"""AURA OS - AME Sync REST Endpoints (/api/ame/sync)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter

from backend.integrations.ame_sync_manager import AMESyncManager, get_ame_sync

router = APIRouter(prefix="/api/ame", tags=["ame_sync"])


@router.get("/sync/status", response_model=Dict[str, Any])
async def ame_sync_status():
    """Estado de la sync con AME: conectado, ultima sync, version LoRA."""
    ame = get_ame_sync()
    return {
        "ame_connected": True,
        "last_sync": ame.last_sync,
        "lora_version": ame.lora_version,
        "ame_device_id": ame.ame_device_id,
        "sync_entries": len(ame.sync_log),
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/sync/now", response_model=Dict[str, Any])
async def ame_sync_now():
    """Fuerza una sync bidireccional inmediata PC <-> AME."""
    ame = get_ame_sync()
    result = await ame.sync_bidirectional()
    return {"success": True, "result": result}


@router.get("/sync/log", response_model=Dict[str, Any])
async def ame_sync_log(limit: int = 20):
    """Historial de los ultimos N syncs."""
    ame = get_ame_sync()
    return {
        "sync_log": ame.sync_log[-limit:] if limit > 0 else ame.sync_log,
        "total_entries": len(ame.sync_log),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/insights", response_model=Dict[str, Any])
async def ame_insights(limit: int = 10):
    """Insights recibidos de AME (ultimos N)."""
    ame = get_ame_sync()
    return {
        "insights": ame.sync_log[-limit:] if limit > 0 else ame.sync_log,
        "total_entries": len(ame.sync_log),
        "timestamp": datetime.now().isoformat(),
    }