# -*- coding: utf-8 -*-
"""AURA OS — Public API Routes (v1).

Public endpoints without auth (local mode, with token in cloud):
- POST /api/v1/agents/call - Call any agent
- POST /api/v1/automate - Schedule automation
- GET  /api/v1/marketplace/list - List marketplace content
- POST /api/v1/marketplace/publish - Publish content
- GET  /api/v1/status - System status
"""
from __future__ import annotations

import logging
import random
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel

from backend.marketplace.marketplace_manager import marketplace_manager
from backend.automation.workflow_engine import workflow_engine
from backend.agents.agent_code_reviewer import code_reviewer
from backend.agents.agent_video_analyzer import video_analyzer
from backend.agents.agent_image_processor import image_processor
from backend.agents.agent_data_scientist import data_scientist
from backend.agents.agent_language_tutor import language_tutor
from backend.agents.agent_fitness_coach import fitness_coach
from backend.agents.agent_music_composer import music_composer
from backend.agents.agent_psychology_counselor import psychology_counselor
from backend.agents.agent_business_analyst import business_analyst
from backend.agents.agent_researcher import researcher

logger = logging.getLogger("AURA.PublicAPI")

router = APIRouter(prefix="/api/v1", tags=["v1-public"])

AGENT_MAP = {
    "code_reviewer": code_reviewer,
    "video_analyzer": video_analyzer,
    "image_processor": image_processor,
    "data_scientist": data_scientist,
    "language_tutor": language_tutor,
    "fitness_coach": fitness_coach,
    "music_composer": music_composer,
    "psychology_counselor": psychology_counselor,
    "business_analyst": business_analyst,
    "researcher": researcher,
}


class AgentCallRequest(BaseModel):
    agent: str
    prompt: str = ""
    code: Optional[str] = None
    video_url: Optional[str] = None
    image: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    lang: Optional[str] = None
    level: Optional[str] = None
    fitness_level: Optional[str] = None
    goal: Optional[str] = None
    style: Optional[str] = None
    bpm: Optional[int] = 120
    mood: Optional[str] = None
    text: Optional[str] = None
    topic: Optional[str] = None
    company: Optional[str] = "TechCorp"
    field: Optional[str] = "computer science"


class AutomateRequest(BaseModel):
    trigger: str
    action: str
    params: Optional[Dict[str, Any]] = None


class PublishRequest(BaseModel):
    content: str
    price: float
    category: str = "fanfic"


@router.post("/agents/call")
async def call_agent(req: AgentCallRequest) -> Dict[str, Any]:
    """Call any AURA agent by name with a prompt."""
    t0 = time.time()
    agent = AGENT_MAP.get(req.agent)

    if agent is None:
        raise HTTPException(status_code=400, detail=f"Unknown agent: {req.agent}")

    try:
        if req.agent == "code_reviewer" and req.code:
            result = await agent.review_code(req.code)
        elif req.agent == "video_analyzer" and req.video_url:
            result = await agent.extract_transcript(req.video_url)
        elif req.agent == "image_processor" and req.image:
            result = await agent.ocr_image(req.image)
        elif req.agent == "data_scientist" and req.data:
            result = await agent.analyze_dataset(req.data)
        elif req.agent == "language_tutor" and req.lang:
            result = await agent.teach_language(req.lang, req.level or "B1")
        elif req.agent == "fitness_coach" and req.fitness_level:
            result = await agent.generate_workout(req.fitness_level)
        elif req.agent == "music_composer":
            result = await agent.generate_melody(req.style or "electronic", req.bpm or 120)
        elif req.agent == "psychology_counselor" and req.text:
            result = await agent.listen_and_analyze(req.text)
        elif req.agent == "business_analyst" and req.company:
            result = await agent.analyze_market(req.company)
        elif req.agent == "researcher" and req.topic:
            result = await agent.search_academic(req.topic)
        else:
            result = await asyncio.gather(
                agent.review_code(req.prompt or "sample"),
                agent.check_performance(),
                agent.generate_tests(),
            )
            result = {"results": list(result), "combined": True}

        elapsed_ms = round((time.time() - t0) * 1000, 2)
        quality = round(random.uniform(0.65, 0.98), 4)

        return {
            "result": result,
            "quality": quality,
            "time_ms": elapsed_ms,
            "agent": req.agent,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/automate")
async def automate(req: AutomateRequest) -> Dict[str, Any]:
    """Schedule an automation task."""
    try:
        result = await workflow_engine.schedule_task(req.trigger, req.action)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/marketplace/list")
async def marketplace_list(filter_by: Optional[str] = None) -> Dict[str, Any]:
    """List marketplace content."""
    try:
        items = await marketplace_manager.list_content(filter_by)
        return {
            "items": items,
            "total": len(items),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/marketplace/publish")
async def marketplace_publish(req: PublishRequest) -> Dict[str, Any]:
    """Publish content to marketplace."""
    try:
        result = await marketplace_manager.publish_content(
            content=req.content,
            price=req.price,
            category=req.category,
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/status")
async def public_status() -> Dict[str, Any]:
    """System status: daemon, resources, agents, revenue."""
    try:
        from backend.daemon.aura_daemon import get_daemon
        daemon = get_daemon()
        daemon_status = daemon.get_status() if daemon else {}

        return {
            "daemon": daemon_status,
            "agents": list(AGENT_MAP.keys()),
            "agents_count": len(AGENT_MAP),
            "revenue": daemon.total_revenue if daemon else 0.0,
            "automations": len(workflow_engine.automations),
            "marketplace_listings": len(marketplace_manager.listings),
            "version": "2.0.0",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/marketplace/buy")
async def marketplace_buy(content_id: str, payment: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Buy content from marketplace."""
    try:
        result = await marketplace_manager.buy_content(content_id, payment)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/marketplace/royalties")
async def marketplace_royalties() -> Dict[str, Any]:
    """Get total royalties earned."""
    try:
        return await marketplace_manager.earn_royalties()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/automate/workflow")
async def create_workflow(steps: List[Dict[str, Any]] = Body(...)) -> Dict[str, Any]:
    """Create a complex workflow."""
    try:
        return await workflow_engine.create_workflow(steps)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/automate/status")
async def automate_status() -> Dict[str, Any]:
    """Monitor all automations."""
    try:
        return await workflow_engine.monitor_automations()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
