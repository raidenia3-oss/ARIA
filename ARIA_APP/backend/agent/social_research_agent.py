"""ARIA OS — Social Research & Video Analysis Agent.

Multi-agent system for deep research across social media platforms,
short-form video analysis, and content intelligence.
"""

import time
from typing import Any, Dict, List, Optional

from backend.social_research.analyzer import VideoAnalyzer
from backend.social_research.classifier import ContentClassifier
from backend.social_research.collector import SocialCollector
from backend.social_research.memory_bridge import MemoryBridge
from backend.social_research.transcriber import WhisperTranscriber
from backend.video_analyzer import VideoAnalysisResult
from backend.video_analyzer.pipeline import VideoAnalysisPipeline


class SocialResearchAgent:
    """Agent specialized in deep research across social media."""

    def __init__(self, openai_client: Optional[Any] = None) -> None:
        self.collector = SocialCollector()
        self.transcriber = WhisperTranscriber()
        self.analyzer = VideoAnalyzer()
        self.classifier = ContentClassifier()
        self.memory = MemoryBridge()
        self._openai_client = openai_client
        self._pipeline: Optional[VideoAnalysisPipeline] = None
        self._research_log: List[Dict[str, Any]] = []

    def set_openai_client(self, client: Any) -> None:
        self._openai_client = client
        self.analyzer.set_client(client)
        self._pipeline = VideoAnalysisPipeline(
            openai_api_key=client.api_key if hasattr(client, "api_key") else None
        )

    def deep_research(
        self,
        topic: str,
        max_sources: int = 10,
        platforms: List[str] = None,
        focus_keywords: List[str] = None,
    ) -> Dict[str, Any]:
        start = time.time()
        platforms = platforms or ["youtube", "instagram", "tiktok"]
        sub_queries = [
            f"{topic}",
            f"{topic} tutorial guía",
            f"{topic} 2026",
        ]

        all_urls: List[str] = []
        for sq in sub_queries:
            try:
                from backend.skills.web.search import run as search_skill

                result = search_skill({"query": f"{sq} shorts reel video"})
                text = str(result)
                import re

                found = re.findall(
                    r"https?://(?:www\.)?(?:youtube\.com/(?:shorts/|watch\?\S*v=)|tiktok\.com/@\S+/video/\d+|instagram\.com/reel/\S+)",
                    text,
                )
                all_urls.extend(found[:max_sources])
            except Exception:
                pass
        all_urls = list(dict.fromkeys(all_urls))[:max_sources]

        video_results: List[Dict[str, Any]] = []
        for url in all_urls:
            try:
                if self.collector.is_supported(url):
                    meta = self.collector.collect(url)
                    transcription = self.transcriber.transcribe(meta.audio_path)
                    result = {
                        "url": url,
                        "platform": meta.platform,
                        "title": meta.title,
                        "duration": meta.duration_seconds,
                        "transcription_snippet": transcription.full_text[:300],
                        "transcription_full": transcription.full_text,
                        "importance": None,
                        "topics": [],
                        "summary": "",
                    }
                    topics = self.analyzer._classify_topics(transcription.full_text, meta.title)
                    result["topics"] = [t.topic for t in topics]
                    importance = self.classifier.classify_importance(
                        transcription_text=transcription.full_text,
                        visual_desc=meta.title,
                        topics=result["topics"],
                        custom_criteria={
                            "focus_keywords": focus_keywords or [],
                        },
                    )
                    result["importance"] = {
                        "score": importance.score,
                        "level": importance.level,
                        "reasons": importance.reasons,
                    }
                    result["summary"] = self.analyzer._generate_summary(
                        transcription.full_text, [], topics
                    )
                    video_results.append(result)
            except Exception:
                continue

        video_results.sort(
            key=lambda x: x["importance"]["score"] if x["importance"] else 0, reverse=True
        )

        important = [
            v for v in video_results if v["importance"] and v["importance"]["score"] >= 0.4
        ]

        synthesis = self._synthesize_research(topic, video_results)

        for v in important:
            try:
                profile = type(
                    "Profile",
                    (),
                    {
                        "url": v["url"],
                        "platform": v["platform"],
                        "title": v["title"],
                        "transcription_summary": v["transcription_snippet"],
                        "topics": v["topics"],
                        "visual_description": v["title"],
                        "importance": v["importance"],
                        "tags": [],
                        "analysis_timestamp": time.time(),
                    },
                )()
                self.memory.save_to_memory(
                    profile=profile, transcription_text=v.get("transcription_full", "")
                )
            except Exception:
                pass

        elapsed = round(time.time() - start, 2)
        log_entry = {
            "topic": topic,
            "timestamp": time.time(),
            "duration_seconds": elapsed,
            "urls_found": len(all_urls),
            "videos_analyzed": len(video_results),
            "important_count": len(important),
        }
        self._research_log.append(log_entry)

        return {
            "topic": topic,
            "status": "completed",
            "sub_queries": sub_queries,
            "sources_found": len(all_urls),
            "videos_analyzed": len(video_results),
            "important_videos": len(important),
            "duration_seconds": elapsed,
            "synthesis": synthesis,
            "videos": video_results,
            "important": important,
        }

    def analyze_single_video(self, url: str) -> Dict[str, Any]:
        if not self.collector.is_supported(url):
            return {"status": "error", "message": f"URL no soportada: {url}"}
        try:
            meta = self.collector.collect(url)
            transcription = self.transcriber.transcribe(meta.audio_path)
            analysis = self.analyzer.analyze_video(
                video_path=meta.video_path,
                transcription_text=transcription.full_text,
            )
            topics = [t.topic for t in analysis.topics]
            importance = self.classifier.classify_importance(
                transcription_text=transcription.full_text,
                visual_desc=(
                    analysis.visual_analysis.description if analysis.visual_analysis else ""
                ),
                topics=topics,
            )
            tags = self.classifier.tag_content(transcription.full_text, topics)
            return {
                "status": "ok",
                "url": url,
                "title": meta.title,
                "platform": meta.platform,
                "transcription": transcription.full_text[:1000],
                "transcription_language": transcription.language,
                "topics": topics,
                "summary": analysis.summary,
                "importance": {
                    "score": importance.score,
                    "level": importance.level,
                    "reasons": importance.reasons,
                },
                "tags": tags,
                "visual_description": (
                    analysis.visual_analysis.description if analysis.visual_analysis else ""
                ),
                "auto_save": importance.score >= 0.4,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_research_log(self) -> List[Dict[str, Any]]:
        return list(reversed(self._research_log))

    def _synthesize_research(self, topic: str, results: List[Dict[str, Any]]) -> str:
        if not results:
            return f"No se encontraron resultados para '{topic}'."
        important = [r for r in results if r.get("importance", {}).get("score", 0) >= 0.4]
        parts = [
            f"INVESTIGACIÓN: {topic}",
            f"Total de fuentes: {len(results)}, importantes: {len(important)}",
            "",
        ]
        for i, r in enumerate(results[:5], 1):
            level = r.get("importance", {}).get("level", "unknown")
            parts.append(f"{i}. [{level.upper()}] {r['title']}")
            if r.get("transcription_snippet"):
                parts.append(f"   Resumen: {r['transcription_snippet']}")
            parts.append(f"   Temas: {', '.join(r.get('topics', []))}")
            parts.append("")
        return "\n".join(parts)
