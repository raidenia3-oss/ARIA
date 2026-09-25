from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.social_research.analyzer import ContentTopic, FullAnalysis, VideoAnalyzer
from backend.social_research.classifier import ContentClassifier, ContentProfile, ImportanceScore
from backend.social_research.collector import SocialCollector, VideoMetadata
from backend.social_research.memory_bridge import MemoryBridge, SavedContent
from backend.social_research.transcriber import TranscriptionResult, WhisperTranscriber

router = APIRouter(prefix="/api/social-research", tags=["social-research"])

collector: Optional[SocialCollector] = None
transcriber: Optional[WhisperTranscriber] = None
analyzer: Optional[VideoAnalyzer] = None
classifier: Optional[ContentClassifier] = None
memory_bridge: Optional[MemoryBridge] = None


def _init_modules():
    global collector, transcriber, analyzer, classifier, memory_bridge
    if collector is None:
        collector = SocialCollector()
    if transcriber is None:
        transcriber = WhisperTranscriber(model_size="base")
    if analyzer is None:
        analyzer = VideoAnalyzer()
    if classifier is None:
        classifier = ContentClassifier()
    if memory_bridge is None:
        memory_bridge = MemoryBridge()


class CollectRequest(BaseModel):
    url: str


class CollectBatchRequest(BaseModel):
    urls: List[str]


class AnalyzeRequest(BaseModel):
    video_path: str
    transcription_text: str = ""
    openai_api_key: Optional[str] = None


class ResearchRequest(BaseModel):
    topic: str
    max_results: int = 10
    platforms: List[str] = ["youtube", "instagram", "tiktok"]
    focus_keywords: List[str] = []


class SaveContentRequest(BaseModel):
    profile: Dict[str, Any]
    transcription_text: str = ""
    visual_desc: str = ""


@router.get("/status")
def social_status():
    _init_modules()
    return {
        "collector": {"available": collector.available, "platforms": collector.SUPPORTED_PLATFORMS},
        "transcriber": {"model": transcriber.model_size, "loaded": transcriber._model_loaded},
        "analyzer": {
            "vision_model": analyzer._vision_model,
            "has_client": analyzer._openai_client is not None,
        },
        "classifier": {"ready": True},
        "memory": {"saved": len(memory_bridge.library)},
    }


