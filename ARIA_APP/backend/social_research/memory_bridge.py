import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.social_research.classifier import ContentProfile, ImportanceScore


@dataclass
class SavedContent:
    content_id: str = ""
    url: str = ""
    platform: str = ""
    title: str = ""
    summary: str = ""
    importance_score: float = 0.0
    topics: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    transcription_snippet: str = ""
    visual_description: str = ""
    saved_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class MemoryBridge:

    def __init__(self, storage_dir: Optional[str] = None) -> None:
        self.storage_dir = (
            Path(storage_dir) if storage_dir else Path.home() / ".aura" / "social_research"
        )
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.library_file = self.storage_dir / "library.json"
        self.library: List[SavedContent] = []
        self._load_library()

    def _load_library(self) -> None:
        if self.library_file.exists():
            try:
                with open(self.library_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.library = [SavedContent(**item) for item in data]
            except Exception:
                self.library = []

    def _save_library(self) -> None:
        try:
            with open(self.library_file, "w", encoding="utf-8") as f:
                json.dump([item.__dict__ for item in self.library], f, ensure_ascii=False, indent=2)
        except Exception as e:
            pass

    def save_to_memory(
        self,
        profile: ContentProfile,
        transcription_text: str = "",
        visual_desc: str = "",
        ai_memory=None,
    ) -> SavedContent:
        content_id = f"content_{int(time.time() * 1000)}"
        saved = SavedContent(
            content_id=content_id,
            url=profile.url,
            platform=profile.platform,
            title=profile.title,
            summary=profile.transcription_summary
            or profile.visual_description
            or "Sin descripción",
            importance_score=profile.importance.score,
            topics=profile.topics,
            tags=profile.tags,
            transcription_snippet=transcription_text[:500] if transcription_text else "",
            visual_description=visual_desc,
            metadata={
                "importance_reasons": profile.importance.reasons,
                "auto_saved": profile.importance.score >= 0.4,
                "timestamp": time.time(),
            },
        )
        self.library.append(saved)
        self._save_library()

        if ai_memory:
            try:
                memory_text = (
                    f"[Contenido Social - {profile.platform}] {profile.title}\n"
                    f"Importancia: {profile.importance.score:.2f} ({profile.importance.level})\n"
                    f"Temas: {', '.join(profile.topics)}\n"
                    f"Resumen: {profile.transcription_summary[:300]}"
                )
                ai_memory.save_interaction(
                    f"Guardar contenido: {profile.title}",
                    memory_text,
                    meta={"type": "social_content", "content_id": content_id, "url": profile.url},
                )
            except Exception:
                pass

        return saved

    def search_library(self, query: str, top_k: int = 10) -> List[SavedContent]:
        query_lower = query.lower()
        scored: List[tuple[float, SavedContent]] = []
        for item in self.library:
            score = 0.0
            if query_lower in item.title.lower():
                score += 2.0
            if query_lower in item.summary.lower():
                score += 1.5
            for topic in item.topics:
                if query_lower in topic.lower():
                    score += 1.0
            for tag in item.tags:
                if query_lower in tag.lower():
                    score += 0.5
            for reason in item.importance_reasons if hasattr(item.importance, "reasons") else []:
                if query_lower in reason.lower():
                    score += 0.5
            if score > 0:
                scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:top_k]]

    def list_all(
        self, limit: int = 50, min_importance: Optional[float] = None
    ) -> List[SavedContent]:
        items = list(self.library)
        if min_importance is not None:
            items = [i for i in items if i.importance_score >= min_importance]
        items.sort(key=lambda x: x.saved_at, reverse=True)
        return items[:limit]

    def get_content(self, content_id: str) -> Optional[SavedContent]:
        for item in self.library:
            if item.content_id == content_id:
                return item
        return None

    def delete_content(self, content_id: str) -> bool:
        for i, item in enumerate(self.library):
            if item.content_id == content_id:
                self.library.pop(i)
                self._save_library()
                return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        if not self.library:
            return {"total": 0}
        scores = [i.importance_score for i in self.library]
        return {
            "total": len(self.library),
            "avg_importance": round(sum(scores) / len(scores), 3),
            "high_importance": sum(1 for s in scores if s >= 0.6),
            "medium_importance": sum(1 for s in scores if 0.3 <= s < 0.6),
            "low_importance": sum(1 for s in scores if s < 0.3),
            "platforms": list(set(i.platform for i in self.library)),
            "topics": list(set(t for i in self.library for t in i.topics)),
        }
