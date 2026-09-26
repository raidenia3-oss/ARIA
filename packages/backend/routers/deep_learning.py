"""
AURA Deep Learning & Narrative Router
Endpoints para autoaprendizaje, investigación y generación de narrativas coherentes.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.aura_os.deep_learning import DeepLearningModule
from backend.aura_os.narrative_engine import NarrativeEngine

logger = logging.getLogger("AURA.DeepLearning")

deep_learning = DeepLearningModule()
narrative_engine = NarrativeEngine()

router = APIRouter()


class LearnRequest(BaseModel):
    topic: str
    depth: str = "standard"


class CharacterRequest(BaseModel):
    name: str
    personality: str
    background: str
    voice_pattern: str = ""


class PlotRequest(BaseModel):
    title: str
    genre: str
    main_conflict: str
    themes: List[str] = []


class ChapterRequest(BaseModel):
    plot_title: str
    chapter_title: str
    pov_character: str
    target_length: int = 1000


class FeedbackRequest(BaseModel):
    prompt: str
    response: str
    provider: str
    feedback: str


@router.post("/deep-learning/learn")
async def learn_topic(request: LearnRequest) -> Dict[str, Any]:
    topic = request.topic.strip()
    if not topic:
        raise HTTPException(status_code=422, detail="topic is required")
    result = deep_learning.learn_from_internet(topic)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to learn topic")
    return result


@router.get("/deep-learning/knowledge")
async def query_knowledge(q: str = "", limit: int = 5) -> Dict[str, Any]:
    if not q:
        raise HTTPException(status_code=422, detail="q is required")
    results = deep_learning.query_knowledge(q, max_results=limit)
    return {"query": q, "results": results}


@router.post("/deep-learning/feedback")
async def record_feedback(request: FeedbackRequest) -> Dict[str, Any]:
    deep_learning.learn_from_interaction(
        prompt=request.prompt,
        response=request.response,
        provider=request.provider,
        feedback=request.feedback,
    )
    return {"status": "ok"}


@router.get("/deep-learning/stats")
async def learning_stats() -> Dict[str, Any]:
    return deep_learning.get_stats()


@router.post("/narrative/character")
async def create_character(request: CharacterRequest) -> Dict[str, Any]:
    char = narrative_engine.create_character(
        name=request.name,
        personality=request.personality,
        background=request.background,
        voice_pattern=request.voice_pattern,
    )
    return {"status": "ok", "character": char.to_dict()}


@router.post("/narrative/plot")
async def create_plot(request: PlotRequest) -> Dict[str, Any]:
    plot = narrative_engine.create_plot(
        title=request.title,
        genre=request.genre,
        main_conflict=request.main_conflict,
        themes=request.themes,
    )
    return {"status": "ok", "plot": plot.to_dict()}


@router.post("/narrative/chapter")
async def generate_chapter(request: ChapterRequest) -> Dict[str, Any]:
    text = narrative_engine.generate_chapter(
        plot_title=request.plot_title,
        chapter_title=request.chapter_title,
        pov_character=request.pov_character,
        target_length=request.target_length,
    )
    if not text:
        raise HTTPException(status_code=500, detail="Failed to generate chapter")
    return {"status": "ok", "chapter": text}


@router.get("/narrative/stats")
async def narrative_stats() -> Dict[str, Any]:
    return narrative_engine.get_stats()