@router.post("/collect")
def collect_video(req: CollectRequest):
    _init_modules()
    if not collector.is_supported(req.url):
        raise HTTPException(status_code=400, detail=f"URL no soportada: {req.url}")
    try:
        meta = collector.collect(req.url)
        return {
            "status": "ok",
            "metadata": {
                "url": meta.url,
                "platform": meta.platform,
                "title": meta.title,
                "author": meta.author,
                "duration_seconds": meta.duration_seconds,
                "view_count": meta.view_count,
                "like_count": meta.like_count,
                "thumbnail_path": meta.thumbnail_path,
                "video_path": meta.video_path,
                "audio_path": meta.audio_path,
                "resolution": meta.resolution,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/collect-batch")
def collect_batch(req: CollectBatchRequest):
    _init_modules()
    results = []
    for url in req.urls:
        try:
            meta = collector.collect(url)
            results.append({"url": url, "status": "ok", "title": meta.title})
        except Exception as e:
            results.append({"url": url, "status": "error", "error": str(e)})
    return {"results": results, "total": len(results)}


@router.post("/transcribe")
def transcribe_video(req: CollectRequest):
    _init_modules()
    try:
        meta = collector.collect(req.url)
        if not meta.audio_path:
            raise HTTPException(status_code=404, detail="No se pudo extraer audio")
        result = transcriber.transcribe(meta.audio_path)
        return {
            "status": "ok",
            "language": result.language,
            "language_probability": result.language_probability,
            "full_text": result.full_text,
            "duration_seconds": result.duration_seconds,
            "segments": [
                {"start": s.start, "end": s.end, "text": s.text, "confidence": s.confidence}
                for s in result.segments
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze")
def analyze_video(req: AnalyzeRequest):
    _init_modules()
    if req.openai_api_key:
        import openai

        analyzer.set_client(openai.OpenAI(api_key=req.openai_api_key))
    try:
        from backend.social_research.collector import SocialCollector

        col = SocialCollector()
        frames = col.extract_frames(req.video_path, fps=0.15, max_frames=10)
        frame_paths = [f["path"] for f in frames]
        transcription_text = req.transcription_text
        result = analyzer.analyze_video(
            video_path=req.video_path,
            transcription_text=transcription_text,
            visual_samples=frame_paths,
        )
        return {
            "status": "ok",
            "analysis": {
                "topics": [
                    {
                        "topic": t.topic,
                        "category": t.category,
                        "confidence": t.confidence,
                        "keywords": t.keywords,
                    }
                    for t in result.topics
                ],
                "summary": result.summary,
                "visual_description": (
                    result.visual_analysis.description if result.visual_analysis else ""
                ),
                "key_moments": result.key_moments,
                "is_educational": result.is_educational,
                "is_entertainment": result.is_entertainment,
                "educational_score": result.is_educational_score,
                "entertainment_score": result.is_entertainment_score,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/classify")
def classify_content(req: AnalyzeRequest):
    _init_modules()
    try:
        topics = [t.topic for t in analyzer._classify_topics(req.transcription_text)]
        visual_desc = ""
        from backend.social_research.collector import SocialCollector

        col = SocialCollector()
        frames = (
            col.extract_frames(req.video_path, fps=0.05, max_frames=3) if req.video_path else []
        )
        if frames:
            va = analyzer.analyze_visual(frames[0]["path"])
            visual_desc = va.description

        importance = classifier.classify_importance(
            transcription_text=req.transcription_text,
            visual_desc=visual_desc,
            topics=topics,
        )
        tags = classifier.tag_content(req.transcription_text, topics)

        profile = ContentProfile(
            url=req.video_path,
            platform="unknown",
            title=req.video_path,
            transcription_summary=req.transcription_text[:300],
            topics=topics,
            visual_description=visual_desc,
            importance=importance,
            tags=tags,
            analysis_timestamp=0,
        )

        save = classifier.auto_save_decision(profile)

        return {
            "status": "ok",
            "importance": {
                "score": importance.score,
                "level": importance.level,
                "reasons": importance.reasons,
            },
            "topics": topics,
            "tags": tags,
            "auto_save": save,
            "visual_description": visual_desc,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/research")
def research_topic(req: ResearchRequest):
    _init_modules()
    results = []
    search_queries = [
        f"{req.topic}",
        f"{req.topic} tutorial",
        f"{req.topic} guía",
        f"{req.topic} 2026",
    ]
    for query in search_queries[:3]:
        try:
            from backend.skills.web.search import run as search_skill

            search_result = search_skill({"query": query})
            results.append({"query": query, "result": str(search_result)[:1000]})
        except Exception as e:
            results.append({"query": query, "error": str(e)})

    return {
        "status": "ok",
        "topic": req.topic,
        "queries_executed": len(results),
        "results": results,
        "note": "Investigación inicial ejecutada. Use /collect con URLs encontradas para análisis profundo.",
    }


@router.post("/save")
def save_content(req: SaveContentRequest):
    _init_modules()
    try:
        profile = ContentProfile(
            url=req.profile.get("url", ""),
            platform=req.profile.get("platform", ""),
            title=req.profile.get("title", ""),
            transcription_summary=req.profile.get("transcription_summary", ""),
            topics=req.profile.get("topics", []),
            visual_description=req.profile.get("visual_description", ""),
            importance=ImportanceScore(
                **req.profile.get("importance", {"score": 0.5, "level": "medium", "reasons": []})
            ),
            tags=req.profile.get("tags", []),
            analysis_timestamp=time.time(),
        )
        saved = memory_bridge.save_to_memory(
            profile=profile,
            transcription_text=req.transcription_text,
            visual_desc=req.visual_desc,
        )
        return {
            "status": "saved",
            "content_id": saved.content_id,
            "importance": saved.importance_score,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/library")
def list_library(limit: int = 50, min_importance: Optional[float] = None):
    _init_modules()
    items = memory_bridge.list_all(limit=limit, min_importance=min_importance)
    return {
        "total": len(items),
        "items": [
            {
                "content_id": i.content_id,
                "title": i.title,
                "url": i.url,
                "platform": i.platform,
                "importance_score": i.importance_score,
                "topics": i.topics,
                "tags": i.tags,
                "summary": i.summary,
                "saved_at": i.saved_at,
            }
            for i in items
        ],
    }


@router.get("/library/search")
def search_library(q: str, top_k: int = 10):
    _init_modules()
    results = memory_bridge.search_library(q, top_k=top_k)
    return {
        "query": q,
        "results": [
            {
                "content_id": r.content_id,
                "title": r.title,
                "importance_score": r.importance_score,
                "topics": r.topics,
                "summary": r.summary,
            }
            for r in results
        ],
    }


@router.get("/library/stats")
def library_stats():
    _init_modules()
    return memory_bridge.get_stats()


import time
