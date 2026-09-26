"""Update routes for AURA."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.update_manager import UpdateManager, VersionTracker

router = APIRouter(prefix="/api/updates", tags=["updates"])

update_manager = UpdateManager()
version_tracker = VersionTracker()


class CheckUpdateRequest(BaseModel):
    client_version: str


class InstalledRequest(BaseModel):
    version: str


class RollbackRequest(BaseModel):
    version: str


@router.get("/check")
async def check_for_updates(client_version: str = Query(...)) -> Dict[str, Any]:
    result = update_manager.check_for_updates(client_version)
    return result


@router.get("/latest")
async def get_latest_version() -> Dict[str, Any]:
    latest = update_manager.get_latest_version()
    info = update_manager.get_version_info(latest)
    return {
        "version": latest,
        "info": info,
        "download_url": f"/api/updates/download/{latest}",
    }


@router.get("/download/{version}")
async def download_patch(version: str) -> Dict[str, Any]:
    patch = update_manager.get_version_info(version)
    if not patch:
        raise HTTPException(status_code=404, detail=f"Patch para v{version} no encontrado")
    return {
        "version": version,
        "size_mb": 0.0,
        "checksum": patch.get("checksum", ""),
        "changes": patch.get("features", []),
        "download_path": f"/updates/patches/{version}.zip",
    }


@router.post("/installed/{version}")
async def confirm_update_installed(version: str) -> Dict[str, Any]:
    version_tracker.save_version(version)
    version_tracker.add_installed_patch(version)
    return {
        "status": "confirmed",
        "version": version,
        "message": f"Actualización a v{version} confirmada",
    }


@router.post("/rollback/{version}")
async def rollback_to_version(version: str) -> Dict[str, Any]:
    success = update_manager.rollback_version(version)
    if success:
        version_tracker.save_version(version)
        return {
            "status": "success",
            "version": version,
            "message": f"Rollback a v{version} exitoso",
        }
    raise HTTPException(status_code=400, detail=f"No se pudo hacer rollback a v{version}")


@router.get("/changelog")
async def get_changelog(
    from_version: str = Query("3.1.0"), to_version: str = Query("latest")
) -> Dict[str, Any]:
    if to_version == "latest":
        to_version = update_manager.get_latest_version()
    changelog = update_manager._generate_changelog(from_version, to_version)
    return {"from": from_version, "to": to_version, "changelog": changelog}


@router.get("/history")
async def get_version_history() -> Dict[str, Any]:
    return update_manager.version_history
