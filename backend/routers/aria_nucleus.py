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
    from backend.aria_nucleus.kernel import AriaMode, AriaAspect
except Exception:
    class AriaMode: REACTIVE='reactive'
    class AriaAspect: FUSED='fused'
router = APIRouter(prefix='/aria/nucleus', tags=['aria-nucleus'])
class ProcReq(BaseModel):
    input: str
    context: Optional[Dict[str,Any]] = None
class AnalyzeReq(BaseModel):
    subject: str
    depth: int = 3
    aspect: Optional[str] = None
class TransformReq(BaseModel):
    target: str
    into: str
class AspectReq(BaseModel):
    aspect: str
class SkillActivateReq(BaseModel):
    skill_id: str
class SacrificeReq(BaseModel):
    donor_id: str
    target_id: str
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
@router.get('/skills')
async def skills():
    if not aria_nucleus: return {'ok':False}
    return {'ok':True,'skills':aria_nucleus.list_skills()}
@router.post('/skills/activate')
async def skill_activate(req: SkillActivateReq):
    if not aria_nucleus: raise HTTPException(503,'nucleus_not_ready')
    return aria_nucleus.activate_skill(req.skill_id)
@router.post('/skills/deactivate')
async def skill_deactivate(req: SkillActivateReq):
    if not aria_nucleus: raise HTTPException(503,'nucleus_not_ready')
    return aria_nucleus.deactivate_skill(req.skill_id)
@router.post('/skills/sacrifice')
async def skill_sacrifice(req: SacrificeReq):
    if not aria_nucleus: raise HTTPException(503,'nucleus_not_ready')
    if not aria_nucleus.can_sacrifice(req.donor_id, req.target_id):
        raise HTTPException(400,'cannot_sacrifice')
    return aria_nucleus.sacrifice_skill(req.donor_id, req.target_id)
@router.post('/analyze')
async def analyze(req: AnalyzeReq):
    if not aria_nucleus: raise HTTPException(503,'nucleus_not_ready')
    aria_nucleus.start()
    return await aria_nucleus.analyze(req.subject, depth=req.depth, aspect=req.aspect)
@router.post('/transform')
async def transform(req: TransformReq):
    if not aria_nucleus: raise HTTPException(503,'nucleus_not_ready')
    aria_nucleus.start()
    return await aria_nucleus.transform(req.target, req.into)
@router.post('/aspect')
async def set_aspect(req: AspectReq):
    if not aria_nucleus: raise HTTPException(503,'nucleus_not_ready')
    return aria_nucleus.set_aspect(req.aspect)
@router.get('/aspects')
async def aspects():
    return {'ok':True,'aspects':[a.value for a in AriaAspect]}
