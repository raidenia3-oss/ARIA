"""AURA Local Backup & Snapshot Engine — endpoints REST (BLOQUE 49).

- POST   /api/story/{work_id}/snapshots              — crear snapshot manual
- GET    /api/story/{work_id}/snapshots              — listar snapshots
- GET    /api/story/{work_id}/snapshots/{snap_id}    — metadatos de snapshot
- POST   /api/story/{work_id}/snapshots/{snap_id}/restore — restaurar snapshot
- DELETE /api/story/{work_id}/snapshots/{snap_id}    — eliminar snapshot
- POST   /api/story/{work_id}/snapshots/cleanup      — limpiar snapshots antiguos

Autenticación: si AURA_API_KEY está definida se exige X-API-Key
(local-first: sin key configurada, el endpoint queda abierto en red local).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Query

from backend.backup.snapshot import (
    LocalSnapshotEngine,
    get_backup_engine,
    reset_backup_engine,
)

router = APIRouter(prefix="/api/story/{work_id}/snapshots", tags=["backup-snapshots"])


def _check_api_key(provided: Optional[str]) -> None:
    expected = os.getenv("AURA_API_KEY", "")
    if expected and provided != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


def _engine() -> LocalSnapshotEngine:
    return get_backup_engine()


@router.post("", status_code=201)
async def create_snapshot(
    work_id: str,
    message: str = "manual backup",
    author: str = "ame",
    components: Optional[List[str]] = Query(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Crea una instantánea comprimida completa de la obra."""
    _check_api_key(x_api_key)
    if not _engine().storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    res = _engine().create_snapshot(work_id, message=message, author=author, components=components)
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["error"])
    return res


@router.get("")
async def list_snapshots(
    work_id: str,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Lista todas las instantáneas de una obra."""
    _check_api_key(x_api_key)
    if not _engine().storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    return _engine().list_snapshots(work_id)


@router.get("/{snap_id}")
async def get_snapshot(
    work_id: str,
    snap_id: str,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Obtiene metadatos de una instantánea."""
    _check_api_key(x_api_key)
    if not _engine().storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    res = _engine().get_snapshot(work_id, snap_id)
    if res["status"] == "error":
        raise HTTPException(status_code=404, detail=res["error"])
    return res


@router.post("/{snap_id}/restore")
async def restore_snapshot(
    work_id: str,
    snap_id: str,
    target_work_id: Optional[str] = Query(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Restaura una obra desde una instantánea."""
    _check_api_key(x_api_key)
    if not _engine().storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    res = _engine().restore_snapshot(work_id, snap_id, target_work_id=target_work_id)
    if res["status"] == "error":
        raise HTTPException(status_code=404, detail=res["error"])
    return res


@router.delete("/{snap_id}")
async def delete_snapshot(
    work_id: str,
    snap_id: str,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Elimina una instantánea."""
    _check_api_key(x_api_key)
    if not _engine().storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    res = _engine().delete_snapshot(work_id, snap_id)
    if res["status"] == "error":
        raise HTTPException(status_code=404, detail=res["error"])
    return res


@router.post("/cleanup")
async def cleanup_snapshots(
    work_id: str,
    keep: int = Query(10, ge=1, le=100),
    max_age_days: int = Query(0, ge=0, le=365),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Limpia instantáneas antiguas (mantiene las N más recientes y elimina > max_age_days)."""
    _check_api_key(x_api_key)
    if not _engine().storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    removed = _engine().cleanup_old(work_id, keep=keep, max_age_days=max_age_days)
    return {"status": "ok", "work_id": work_id, "removed": removed, "keep": keep, "max_age_days": max_age_days}