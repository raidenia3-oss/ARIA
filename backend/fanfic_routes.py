"""Fanfic routes for AURA browser extension."""

from __future__ import annotations

import time
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query

from backend.database import SessionLocal
from backend.models import FanficDraft, Story

router = APIRouter(prefix="/api/fanfic", tags=["fanfic"])


@router.post("/stories/{story_id}/save-draft")
async def save_draft(story_id: int) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        story = db.query(Story).filter(Story.id == story_id).first()
        if not story:
            raise HTTPException(status_code=404, detail="Story not found")

        draft = FanficDraft(
            story_id=story_id,
            title=story.title,
            platform="cloud",
            content="",
            created_at=time.time(),
            updated_at=time.time(),
        )
        db.add(draft)
        db.commit()
        db.refresh(draft)
        return {"status": "draft_saved", "draft_id": draft.id, "story_id": story_id}
    finally:
        db.close()


@router.get("/drafts")
async def get_drafts(limit: int = Query(10)) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        drafts = (
            db.query(FanficDraft)
            .order_by(FanficDraft.updated_at.desc())
            .limit(limit)
            .all()
        )
        return {
            "drafts": [
                {
                    "id": d.id,
                    "story_id": d.story_id,
                    "title": d.title,
                    "platform": d.platform,
                    "updated_at": d.updated_at,
                }
                for d in drafts
            ]
        }
    finally:
        db.close()


@router.post("/stories/{story_id}/publish/{platform}")
async def publish_story(story_id: int, platform: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        story = db.query(Story).filter(Story.id == story_id).first()
        if not story:
            raise HTTPException(status_code=404, detail="Story not found")
        return {
            "status": "publish_ready",
            "story_id": story_id,
            "platform": platform,
            "title": story.title,
            "message": "Content ready for extension to publish on site",
        }
    finally:
        db.close()


@router.post("/stories/{story_id}/narrate")
async def generate_narration(story_id: int) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        story = db.query(Story).filter(Story.id == story_id).first()
        if not story:
            raise HTTPException(status_code=404, detail="Story not found")
        return {
            "status": "narration_generated",
            "story_id": story_id,
            "audio_url": f"/api/fanfic/audio/{story_id}.mp3",
            "message": "Use browser TTS or backend audio endpoint",
        }
    finally:
        db.close()


@router.get("/sync")
async def sync_extension() -> Dict[str, Any]:
    db = SessionLocal()
    try:
        drafts = db.query(FanficDraft).order_by(FanficDraft.updated_at.desc()).all()
        return {
            "drafts": [
                {
                    "id": d.id,
                    "story_id": d.story_id,
                    "title": d.title,
                    "platform": d.platform,
                    "updated_at": d.updated_at,
                }
                for d in drafts
            ],
            "published": [],
            "settings": {},
        }
    finally:
        db.close()
