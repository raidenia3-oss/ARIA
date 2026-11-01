# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

try:
    from backend.social.social_understander import social_understander
except Exception:
    social_understander = None

router = APIRouter(prefix='/social', tags=['social'])

class UnderstandReq(BaseModel):
    url: HttpUrl
    max_frames: Optional[int] = 8
    headless: Optional[bool] = True

@router.post('/understand')
async def understand(req: UnderstandReq) -> Dict[str, Any]:
    if social_understander is None:
        raise HTTPException(status_code=503, detail='understander_not_ready')
    res = await social_understander.understand(str(req.url), max_frames=req.max_frames or 8, headless=req.headless if req.headless is not None else True)
    if not res.get('ok'):
        raise HTTPException(status_code=500, detail=res.get('error','failed'))
    return res

@router.get('/understand/capabilities')
async def caps() -> Dict[str, Any]:
    return {
        'ok': True,
        'downloads': False,
        'method': 'viewport-frame-sampling + fusion',
        'platforms_universal': True,
        'formats': ['reels','shorts','story','video','photo','carousel','live','post'],
    }
