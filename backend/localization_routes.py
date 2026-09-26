"""Localization routes for AURA."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query, Header

from backend.localization_manager import LocalizationManager, SupportedLanguage

router = APIRouter(prefix="/api/localization", tags=["localization"])

localization: LocalizationManager | None = None


def init_localization(db_session_factory) -> None:
    global localization
    db = db_session_factory() if db_session_factory else None
    localization = LocalizationManager(db)


@router.get("/languages")
async def get_supported_languages() -> Dict[str, Any]:
    if localization is None:
        raise HTTPException(status_code=500, detail="Localization not initialized")
    return {"languages": localization.get_supported_languages(), "count": len(localization.supported_langs)}


@router.post("/detect")
async def detect_language(text: str = Query(...)) -> Dict[str, Any]:
    if localization is None:
        raise HTTPException(status_code=500, detail="Localization not initialized")
    detected = await localization.detect_language(text)
    return {
        "detected_language": detected,
        "language_name": localization._get_language_name(SupportedLanguage(detected)),
        "confidence": 0.95,
    }


@router.get("/metrics")
async def get_language_metrics() -> Dict[str, Any]:
    if localization is None:
        raise HTTPException(status_code=500, detail="Localization not initialized")
    metrics = localization.get_language_metrics()
    return {
        "languages": [
            {
                "language": m.language,
                "stories_generated": m.stories_generated,
                "stories_published": m.stories_published,
                "quality_score": m.avg_quality_score,
                "engagement_rate": m.engagement_rate,
                "monthly_earnings": m.monthly_earnings,
            }
            for m in metrics
        ]
    }


@router.get("/trending")
async def get_trending_languages(limit: int = Query(5)) -> Dict[str, Any]:
    if localization is None:
        raise HTTPException(status_code=500, detail="Localization not initialized")
    trending = localization.get_trending_languages(limit)
    return {"trending_languages": trending, "count": len(trending)}


@router.post("/optimize")
async def optimize_by_demand() -> Dict[str, Any]:
    if localization is None:
        raise HTTPException(status_code=500, detail="Localization not initialized")
    result = await localization.optimize_by_language_demand()
    return result


@router.post("/story/multilang")
async def generate_story_multilang(story_data: Dict[str, Any], language: str = Header("en")) -> Dict[str, Any]:
    if localization is None:
        raise HTTPException(status_code=500, detail="Localization not initialized")
    if language not in localization.supported_langs:
        language = SupportedLanguage.ENGLISH.value
    prompt = localization.build_localized_prompt(story_data, language)
    return {"prompt": prompt, "language": language, "language_name": localization._get_language_name(SupportedLanguage(language))}


@router.get("/analytics/by-language")
async def get_analytics_by_language() -> Dict[str, Any]:
    if localization is None:
        raise HTTPException(status_code=500, detail="Localization not initialized")
    metrics = localization.get_language_metrics()
    return {
        "by_language": {
            m.language: {
                "generated": m.stories_generated,
                "published": m.stories_published,
                "quality": m.avg_quality_score,
                "engagement": m.engagement_rate,
                "earnings": m.monthly_earnings,
            }
            for m in metrics
        }
    }
