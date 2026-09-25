import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.social_research.analyzer import FullAnalysis, VideoAnalyzer
from backend.social_research.classifier import ContentClassifier, ImportanceScore
from backend.social_research.collector import SocialCollector, VideoMetadata
from backend.social_research.memory_bridge import MemoryBridge
from backend.social_research.transcriber import TranscriptionResult, WhisperTranscriber


@dataclass
class ResearchQuery:
    topic: str
    sub_queries: List[str] = field(default_factory=list)
    sources_checked: List[str] = field(default_factory=list)
    findings: List[str] = field(default_factory=list)
    importance_score: float = 0.0
    sources: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "pending"
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None


class VideoAnalysisPipeline:

    def __init__(self, openai_api_key: Optional[str] = None) -> None:
        self.collector = SocialCollector()
        self.transcriber = WhisperTranscriber(model_size="base")
        self.analyzer = VideoAnalyzer()
        self.classifier = ContentClassifier()
        self.memory = MemoryBridge()
        if openai_api_key:
            import openai

            self.analyzer.set_client(openai.OpenAI(api_key=openai_api_key))
        self._last_result: Optional[Any] = None

    def process_url(
        self,
        url: str,
        save_if_important: bool = True,
        ai_memory=None,
        openai_api_key: Optional[str] = None,
    ) -> Any:
        start = time.time()
        if openai_api_key:
            import openai

            self.analyzer.set_client(openai.OpenAI(api_key=openai_api_key))

        platform = self.collector.detect_platform(url)
        if not self.collector.is_supported(url):
            raise ValueError(f"Plataforma no soportada: {platform}")

        meta = self.collector.collect(url)
        transcription = self.transcriber.transcribe(meta.audio_path)

        frames = self.collector.extract_frames(meta.video_path, fps=0.15, max_frames=10)
        frame_paths = [f["path"] for f in frames]

        visual = self.analyzer.analyze_visual(frame_paths[0]) if frame_paths else None
        analysis = self.analyzer.analyze_video(
            video_path=meta.video_path,
            transcription_text=transcription.full_text,
            visual_samples=frame_paths,
        )

        topics = [t.topic for t in analysis.topics]
        visual_desc = visual.description if visual else ""
        importance = self.classifier.classify_importance(
            transcription_text=transcription.full_text,
            visual_desc=visual_desc,
            topics=topics,
        )
        tags = self.classifier.tag_content(transcription.full_text, topics)

        saved = False
        content_id = ""
        if save_if_important and importance.score >= 0.4:
            profile = type(
                "Profile",
                (),
                {
                    "url": url,
                    "platform": platform,
                    "title": meta.title,
                    "transcription_summary": transcription.full_text[:300],
                    "topics": topics,
                    "visual_description": visual_desc,
                    "importance": importance,
                    "tags": tags,
                    "analysis_timestamp": time.time(),
                },
            )()
            saved_content = self.memory.save_to_memory(
                profile=profile,
                transcription_text=transcription.full_text,
                visual_desc=visual_desc,
                ai_memory=ai_memory,
            )
            saved = True
            content_id = saved_content.content_id

        result = type(
            "VideoAnalysisResult",
            (),
            {
                "video_path": meta.video_path,
                "url": url,
                "platform": platform,
                "title": meta.title,
                "duration_seconds": meta.duration_seconds,
                "transcription": {
                    "language": transcription.language,
                    "full_text": transcription.full_text,
                    "segment_count": len(transcription.segments),
                    "duration_seconds": transcription.duration_seconds,
                },
                "visual_analysis": {
                    "description": visual.description if visual else "",
                    "tags": visual.tags if visual else [],
                    "scene_type": visual.scene_type if visual else "",
                    "mood": visual.mood if visual else "",
                    "objects_detected": visual.objects_detected if visual else [],
                    "confidence": visual.confidence if visual else 0.0,
                },
                "topics": [
                    {
                        "topic": t.topic,
                        "category": t.category,
                        "confidence": t.confidence,
                        "keywords": t.keywords,
                    }
                    for t in analysis.topics
                ],
                "summary": analysis.summary,
                "importance": {
                    "score": importance.score,
                    "level": importance.level,
                    "reasons": importance.reasons,
                },
                "tags": tags,
                "key_moments": analysis.key_moments,
                "saved": saved,
                "content_id": content_id,
                "processing_time": round(time.time() - start, 2),
            },
        )()
        self._last_result = result
        return result

    def process_batch(
        self,
        urls: List[str],
        max_concurrent: int = 3,
    ) -> List[Any]:
        results = []
        for i in range(0, len(urls), max_concurrent):
            batch = urls[i : i + max_concurrent]
            batch_results = []
            for url in batch:
                try:
                    r = self.process_url(url)
                    batch_results.append(r)
                except Exception as e:
                    batch_results.append(
                        type(
                            "VideoAnalysisResult",
                            (),
                            {"url": url, "processing_time": 0, "summary": f"Error: {e}"},
                        )()
                    )
            results.extend(batch_results)
        return results

    def get_last_result(self) -> Optional[Any]:
        return self._last_result
