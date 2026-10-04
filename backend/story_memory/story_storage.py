"""Story storage layer — persistencia por obra, universo y personaje.

Separa datos literarios de la memoria vectorial (MemoryEngine/ChromaDB).
Usa JSON simple en disco dentro de AURA_STORY_DIR (default: ./story_memory).

Estructura en disco:
    <store_dir>/
      work_<work_id>/
        metadata.json        # título, universo, descripción, creado, actualizado
        characters/
          <char_id>.json     # CharacterBible entry
        canon/
          <event_id>.json    # canon evento
        continuity/
          <event_id>.json    # continuity evento
        chapters/
          <chapter_id>.json  # capítulo planificado con scenes
        consistency_checks/
          <check_id>.json     # registro de checks de coherencia
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class StoryStorage:
    """Gestor de almacenamiento JSON para la base literaria de AURA/AME."""

    def __init__(self, store_dir: Optional[str] = None) -> None:
        self.store_dir = Path(
            store_dir or os.getenv("AURA_STORY_DIR", os.path.join(os.getcwd(), "story_memory"))
        )
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _work_dir(self, work_id: str) -> Path:
        return self.store_dir / f"work_{work_id}"

    def _ensure_work(self, work_id: str) -> Path:
        d = self._work_dir(work_id)
        d.mkdir(parents=True, exist_ok=True)
        for sub in ("characters", "canon", "continuity", "chapters", "consistency_checks"):
            (d / sub).mkdir(exist_ok=True)
        return d

    def _meta_path(self, work_id: str) -> Path:
        return self._work_dir(work_id) / "metadata.json"

    def _char_path(self, work_id: str, char_id: str) -> Path:
        return self._work_dir(work_id) / "characters" / f"{char_id}.json"

    def _canon_path(self, work_id: str, event_id: str) -> Path:
        return self._work_dir(work_id) / "canon" / f"{event_id}.json"

    def _continuity_path(self, work_id: str, event_id: str) -> Path:
        return self._work_dir(work_id) / "continuity" / f"{event_id}.json"

    def _chapter_path(self, work_id: str, chapter_id: str) -> Path:
        return self._work_dir(work_id) / "chapters" / f"{chapter_id}.json"

    def _check_path(self, work_id: str, check_id: str) -> Path:
        return self._work_dir(work_id) / "consistency_checks" / f"{check_id}.json"

    @staticmethod
    def _load_json(path: Path) -> Optional[Dict[str, Any]]:
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else None

    @staticmethod
    def _save_json(path: Path, data: Dict[str, Any]) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        path.unlink(missing_ok=True)
        tmp.rename(path)

    def work_exists(self, work_id: str) -> bool:
        return self._meta_path(work_id).exists()

    def create_work(
        self,
        work_id: str,
        title: str,
        universe: str = "",
        description: str = "",
        author: str = "",
    ) -> Dict[str, Any]:
        with self._lock:
            if self.work_exists(work_id):
                return {"status": "exists", "work_id": work_id}
            self._ensure_work(work_id)
            meta = {
                "work_id": work_id,
                "title": title,
                "universe": universe,
                "description": description,
                "author": author,
                "created_at": time.time(),
                "updated_at": time.time(),
            }
            self._save_json(self._meta_path(work_id), meta)
            return {"status": "created", "work_id": work_id, "title": title}

    def get_work(self, work_id: str) -> Optional[Dict[str, Any]]:
        return self._load_json(self._meta_path(work_id))

    def list_works(self) -> List[Dict[str, Any]]:
        results = []
        for d in self.store_dir.iterdir():
            if d.name.startswith("work_") and d.is_dir():
                meta = self._load_json(d / "metadata.json")
                if meta:
                    results.append(meta)
        return results

    def save_character(self, work_id: str, char_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            self._ensure_work(work_id)
            data["char_id"] = char_id
            data["updated_at"] = time.time()
            if "created_at" not in data:
                data["created_at"] = data["updated_at"]
            self._save_json(self._char_path(work_id, char_id), data)
            self._broadcast("character_update", {"work_id": work_id, "char_id": char_id, "character": data}, work_id)
            return {"status": "saved", "work_id": work_id, "char_id": char_id}

    def get_character(self, work_id: str, char_id: str) -> Optional[Dict[str, Any]]:
        return self._load_json(self._char_path(work_id, char_id))

    def list_characters(self, work_id: str) -> List[Dict[str, Any]]:
        if not self._work_dir(work_id).exists():
            return []
        chars_dir = self._work_dir(work_id) / "characters"
        results = []
        for p in chars_dir.glob("*.json"):
            data = self._load_json(p)
            if data:
                results.append(data)
        return results

    def delete_character(self, work_id: str, char_id: str) -> Dict[str, Any]:
        with self._lock:
            p = self._char_path(work_id, char_id)
            if p.exists():
                p.unlink()
                return {"status": "deleted", "char_id": char_id}
            return {"status": "not_found", "char_id": char_id}

    def add_canon_event(self, work_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            self._ensure_work(work_id)
            event_id = event.get("event_id") or f"canon_{int(time.time() * 1000)}"
            event["event_id"] = event_id
            event["type"] = "canon"
            event.setdefault("created_at", time.time())
            event.setdefault("updated_at", time.time())
            self._save_json(self._canon_path(work_id, event_id), event)
            self._broadcast("canon_event", {"work_id": work_id, "description": event.get("description", ""),
                                            "event_id": event_id, "source": event.get("source", "user")}, work_id)
            return {"status": "added", "event_id": event_id, "type": "canon"}

    def get_canon_events(self, work_id: str) -> List[Dict[str, Any]]:
        if not self._work_dir(work_id).exists():
            return []
        results = []
        for p in (self._work_dir(work_id) / "canon").glob("*.json"):
            data = self._load_json(p)
            if data:
                results.append(data)
        results.sort(key=lambda x: x.get("timestamp", 0))
        return results

    def add_continuity_event(self, work_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            self._ensure_work(work_id)
            event_id = event.get("event_id") or f"cont_{int(time.time() * 1000)}"
            event["event_id"] = event_id
            event["type"] = "continuity"
            event.setdefault("created_at", time.time())
            event.setdefault("updated_at", time.time())
            self._save_json(self._continuity_path(work_id, event_id), event)
            return {"status": "added", "event_id": event_id, "type": "continuity"}

    def get_continuity_events(self, work_id: str) -> List[Dict[str, Any]]:
        if not self._work_dir(work_id).exists():
            return []
        results = []
        for p in (self._work_dir(work_id) / "continuity").glob("*.json"):
            data = self._load_json(p)
            if data:
                results.append(data)
        results.sort(key=lambda x: x.get("timestamp", 0))
        return results

    def save_chapter(self, work_id: str, chapter: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            self._ensure_work(work_id)
            chapter_id = chapter.get("chapter_id") or f"ch_{int(time.time() * 1000)}"
            chapter["chapter_id"] = chapter_id
            chapter.setdefault("created_at", time.time())
            chapter["updated_at"] = time.time()
            self._save_json(self._chapter_path(work_id, chapter_id), chapter)
            return {"status": "saved", "chapter_id": chapter_id}

    def get_chapter(self, work_id: str, chapter_id: str) -> Optional[Dict[str, Any]]:
        return self._load_json(self._chapter_path(work_id, chapter_id))

    def list_chapters(self, work_id: str) -> List[Dict[str, Any]]:
        if not self._work_dir(work_id).exists():
            return []
        results = []
        for p in (self._work_dir(work_id) / "chapters").glob("*.json"):
            data = self._load_json(p)
            if data:
                results.append(data)
        results.sort(key=lambda x: x.get("order", 0))
        return results

    def save_consistency_check(self, work_id: str, check: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            self._ensure_work(work_id)
            check_id = check.get("check_id") or f"chk_{int(time.time() * 1000)}"
            check["check_id"] = check_id
            check.setdefault("created_at", time.time())
            self._save_json(self._check_path(work_id, check_id), check)
            return {"status": "saved", "check_id": check_id}

    def get_consistency_checks(self, work_id: str) -> List[Dict[str, Any]]:
        if not self._work_dir(work_id).exists():
            return []
        results = []
        for p in (self._work_dir(work_id) / "consistency_checks").glob("*.json"):
            data = self._load_json(p)
            if data:
                results.append(data)
        results.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        return results

    def clear_work(self, work_id: str) -> Dict[str, Any]:
        import shutil

        with self._lock:
            d = self._work_dir(work_id)
            if d.exists():
                shutil.rmtree(d)
                return {"status": "cleared", "work_id": work_id}
            return {"status": "not_found", "work_id": work_id}

    @staticmethod
    def _broadcast(event_type: str, payload: Dict[str, Any], work_id: Optional[str] = None) -> None:
        """Transmite eventos literarios a AME conectados vía WebSocket (no bloqueante)."""
        try:
            import asyncio
            asyncio.get_running_loop()
            asyncio.ensure_future(__import__("backend.websocket_manager", fromlist=["ws_gateway"]).ws_gateway.broadcast(
                event_type, payload, work_id=work_id))
        except Exception as exc:
            logger = __import__("logging").getLogger("AURA.StoryStorage")
            logger.debug("WS broadcast deferred for %s: %s", event_type, exc)
