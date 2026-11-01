# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

try:
    from backend.core.aria_runtime import aria_runtime
except Exception:
    aria_runtime = None

router = APIRouter(prefix='/aria', tags=['aria'])

class UnderstandReq(BaseModel):
    q: str
    max_frames: Optional[int] = 6
    headless: Optional[bool] = True

@router.post('/understand')
async def understand(req: UnderstandReq) -> Dict[str, Any]:
    if aria_runtime is None:
        raise HTTPException(status_code=503, detail='runtime_not_ready')
    await aria_runtime.start()
    res = await aria_runtime.understand(req.q, max_frames=req.max_frames or 6, headless=req.headless if req.headless is not None else True)
    return res

@router.get('/status')
async def status() -> Dict[str, Any]:
    if aria_runtime is None:
        return {'ok': False}
    return {'ok': True, 'status': aria_runtime.status()}

@router.post('/start')
async def start() -> Dict[str, Any]:
    if aria_runtime is None:
        raise HTTPException(status_code=503, detail='runtime_not_ready')
    await aria_runtime.start()
    return {'ok': True, 'status': aria_runtime.status()}

@router.post('/stop')
async def stop() -> Dict[str, Any]:
    if aria_runtime is None:
        raise HTTPException(status_code=503, detail='runtime_not_ready')
    await aria_runtime.stop()
    return {'ok': True}
