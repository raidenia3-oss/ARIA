# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
try:
    from backend.aria_nucleus.nucleus import aria_nucleus
except Exception:
    aria_nucleus = None
try:
    from backend.aria_nucleus.kernel import AriaMode
except Exception:
    class AriaMode: REACTIVE='reactive'
router = APIRouter(prefix='/aria/nucleus', tags=['aria-nucleus'])
class ProcReq(BaseModel):
    input: str
    context: Optional[Dict[str,Any]] = None
@router.post('/process')
async def process(req: ProcReq):
    if not aria_nucleus: raise HTTPException(503,'nucleus_not_ready')
    aria_nucleus.start()
    return await aria_nucleus.process(req.input, context=req.context or {})
@router.get('/status')
async def status():
    if not aria_nucleus: return {'ok':False}
    return {'ok':True,'status':aria_nucleus.status()}
@router.get('/heartbeat')
async def heartbeat():
    if not aria_nucleus: return {'ok':False}
    return {'ok':True,'heartbeat':aria_nucleus.kernel.heartbeat()}
@router.post('/autonomous/start')
async def autostart(interval:float=30.0):
    if not aria_nucleus: raise HTTPException(503,'nucleus_not_ready')
    aria_nucleus.start()
    aria_nucleus.start_autonomous(interval)
    return {'ok':True,'mode':aria_nucleus.kernel.mode.value}
@router.post('/autonomous/stop')
async def autostop():
    if not aria_nucleus: raise HTTPException(503,'nucleus_not_ready')
    aria_nucleus.kernel.set_mode(AriaMode.REACTIVE)
    return {'ok':True,'mode':aria_nucleus.kernel.mode.value}
