"""ARIA OS - Research Agent for social media and video analysis."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from agents.base import Agent

logger = logging.getLogger("ARIA.Agents")


class ResearchAgent(Agent):
    """Agent specialized in social media research and video analysis.

    Uses the SocialCollector, WhisperTranscriber, VideoAnalyzer, and
    ContentClassifier pipeline from backend.social_research.
    """

    def __init__(self):
        super().__init__(
            name="ResearchAgent",
            role="Social Media & Video Research",
        )
        self._collector = None
        self._transcriber = None
        self._analyzer = None
        self._classifier = None
        self._memory = None
        self._initialized = False

    def _ensure_init(self):
        if self._initialized:
            return
        try:
            from backend.social_research.collector import SocialCollector
            from backend.social_research.transcriber import WhisperTranscriber
            from backend.social_research.analyzer import VideoAnalyzer
            from backend.social_research.classifier import ContentClassifier
            from backend.social_research.memory_bridge import MemoryBridge

            self._collector = SocialCollector()
            self._transcriber = WhisperTranscriber(model_size="base")
            self._analyzer = VideoAnalyzer()
            self._classifier = ContentClassifier()
            self._memory = MemoryBridge()
            self._initialized = True
        except Exception as e:
            logger.warning(f"ResearchAgent init failed: {e}")

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a research task.

        Supported task types:
        - url: analyze a specific video URL
        - topic: search web for topic
        - batch: analyze multiple URLs
        """
        self._ensure_init()
        if not self._initialized:
            return {"status": "error", "error": "Research pipeline not available"}

        url = task.get("url", "")
        topic = task.get("topic", "")
        batch_urls = task.get("batch", [])

        if batch_urls:
            return await self._analyze_batch(batch_urls)
        if url:
            return await self._analyze_url(url, task)
        if topic:
            return await self._search_topic(topic, task)

        return {"status": "error", "error": "No url, topic, or batch provided"}

    async def _analyze_url(self, url: str, task: Dict[str, Any]) -> Dict[str, Any]:
        try:
            meta = self._collector.collect(url)
            transcription = None
            if meta.audio_path:
                transcription = self._transcriber.transcribe(meta.audio_path)
            frames = []
            if meta.video_path:
                frames = self._collector.extract_frames(meta.video_path, fps=0.15, max_frames=10)
            frame_paths = [f["path"] for f in frames]
            visual = None
            if frame_paths:
                visual = self._analyzer.analyze_visual(frame_paths[0])
            analysis = self._analyzer.analyze_video(
                video_path=meta.video_path or "",
                transcription_text=transcription.full_text if transcription else "",
                visual_samples=frame_paths,
            )
            topics = [t.topic for t in analysis.topics]
            importance = self._classifier.classify_importance(
                transcription_text=transcription.full_text if transcription else "",
                visual_desc=visual.description if visual else "",
                topics=topics,
            )
            tags = self._classifier.tag_content(
                transcription.full_text if transcription else "", topics
            )
            saved = False
            if importance.score >= 0.4 and self._memory:
                self._memory.save(
                    url=url,
                    title=meta.title,
                    platform=meta.platform,
                    transcription=transcription.full_text if transcription else "",
                    summary=analysis.summary,
                    topics=topics,
                    importance=importance.score,
                    tags=tags,
                )
                saved = True

            return {
                "status": "ok",
                "url": url,
                "title": meta.title,
                "platform": meta.platform,
                "transcription": (transcription.full_text[:1000] if transcription else ""),
                "topics": topics,
                "summary": analysis.summary,
                "importance": {"score": importance.score, "level": importance.level},
                "tags": tags,
                "visual_description": visual.description if visual else "",
                "saved": saved,
            }
        except Exception as e:
            logger.error(f"ResearchAgent URL analysis failed: {e}")
            return {"status": "error", "error": str(e)}

    async def _analyze_batch(self, urls: List[str]) -> Dict[str, Any]:
        results = []
        for url in urls[:10]:  # cap at 10
            r = await self._analyze_url(url, {})
            results.append(r)
        success = len([r for r in results if r.get("status") == "ok"])
        return {
            "status": "ok" if success > 0 else "error",
            "results": results,
            "total": len(urls),
            "success": success,
        }

    async def _search_topic(self, topic: str, task: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from backend.skills.web.search import run as search_skill

            results = []
            for q in [topic, f"{topic} tutorial", f"{topic} guía"]:
                try:
                    r = search_skill({"query": q})
                    results.append(str(r)[:500])
                except Exception as e:
                    results.append(f"Error: {e}")
            return {
                "status": "ok",
                "topic": topic,
                "research_results": results,
                "mode": "web_search",
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base["pipeline_ready"] = self._initialized
        return base