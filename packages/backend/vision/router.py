"""
AURA Screen-Awareness Vision Router

Endpoints REST para captura y análisis de pantalla local.
Compatible con OSWorld-style desktop vision.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.vision.screen_bridge import (
    ScreenBridge,
    ScreenCaptureConfig,
    CaptureBackend,
    AnalysisMode,
    FrameData,
    VisionAnalysisResult,
    get_screen_bridge,
)

router = APIRouter(prefix="/api/vision", tags=["Screen Vision"])
logger = logging.getLogger("AURAScreenVision")


# Modelos Pydantic para requests/responses
class CaptureConfigRequest(BaseModel):
    backend: Optional[str] = Field(default="auto", description="Backend de captura: auto, pil, mss")
    interval_seconds: Optional[float] = Field(default=5.0, ge=0.5, le=60.0)
    max_dimension: Optional[int] = Field(default=1280, ge=320, le=3840)
    jpeg_quality: Optional[int] = Field(default=75, ge=10, le=100)
    compression_level: Optional[int] = Field(default=6, ge=1, le=9)
    monitor_index: Optional[int] = Field(default=0, ge=0)
    region: Optional[List[int]] = Field(default=None, description="[left, top, width, height]")
    enabled: bool = True


class AnalyzeRequest(BaseModel):
    mode: str = Field(default="full", description="Modo: full, fast, ocr, ui")
    session_id: str = Field(default="")
    region: Optional[List[int]] = Field(default=None, description="[left, top, width, height]")
    custom_prompt: Optional[str] = Field(default=None)


class MonitorRequest(BaseModel):
    mode: str = Field(default="fast", description="Modo: full, fast, ocr, ui")
    session_id: str = Field(default="")


class CaptureResponse(BaseModel):
    success: bool
    frame: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class AnalyzeResponse(BaseModel):
    success: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class MonitorStatusResponse(BaseModel):
    monitoring: bool
    mode: Optional[str] = None
    session_id: Optional[str] = None


# ============================================================
# Endpoints de configuración
# ============================================================

@router.get("/config")
async def get_vision_config() -> Dict[str, Any]:
    """Obtiene la configuración actual del bridge de visión."""
    bridge = get_screen_bridge()
    return bridge.get_status()


@router.post("/config")
async def update_vision_config(config: CaptureConfigRequest) -> Dict[str, Any]:
    """Actualiza la configuración de captura."""
    bridge = get_screen_bridge()
    
    try:
        backend = CaptureBackend(config.backend) if config.backend else CaptureBackend.AUTO
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid backend: {config.backend}")
    
    new_config = ScreenCaptureConfig(
        backend=backend,
        interval_seconds=config.interval_seconds or 5.0,
        max_dimension=config.max_dimension or 1280,
        jpeg_quality=config.jpeg_quality or 75,
        compression_level=config.compression_level or 6,
        monitor_index=config.monitor_index or 0,
        region=tuple(config.region) if config.region else None,
        enabled=config.enabled,
    )
    
    # Recrear captura con nueva config
    bridge.capture = ScreenCapture(new_config)
    bridge.config = new_config
    
    return {"success": True, "config": bridge.get_status()["capture"]}


# ============================================================
# Endpoints de captura
# ============================================================

@router.post("/capture", response_model=CaptureResponse)
async def capture_screen(
    region: Optional[List[int]] = Query(default=None, description="[left, top, width, height]"),
    monitor_index: int = Query(default=0, ge=0),
) -> CaptureResponse:
    """Captura un frame de la pantalla actual."""
    bridge = get_screen_bridge()
    
    region_tuple = tuple(region) if region else None
    frame = bridge.capture.capture(region=region_tuple)
    
    if frame is None:
        return CaptureResponse(success=False, error="Screen capture failed or disabled")
    
    return CaptureResponse(success=True, frame=frame.to_dict())


@router.get("/monitors")
async def get_monitors() -> Dict[str, Any]:
    """Lista monitores disponibles."""
    bridge = get_screen_bridge()
    monitors = bridge.capture.get_monitor_info()
    return {"monitors": monitors, "count": len(monitors)}


# ============================================================
# Endpoints de análisis
# ============================================================

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_screen(request: AnalyzeRequest) -> AnalyzeResponse:
    """Analiza la pantalla actual con el modo especificado."""
    bridge = get_screen_bridge()
    
    try:
        mode = AnalysisMode(request.mode)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid mode: {request.mode}")
    
    region_tuple = tuple(request.region) if request.region else None
    
    result = bridge.analyze_screen(
        mode=mode,
        session_id=request.session_id,
        region=region_tuple,
        custom_prompt=request.custom_prompt,
    )
    
    return AnalyzeResponse(success=True, result=result.to_dict())


@router.post("/analyze-frame", response_model=AnalyzeResponse)
async def analyze_frame(frame_data: Dict[str, Any], mode: str = "full", session_id: str = "") -> AnalyzeResponse:
    """Analiza un frame ya capturado (base64)."""
    bridge = get_screen_bridge()
    
    try:
        mode_enum = AnalysisMode(mode)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid mode: {mode}")
    
    try:
        frame = FrameData(
            timestamp=frame_data.get("timestamp", 0),
            image_base64=frame_data.get("image_base64", ""),
            width=frame_data.get("width", 0),
            height=frame_data.get("height", 0),
            format=frame_data.get("format", "JPEG"),
            monitor_index=frame_data.get("monitor_index", 0),
            region=frame_data.get("region"),
            metadata=frame_data.get("metadata", {}),
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid frame data: {exc}")
    
    if not frame.image_base64:
        raise HTTPException(status_code=422, detail="image_base64 is required")
    
    result = bridge.analyze_frame(frame, mode=mode_enum, session_id=session_id)
    return AnalyzeResponse(success=True, result=result.to_dict())


# ============================================================
# Endpoints de monitoreo continuo
# ============================================================

# Variable para almacenar callback de monitoreo (simplificado)
_monitor_callbacks: Dict[str, list] = {}


@router.post("/monitor/start", response_model=MonitorStatusResponse)
async def start_monitoring(request: MonitorRequest) -> MonitorStatusResponse:
    """Inicia monitoreo continuo de la pantalla."""
    bridge = get_screen_bridge()
    
    try:
        mode = AnalysisMode(request.mode)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid mode: {request.mode}")
    
    success = bridge.start_monitoring(mode=mode, session_id=request.session_id)
    
    return MonitorStatusResponse(
        monitoring=success,
        mode=request.mode if success else None,
        session_id=request.session_id if success else None,
    )


@router.post("/monitor/stop", response_model=MonitorStatusResponse)
async def stop_monitoring() -> MonitorStatusResponse:
    """Detiene el monitoreo continuo."""
    bridge = get_screen_bridge()
    bridge.stop_monitoring()
    return MonitorStatusResponse(monitoring=False)


@router.get("/monitor/status", response_model=MonitorStatusResponse)
async def monitor_status() -> MonitorStatusResponse:
    """Estado del monitoreo continuo."""
    bridge = get_screen_bridge()
    status = bridge.get_status()
    return MonitorStatusResponse(
        monitoring=status.get("monitoring", False),
    )


# ============================================================
# Endpoints de estado y utilidades
# ============================================================

@router.get("/status")
async def vision_status() -> Dict[str, Any]:
    """Estado completo del sistema de visión."""
    bridge = get_screen_bridge()
    return bridge.get_status()


@router.get("/last-analysis")
async def get_last_analysis() -> Dict[str, Any]:
    """Último análisis realizado."""
    bridge = get_screen_bridge()
    last = bridge._last_analysis
    if last:
        return {"success": True, "analysis": last.to_dict()}
    return {"success": False, "analysis": None, "message": "No analysis performed yet"}


@router.post("/capture-save")
async def capture_and_save(
    path: str = Query(..., description="Ruta donde guardar"),
    region: Optional[List[int]] = Query(default=None, description="[left, top, width, height]"),
) -> Dict[str, Any]:
    """Captura pantalla y guarda a archivo."""
    bridge = get_screen_bridge()
    region_tuple = tuple(region) if region else None
    
    success = bridge.capture.capture_to_file(path, region=region_tuple)
    
    return {
        "success": success,
        "path": path if success else None,
        "error": None if success else "Failed to save capture",
    }