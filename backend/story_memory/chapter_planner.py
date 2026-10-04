"""Chapter Planner — planificación de capítulos y escenas.

Permite estructurar la narrativa con beats, estado de progreso y referencias a canon.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURA.StoryMemory.ChapterPlanner")


class ChapterPlanner:
    """Gestión de planificación de capítulos y escenas."""

    def __init__(self) -> None:
        from backend.story_memory.story_storage import StoryStorage

        self.storage = StoryStorage()

    def create_chapter(
        self,
        work_id: str,
        title: str,
        order: int = 0,
        beat_summary: str = "",
        scenes: Optional[List[Dict[str, Any]]] = None,
        related_canon: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        chapter = {
            "title": title,
            "order": order,
            "beat_summary": beat_summary,
            "scenes": scenes or [],
            "related_canon": related_canon or [],
            "status": "planned",
            "created_at": time.time(),
        }
        result = self.storage.save_chapter(work_id, chapter)
        logger.info("Chapter created: work=%s title=%s order=%d", work_id, title, order)
        return {**result, "chapter": chapter}

    def update_chapter_status(self, work_id: str, chapter_id: str, status: str) -> Dict[str, Any]:
        chapter = self.storage.get_chapter(work_id, chapter_id)
        if not chapter:
            return {"status": "error", "error": "chapter_not_found"}
        valid_statuses = {"planned", "in_progress", "drafted", "revised", "completed"}
        if status not in valid_statuses:
            return {"status": "error", "error": "invalid_status"}
        chapter["status"] = status
        chapter["updated_at"] = time.time()
        result = self.storage.save_chapter(work_id, chapter)
        result["status"] = "saved"
        result["chapter_status"] = status
        return result

    def add_scene(
        self,
        work_id: str,
        chapter_id: str,
        scene: Dict[str, Any],
    ) -> Dict[str, Any]:
        chapter = self.storage.get_chapter(work_id, chapter_id)
        if not chapter:
            return {"status": "error", "error": "chapter_not_found"}
        scene["scene_id"] = scene.get("scene_id") or f"sc_{int(time.time() * 1000)}"
        scene.setdefault("created_at", time.time())
        chapter["scenes"].append(scene)
        chapter["updated_at"] = time.time()
        result = self.storage.save_chapter(work_id, chapter)
        return {**result, "scene_id": scene["scene_id"]}

    def list_chapters(self, work_id: str) -> List[Dict[str, Any]]:
        return self.storage.list_chapters(work_id)

    def get_chapter(self, work_id: str, chapter_id: str) -> Optional[Dict[str, Any]]:
        return self.storage.get_chapter(work_id, chapter_id)

    def get_progress(self, work_id: str) -> Dict[str, Any]:
        chapters = self.list_chapters(work_id)
        total = len(chapters)
        completed = sum(1 for c in chapters if c.get("status") == "completed")
        in_progress = sum(1 for c in chapters if c.get("status") == "in_progress")
        return {
            "total_chapters": total,
            "completed": completed,
            "in_progress": in_progress,
            "planned": total - completed - in_progress,
            "progress_percent": round((completed / total * 100), 1) if total > 0 else 0,
            "chapters": chapters,
        }

    def build_chapter_context(self, work_id: str, max_chapters: int = 5) -> str:
        chapters = self.list_chapters(work_id)[:max_chapters]
        if not chapters:
            return ""
        lines = ["[PLAN DE CAPITULOS]"]
        for ch in chapters:
            status_icon = {
                "planned": "[ ]",
                "in_progress": "[~]",
                "drafted": "[draft]",
                "revised": "[rev]",
                "completed": "[x]",
            }.get(ch.get("status", "planned"), "[?]")
            lines.append(f"  {status_icon} Cap. {ch.get('order', '?')}: {ch.get('title', '')}")
        return "\n".join(lines)
