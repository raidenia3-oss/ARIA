"""AURA Local Media Gallery — endpoints REST (Bloque 47).

- GET  /api/story/{work_id}/media/status          — estado del gestor.
- POST /api/story/{work_id}/media                 — subir asset (multipart).
- GET  /api/story/{work_id}/media                 — listar con filtros.
- GET  /api/story/{work_id}/media/stats           — estadísticas.
- GET  /api/story/{work_id}/media/{asset_id}      — metadatos de asset.
- GET  /api/story/{work_id}/media/{asset_id}/file — descargar original.
- GET  /api/story/{work_id}/media/{asset_id}/thumb — descargar thumbnail.
- PUT  /api/story/{work_id}/media/{asset_id}      — actualizar metadatos.
- POST /api/story/{work_id}/media/{asset_id}/link/character — vincular personaje.
- POST /api/story/{work_id}/media/{asset_id}/link/codex     — vincular codex.
- DELETE /api/story/{work_id}/media/{asset_id}    — borrar asset.

Autenticación: si AURA_API_KEY está definida se exige X-API-Key
(local-first: sin key configurada, el endpoint queda abierto en red local).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from backend.media.manager import (
    AssetKind,
    MediaManager,
    get_media_manager,
    reset_media_manager,
)

logger = logging.getLogger("AURA.Media.Routes")

router = APIRouter(prefix="/api/story/{work_id}/media", tags=["media-gallery"])


def _check_api_key(provided: Optional[str]) -> None:
    expected = os.getenv("AURA_API_KEY", "")
    if expected and provided != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


def _mgr() -> MediaManager:
    return get_media_manager()


@router.get("/status")
async def media_status(
    work_id: str,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    if not _mgr().storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    return {"status": "ok", "work_id": work_id, "media_root": str(_mgr().media_root)}


@router.post("", status_code=201)
async def media_upload(
    work_id: str,
    file: UploadFile = File(...),
    kind: str = Form(AssetKind.OTHER.value),
    title: str = Form(""),
    char_id: str = Form(""),
    codex_entry_id: str = Form(""),
    tags: str = Form(""),
    asset_id: str = Form(""),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    if not _mgr().storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="empty_file")
    import io
    stream = io.BytesIO(data)
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    aid = asset_id if asset_id else None
    res = _mgr().ingest(
        work_id=work_id,
        stream=stream,
        filename=file.filename or "asset",
        mime=file.content_type or "application/octet-stream",
        kind=kind,
        title=title,
        char_id=char_id,
        codex_entry_id=codex_entry_id,
        tags=tag_list,
        asset_id=aid,
    )
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["error"])
    return res


@router.get("")
async def media_list(
    work_id: str,
    kind: Optional[str] = Query(None),
    char_id: Optional[str] = Query(None),
    codex_entry_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    if not _mgr().storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    return _mgr().list(
        work_id, kind=kind, char_id=char_id,
        codex_entry_id=codex_entry_id, limit=limit, offset=offset,
    )


@router.get("/stats")
async def media_stats(
    work_id: str,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    if not _mgr().storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    return _mgr().stats(work_id)


@router.get("/{asset_id}")
async def media_get(
    work_id: str,
    asset_id: str,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    if not _mgr().storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    res = _mgr().get(work_id, asset_id)
    if res["status"] == "error":
        raise HTTPException(status_code=404, detail=res["error"])
    return res


@router.get("/{asset_id}/file")
async def media_file(
    work_id: str,
    asset_id: str,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> FileResponse:
    _check_api_key(x_api_key)
    if not _mgr().storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    path = _mgr().file_path(work_id, asset_id, thumb=False)
    if not path:
        raise HTTPException(status_code=404, detail="file_not_found")
    asset = _mgr().get(work_id, asset_id)["asset"]
    return FileResponse(path=path, media_type=asset["mime"], filename=asset["filename"])


@router.get("/{asset_id}/thumb")
async def media_thumb(
    work_id: str,
    asset_id: str,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> FileResponse:
    _check_api_key(x_api_key)
    if not _mgr().storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    path = _mgr().file_path(work_id, asset_id, thumb=True)
    if not path:
        raise HTTPException(status_code=404, detail="thumb_not_found")
    asset = _mgr().get(work_id, asset_id)["asset"]
    return FileResponse(path=path, media_type="image/webp", filename=f"thumb_{asset['filename']}")


@router.put("/{asset_id}")
async def media_update(
    work_id: str,
    asset_id: str,
    payload: Dict[str, Any],
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    if not _mgr().storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    res = _mgr().update(work_id, asset_id, payload)
    if res["status"] == "error":
        raise HTTPException(status_code=404, detail=res["error"])
    return res


@router.post("/{asset_id}/link/character")
async def media_link_character(
    work_id: str,
    asset_id: str,
    char_id: str = Form(...),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    if not _mgr().storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    res = _mgr().link_character(work_id, asset_id, char_id)
    if res["status"] == "error":
        raise HTTPException(status_code=404, detail=res["error"])
    return res


@router.post("/{asset_id}/link/codex")
async def media_link_codex(
    work_id: str,
    asset_id: str,
    codex_entry_id: str = Form(...),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    if not _mgr().storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    res = _mgr().link_codex(work_id, asset_id, codex_entry_id)
    if res["status"] == "error":
        raise HTTPException(status_code=404, detail=res["error"])
    return res


@router.delete("/{asset_id}")
async def media_delete(
    work_id: str,
    asset_id: str,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    _check_api_key(x_api_key)
    if not _mgr().storage.work_exists(work_id):
        raise HTTPException(status_code=404, detail="work_not_found")
    res = _mgr().delete(work_id, asset_id)
    if res["status"] == "error":
        raise HTTPException(status_code=404, detail=res["error"])
    return res