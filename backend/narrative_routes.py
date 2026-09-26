"""Narrative routes for AURA."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.database import SessionLocal
from backend.narrative_engine import NarrativeEngine, NarrativeMemory, StoryTone

router = APIRouter(prefix="/api/narrative", tags=["narrative"])

narrative_engine: Optional[NarrativeEngine] = None


class CreateStoryRequest(BaseModel):
    title: str
    premise: str
    characters: Any
    tone: str = "dramatic"


class ContinueStoryRequest(BaseModel):
    prompt: str


class RegenerateRequest(BaseModel):
    story_id: int
    section: str


class AddWorldRuleRequest(BaseModel):
    story_id: int
    rule: str


def init_narrative_engine(db_session_factory, llm_query, llm_stream) -> None:
    global narrative_engine
    narrative_engine = NarrativeEngine(db_session_factory, llm_query, llm_stream)


@router.post("/stories/create")
async def create_story(request: CreateStoryRequest) -> Dict[str, Any]:
    if narrative_engine is None:
        raise HTTPException(status_code=500, detail="Narrative engine not initialized")
    try:
        tone = StoryTone(request.tone.lower())
    except ValueError:
        tone = StoryTone.DRAMATIC
    story_id = await narrative_engine.start_story(
        title=request.title,
        premise=request.premise,
        characters=request.characters,
        tone=tone,
    )
    return {
        "story_id": story_id,
        "status": "created",
        "message": "Historia creada correctamente.",
    }


@router.post("/stories/{story_id}/continue")
async def continue_story(story_id: int, request: ContinueStoryRequest) -> Dict[str, Any]:
    if narrative_engine is None:
        raise HTTPException(status_code=500, detail="Narrative engine not initialized")
    chunks: List[str] = []
    async for chunk in narrative_engine.continue_story(story_id, request.prompt):
        chunks.append(chunk)
    text = "".join(chunks)
    return {"story_id": story_id, "text": text}


@router.post("/stories/{story_id}/regenerate")
async def regenerate_section(story_id: int, request: RegenerateRequest) -> Dict[str, Any]:
    if narrative_engine is None:
        raise HTTPException(status_code=500, detail="Narrative engine not initialized")
    result = await narrative_engine.regenerate_section(story_id, request.section)
    return {"story_id": story_id, "regenerated": result}


@router.get("/stories/{story_id}/stats")
async def story_stats(story_id: int) -> Dict[str, Any]:
    if narrative_engine is None:
        raise HTTPException(status_code=500, detail="Narrative engine not initialized")
    stats = narrative_engine.get_story_stats(story_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Story not found")
    return stats


@router.get("/stories/{story_id}/memory")
async def story_memory(story_id: int) -> Dict[str, Any]:
    if narrative_engine is None:
        raise HTTPException(status_code=500, detail="Narrative engine not initialized")
    memory = NarrativeMemory(SessionLocal).load_story(story_id)
    if not memory.previous_scenes:
        return {"message": "No memory loaded for this story"}
    return {
        "characters": memory.characters,
        "plot_points": memory.plot_points,
        "tone": memory.tone.value if memory.tone else None,
        "scenes_count": len(memory.previous_scenes),
        "setting": memory.setting,
        "world_rules": memory.world_rules,
    }


@router.post("/stories/{story_id}/world-rule")
async def add_world_rule(request: AddWorldRuleRequest) -> Dict[str, Any]:
    if narrative_engine is None:
        raise HTTPException(status_code=500, detail="Narrative engine not initialized")
    memory = narrative_engine.memory
    if not memory or memory.story_id != request.story_id:
        memory = narrative_engine.memory = narrative_engine.__class__.__new__(narrative_engine.__class__)
        memory.load_story(request.story_id)
    memory.world_rules.append(request.rule)
    db = memory.db_session_factory()
    try:
        from backend.models import Story
        story = db.query(Story).filter_by(id=request.story_id).first()
        if story:
            story.world_rules = json.dumps(memory.world_rules, ensure_ascii=False)
            db.commit()
    finally:
        db.close()
    return {"world_rules": memory.world_rules}
