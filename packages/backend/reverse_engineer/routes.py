"""
Rutas API REST para el Reverse Engineer Bridge (REA).

Endpoints:
- GET  /api/rea/status       — Estado del servicio REA.
- POST /api/rea/analyze-url  — Navega y analiza una página web.
- POST /api/rea/analyze-youtube — Descarga y analiza un video de YouTube.
- POST /api/rea/fuse-mod      — Fusiona un personaje/mod entre juegos.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.reverse_engineer.rea_bridge import get_rea_bridge

router = APIRouter(prefix="/api/rea", tags=["reverse-engineer"])


class AnalyzeURLRequest(BaseModel):
    url: str = Field(..., description="URL pública a analizar")


class AnalyzeYouTubeRequest(BaseModel):
    url: str = Field(..., description="URL de video de YouTube")


class FuseModRequest(BaseModel):
    source_game: str = Field(..., description="Camino al juego/binario origen")
    target_game: str = Field(..., description="Camino al juego/binario destino")
    character: str = Field(..., description="Nombre del personaje o mod a fusionar")


class CloneSoftwareRequest(BaseModel):
    target: str = Field(..., description="URL o ruta al software/binario a clonar")
    output_dir: str = Field(..., description="Directorio donde guardar el código clonado")


class ConnectProviderRequest(BaseModel):
    provider: str = Field(..., description="Proveedor: ghidra, hopper o ida")
    credentials: dict = Field(default_factory=dict, description="Credenciales/path del proveedor")


@router.get("/status")
async def rea_status() -> Dict[str, Any]:
    """Devuelve el estado del servicio REA."""
    bridge = get_rea_bridge()
    return {
        "available": bridge.is_available(),
        "port": bridge._port,
        "yt_dlp_available": bridge._yt_dlp_path is not None,
        "whisper_model": bridge._whisper_model,
        "providers": bridge.get_providers(),
        "rea_path": str(bridge._rea_path),
    }


@router.post("/analyze-url")
async def analyze_url(payload: AnalyzeURLRequest) -> Dict[str, Any]:
    """Navega y analiza una página web usando REA (o fallback local)."""
    bridge = get_rea_bridge()
    try:
        result = await bridge.analyze_website(payload.url)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/analyze-youtube")
async def analyze_youtube(payload: AnalyzeYouTubeRequest) -> Dict[str, Any]:
    """Descarga, transcribe e indexa un video de YouTube."""
    bridge = get_rea_bridge()
    try:
        result = await bridge.analyze_youtube_video(payload.url)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/fuse-mod")
async def fuse_mod(payload: FuseModRequest) -> Dict[str, Any]:
    """Fusiona un personaje/mod de un juego origen a un juego destino."""
    bridge = get_rea_bridge()
    try:
        result = await bridge.fuse_game_mod(
            payload.source_game, payload.target_game, payload.character
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/clone-software")
async def clone_software(payload: CloneSoftwareRequest) -> Dict[str, Any]:
    """Pipeline completo de clonación de software usando REA + AURA."""
    bridge = get_rea_bridge()
    try:
        result = await bridge.clone_software(payload.target, payload.output_dir)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/connect-provider")
async def connect_provider(payload: ConnectProviderRequest) -> Dict[str, Any]:
    """Conecta una cuenta de proveedor de análisis nativo (Ghidra/IDA/Hopper)."""
    bridge = get_rea_bridge()
    try:
        result = await bridge.connect_account(payload.provider, **payload.credentials)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/providers")
async def list_providers() -> Dict[str, Any]:
    """Lista proveedores de análisis nativo configurados."""
    bridge = get_rea_bridge()
    return {"providers": bridge.get_providers()}
