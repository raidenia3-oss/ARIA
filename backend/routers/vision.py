"""Vision router for AURA - Frame analysis and screenshot ingestion."""

from __future__ import annotations

import io
import logging
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from backend.services.vision_engine import VisionEngine

router = APIRouter()
logger = logging.getLogger("AURAVision")

try:
    from backend.orchestrator import orchestrator
except Exception:
    orchestrator = None

vision_engine = VisionEngine(orchestrator=orchestrator)


@router.post("/vision/analyze-frame")
async def analyze_frame(payload: Dict[str, Any]) -> Dict[str, Any]:
    image_b64 = str(payload.get("image", "")).strip()
    session_id = str(payload.get("session_id", ""))
    if not image_b64:
        raise HTTPException(status_code=422, detail="image is required")
    result = vision_engine.analyze_frame(image_b64, session_id=session_id)
    return result


@router.post("/vision/screenshot")
async def analyze_screenshot(payload: Dict[str, Any]) -> Dict[str, Any]:
    image_b64 = str(payload.get("image", "")).strip()
    session_id = str(payload.get("session_id", ""))
    if not image_b64:
        raise HTTPException(status_code=422, detail="image is required")
    result = vision_engine.analyze_screenshot(image_b64, session_id=session_id)
    return result


@router.get("/vision/status")
async def vision_status() -> Dict[str, Any]:
    return vision_engine.get_status()
