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

@router.get('/capabilities')
async def capabilities() -> Dict[str, Any]:
    return {
        'ok': True,
        'method': 'viewport-frame-sampling',
        'downloads_mp4': False,
        'platforms': ['instagram', 'tiktok', 'youtube', 'x', 'facebook', 'linkedin', 'threads', 'bluesky', 'pinterest', 'reddit'],
        'notes': 'Analiza fotogramas renderizados (base64 en memoria). No guarda MP4. Reutiliza VisionEngine.',
    }
