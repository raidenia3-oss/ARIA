# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

try:
    from backend.social.video_stream_analyzer import social_video_analyzer
except Exception:
    social_video_analyzer = None

try:
    from backend.social import social_browser
except Exception:
    social_browser = None

logger = logging.getLogger('ARIA.Routers.SocialVideo')

router = APIRouter(prefix='/social-video', tags=['social-video'])

class FrameIn(BaseModel):
    t: float
    image_b64: str
    mime: Optional[str] = 'image/jpeg'

class AnalyzeFramesReq(BaseModel):
    url: HttpUrl
    frames: List[FrameIn]
    audio_transcript: Optional[str] = None
    fps_sample: Optional[float] = 0.5

class BrowseReq(BaseModel):
    url: HttpUrl
    max_frames: Optional[int] = 12
    interval_ms: Optional[int] = 600
    headless: Optional[bool] = True

@router.post('/analyze-frames')
async def analyze_frames(req: AnalyzeFramesReq) -> Dict[str, Any]:
    if social_video_analyzer is None:
        raise HTTPException(status_code=503, detail='analyzer_not_ready')
    try:
        res = await social_video_analyzer.analyze_from_frames(
            url=str(req.url),
            frames_b64=[f.model_dump() for f in req.frames],
            audio_transcript=req.audio_transcript,
            fps_sample=req.fps_sample or 0.5,
        )
        return {'ok': True, 'result': res.__dict__}
    except Exception as e:
        logger.exception('social-video analyze-frames failed')
        raise HTTPException(status_code=500, detail=str(e))

@router.post('/browse')
async def browse(req: BrowseReq) -> Dict[str, Any]:
    if social_browser is None:
        raise HTTPException(status_code=503, detail='browser_not_ready')
    try:
        res = await social_browser.browse_and_analyze(
            url=str(req.url),
            max_frames=req.max_frames or 12,
            interval_ms=req.interval_ms or 600,
            headless=req.headless if req.headless is not None else True,
        )
        return {'ok': True, 'result': asdict(res)}
    except Exception as e:
        logger.exception('social-video browse failed')
        raise HTTPException(status_code=500, detail=str(e))

@router.get('/capabilities')
async def capabilities() -> Dict[str, Any]:
    return {
        'ok': True,
        'method': 'viewport-frame-sampling',
        'downloads_mp4': False,
        'platforms': ['instagram', 'tiktok', 'youtube', 'x', 'facebook', 'linkedin', 'threads', 'bluesky', 'pinterest', 'reddit'],
        'notes': 'Navega y captura fotogramas renderizados (base64 en memoria). Nunca descarga MP4.',
    }
