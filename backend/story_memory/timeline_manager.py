"""Narrative Timeline & Chronology Mapper (BLOQUE 44).

Motor local de mapeo cronológico y líneas de tiempo narrativas.
Permite estructurar eventos históricos, subtramas paralelas, saltos temporales
(flashbacks/flashforwards) y la cronología general de la obra.
Integra con Jan para detectar incongruencias temporales en el canon.

Almacenamiento: JSON en disco bajo <store_dir>/timelines/work_<id>.timeline.json
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.story_memory.story_storage import StoryStorage
from backend.story_memory.canon_tracker import CanonTracker
from backend.story_memory.chapter_planner import ChapterPlanner


class TimelineEventType(Enum):
    """Tipos de eventos en la línea de tiempo."""
    CANON = "canon"
    CONTINUITY = "continuity"
    CHAPTER = "chapter"
    SCENE = "scene"
    FLASHBACK = "flashback"
    FLASHFORWARD = "flashforward"
    BACKSTORY = "backstory"
    PROLOGUE = "prologue"
    EPILOGUE = "epilogue"


class TemporalRelation(Enum):
    """Relaciones temporales entre eventos."""
    BEFORE = "before"
    AFTER = "after"
    SIMULTANEOUS = "simultaneous"
    DURING = "during"
    CAUSES = "causes"
    CAUSED_BY = "caused_by"
    PRECEDES = "precedes"
    FOLLOWS = "follows"


@dataclass
class TimelineEvent:
    """Evento individual en la línea de tiempo narrativa."""
    event_id: str
    work_id: str
    title: str
    description: str
    event_type: TimelineEventType
    timestamp: float = 0.0
    relative_order: int = 0
    duration: Optional[float] = None
    chapter_id: Optional[str] = None
    scene_id: Optional[str] = None
    scene_ref: Optional[str] = None
    characters: List[str] = field(default_factory=list)
    factions: List[str] = field(default_factory=list)
    location: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    certainty: str = "canon"
    source: str = "user"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "work_id": self.work_id,
            "title": self.title,
            "description": self.description,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "relative_order": self.relative_order,
            "duration": self.duration,
            "chapter_id": self.chapter_id,
            "scene_id": self.scene_id,
            "scene_ref": self.scene_ref,
            "characters": self.characters,
            "factions": self.factions,
            "location": self.location,
            "tags": self.tags,
            "certainty": self.certainty,
            "source": self.source,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimelineEvent":
        return cls(
            event_id=data["event_id"],
            work_id=data["work_id"],
            title=data["title"],
            description=data["description"],
            event_type=TimelineEventType(data["event_type"]),
            timestamp=data.get("timestamp", 0.0),
            relative_order=data.get("relative_order", 0),
            duration=data.get("duration"),
            chapter_id=data.get("chapter_id"),
            scene_id=data.get("scene_id"),
            scene_ref=data.get("scene_ref"),
            characters=data.get("characters", []),
            factions=data.get("factions", []),
            location=data.get("location"),
            tags=data.get("tags", []),
            certainty=data.get("certainty", "canon"),
            source=data.get("source", "user"),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TimelineLink:
    """Enlace de relación temporal entre dos eventos."""
    source_id: str
    target_id: str
    relation: TemporalRelation
    strength: float = 1.0
    evidence: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation.value,
            "strength": self.strength,
            "evidence": self.evidence,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimelineLink":
        return cls(
            source_id=data["source_id"],
            target_id=data["target_id"],
            relation=TemporalRelation(data["relation"]),
            strength=data.get("strength", 1.0),
            evidence=data.get("evidence", []),
            created_at=data.get("created_at", time.time()),
        )


@dataclass
class NarrativeThread:
    """Hilo narrativo / subtrama con su propia cronología."""
    thread_id: str
    work_id: str
    name: str
    description: str = ""
    color: str = "#888888"
    event_ids: List[str] = field(default_factory=list)
    character_ids: List[str] = field(default_factory=list)
    is_main: bool = False
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "thread_id": self.thread_id,
            "work_id": self.work_id,
            "name": self.name,
            "description": self.description,
            "color": self.color,
            "event_ids": self.event_ids,
            "character_ids": self.character_ids,
            "is_main": self.is_main,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NarrativeThread":
        return cls(
            thread_id=data["thread_id"],
            work_id=data["work_id"],
            name=data["name"],
            description=data.get("description", ""),
            color=data.get("color", "#888888"),
            event_ids=data.get("event_ids", []),
            character_ids=data.get("character_ids", []),
            is_main=data.get("is_main", False),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            metadata=data.get("metadata", {}),
        )


@dataclass
class NarrativeTimeline:
    """Línea de tiempo completa para una obra."""
    work_id: str
    events: Dict[str, TimelineEvent] = field(default_factory=dict)
    links: Dict[str, TimelineLink] = field(default_factory=dict)
    threads: Dict[str, NarrativeThread] = field(default_factory=dict)
    main_thread_id: Optional[str] = None
    updated_at: float = field(default_factory=time.time)

    def add_event(self, event: TimelineEvent) -> None:
        self.events[event.event_id] = event
        self.updated_at = time.time()

    def remove_event(self, event_id: str) -> bool:
        if event_id in self.events:
            del self.events[event_id]
            # Remove associated links
            to_remove = [k for k, v in self.links.items()
                        if v.source_id == event_id or v.target_id == event_id]
            for k in to_remove:
                del self.links[k]
            # Remove from threads
            for thread in self.threads.values():
                if event_id in thread.event_ids:
                    thread.event_ids.remove(event_id)
            self.updated_at = time.time()
            return True
        return False

    def add_link(self, link: TimelineLink) -> None:
        key = f"{link.source_id}:{link.target_id}:{link.relation.value}"
        self.links[key] = link
        self.updated_at = time.time()

    def remove_link(self, source_id: str, target_id: str, relation: TemporalRelation) -> bool:
        key = f"{source_id}:{target_id}:{relation.value}"
        if key in self.links:
            del self.links[key]
            self.updated_at = time.time()
            return True
        return False

    def get_events_sorted(self) -> List[TimelineEvent]:
        return sorted(self.events.values(), key=lambda e: (e.timestamp, e.relative_order))

    def get_events_by_type(self, event_type: TimelineEventType) -> List[TimelineEvent]:
        return [e for e in self.events.values() if e.event_type == event_type]

    def get_events_by_character(self, char_id: str) -> List[TimelineEvent]:
        return [e for e in self.events.values() if char_id in e.characters]

    def get_events_by_faction(self, faction_id: str) -> List[TimelineEvent]:
        return [e for e in self.events.values() if faction_id in e.factions]

    def get_events_in_range(self, start: float, end: float) -> List[TimelineEvent]:
        return [e for e in self.events.values() if start <= e.timestamp <= end]

    def add_thread(self, thread: NarrativeThread) -> None:
        self.threads[thread.thread_id] = thread
        if thread.is_main:
            self.main_thread_id = thread.thread_id
        self.updated_at = time.time()

    def remove_thread(self, thread_id: str) -> bool:
        if thread_id in self.threads:
            del self.threads[thread_id]
            if self.main_thread_id == thread_id:
                self.main_thread_id = None
            self.updated_at = time.time()
            return True
        return False

    def get_thread_events(self, thread_id: str) -> List[TimelineEvent]:
        thread = self.threads.get(thread_id)
        if not thread:
            return []
        events = [self.events[eid] for eid in thread.event_ids if eid in self.events]
        return sorted(events, key=lambda e: (e.timestamp, e.relative_order))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "work_id": self.work_id,
            "events": {k: v.to_dict() for k, v in self.events.items()},
            "links": {k: v.to_dict() for k, v in self.links.items()},
            "threads": {k: v.to_dict() for k, v in self.threads.items()},
            "main_thread_id": self.main_thread_id,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NarrativeTimeline":
        tl = cls(work_id=data["work_id"])
        tl.events = {k: TimelineEvent.from_dict(v) for k, v in data.get("events", {}).items()}
        tl.links = {k: TimelineLink.from_dict(v) for k, v in data.get("links", {}).items()}
        tl.threads = {k: NarrativeThread.from_dict(v) for k, v in data.get("threads", {}).items()}
        tl.main_thread_id = data.get("main_thread_id")
        tl.updated_at = data.get("updated_at", time.time())
        return tl


class TimelineManager:
    """Gestor de líneas de tiempo narrativas por obra."""

    def __init__(self, store_dir: Optional[str] = None) -> None:
        self.store_dir = Path(
            store_dir or os.getenv("AURA_STORY_DIR", os.path.join(os.getcwd(), "story_memory"))
        )
        self.timeline_dir = self.store_dir / "timelines"
        self.timeline_dir.mkdir(parents=True, exist_ok=True)
        self.storage = StoryStorage(store_dir=str(self.store_dir))
        self._timelines: Dict[str, NarrativeTimeline] = {}
        self._lock = threading.RLock()

    def _timeline_path(self, work_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in work_id)
        return self.timeline_dir / f"work_{safe}.timeline.json"

    def _load_timeline(self, work_id: str) -> NarrativeTimeline:
        with self._lock:
            if work_id in self._timelines:
                return self._timelines[work_id]

            path = self._timeline_path(work_id)
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    timeline = NarrativeTimeline.from_dict(data)
                except Exception:
                    timeline = NarrativeTimeline(work_id=work_id)
            else:
                timeline = NarrativeTimeline(work_id=work_id)

            self._timelines[work_id] = timeline
            return timeline

    def _save_timeline(self, work_id: str) -> None:
        with self._lock:
            timeline = self._timelines.get(work_id)
            if not timeline:
                return
            path = self._timeline_path(work_id)
            tmp = path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(timeline.to_dict(), f, ensure_ascii=False, indent=2)
            tmp.replace(path)

    def get_or_create_timeline(self, work_id: str) -> NarrativeTimeline:
        """Obtiene o crea la línea de tiempo, sincronizando con canon/chapters."""
        timeline = self._load_timeline(work_id)

        # Sync only if newly created (no existing file)
        path = self._timeline_path(work_id)
        if not path.exists() and self.storage.work_exists(work_id):
            self._sync_from_existing_data(work_id, timeline)

        return timeline

    def _sync_from_existing_data(self, work_id: str, timeline: NarrativeTimeline) -> None:
        """Sincroniza eventos desde canon, continuity y chapters existentes."""
        ct = CanonTracker()
        cp = ChapterPlanner()

        # Create main thread
        main_thread = NarrativeThread(
            thread_id="main",
            work_id=work_id,
            name="Trama Principal",
            description="Línea temporal principal de la obra",
            color="#FF6B6B",
            is_main=True,
        )
        timeline.add_thread(main_thread)

        # Sync canon events
        for event in ct.get_canon_events(work_id):
            tl_event = TimelineEvent(
                event_id=event.get("event_id", f"canon_{int(time.time()*1000)}"),
                work_id=work_id,
                title=event.get("description", "")[:50],
                description=event.get("description", ""),
                event_type=TimelineEventType.CANON,
                timestamp=event.get("timestamp", 0),
                scene_ref=event.get("scene_ref", ""),
                certainty=event.get("certainty", "canon"),
                source=event.get("source", "user"),
            )
            timeline.add_event(tl_event)
            main_thread.event_ids.append(tl_event.event_id)

        # Sync continuity events
        for event in ct.get_continuity_events(work_id):
            tl_event = TimelineEvent(
                event_id=event.get("event_id", f"cont_{int(time.time()*1000)}"),
                work_id=work_id,
                title=event.get("description", "")[:50],
                description=event.get("description", ""),
                event_type=TimelineEventType.CONTINUITY,
                timestamp=event.get("timestamp", 0),
                scene_ref=event.get("scene_ref", ""),
                certainty=event.get("certainty", "continuity"),
                source=event.get("source", "user"),
            )
            timeline.add_event(tl_event)
            main_thread.event_ids.append(tl_event.event_id)

        # Sync chapters
        for chapter in cp.list_chapters(work_id):
            tl_event = TimelineEvent(
                event_id=chapter.get("chapter_id", f"ch_{int(time.time()*1000)}"),
                work_id=work_id,
                title=chapter.get("title", ""),
                description=chapter.get("beat_summary", ""),
                event_type=TimelineEventType.CHAPTER,
                timestamp=chapter.get("created_at", time.time()),
                chapter_id=chapter.get("chapter_id"),
                relative_order=chapter.get("order", 0),
            )
            timeline.add_event(tl_event)
            main_thread.event_ids.append(tl_event.event_id)

        # Sort main thread events by timestamp
        main_thread.event_ids.sort(key=lambda eid: timeline.events[eid].timestamp)

    def save_timeline(self, work_id: str) -> Dict[str, Any]:
        timeline = self.get_or_create_timeline(work_id)
        self._save_timeline(work_id)
        return {"status": "saved", "work_id": work_id}

    # --- Event Operations ---

    def add_event(
        self,
        work_id: str,
        title: str,
        description: str,
        event_type: TimelineEventType,
        timestamp: float = 0.0,
        relative_order: int = 0,
        duration: Optional[float] = None,
        chapter_id: Optional[str] = None,
        scene_id: Optional[str] = None,
        characters: Optional[List[str]] = None,
        factions: Optional[List[str]] = None,
        location: Optional[str] = None,
        tags: Optional[List[str]] = None,
        certainty: str = "canon",
        source: str = "user",
        thread_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        timeline = self.get_or_create_timeline(work_id)

        event_id = f"evt_{int(time.time() * 1000)}"
        event = TimelineEvent(
            event_id=event_id,
            work_id=work_id,
            title=title,
            description=description,
            event_type=event_type,
            timestamp=timestamp,
            relative_order=relative_order,
            duration=duration,
            chapter_id=chapter_id,
            scene_id=scene_id,
            characters=characters or [],
            factions=factions or [],
            location=location,
            tags=tags or [],
            certainty=certainty,
            source=source,
        )

        timeline.add_event(event)

        # Add to thread if specified
        if thread_id and thread_id in timeline.threads:
            timeline.threads[thread_id].event_ids.append(event_id)
        elif timeline.main_thread_id:
            timeline.threads[timeline.main_thread_id].event_ids.append(event_id)

        self._save_timeline(work_id)
        return {"status": "created", "event": event.to_dict()}

    def update_event(
        self,
        work_id: str,
        event_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        event_type: Optional[TimelineEventType] = None,
        timestamp: Optional[float] = None,
        relative_order: Optional[int] = None,
        duration: Optional[float] = None,
        characters: Optional[List[str]] = None,
        factions: Optional[List[str]] = None,
        location: Optional[str] = None,
        tags: Optional[List[str]] = None,
        certainty: Optional[str] = None,
    ) -> Dict[str, Any]:
        timeline = self.get_or_create_timeline(work_id)
        event = timeline.events.get(event_id)
        if not event:
            return {"status": "error", "error": "event_not_found"}

        if title is not None:
            event.title = title
        if description is not None:
            event.description = description
        if event_type is not None:
            event.event_type = event_type
        if timestamp is not None:
            event.timestamp = timestamp
        if relative_order is not None:
            event.relative_order = relative_order
        if duration is not None:
            event.duration = duration
        if characters is not None:
            event.characters = characters
        if factions is not None:
            event.factions = factions
        if location is not None:
            event.location = location
        if tags is not None:
            event.tags = tags
        if certainty is not None:
            event.certainty = certainty

        event.updated_at = time.time()
        self._save_timeline(work_id)
        return {"status": "updated", "event": event.to_dict()}

    def delete_event(self, work_id: str, event_id: str) -> Dict[str, Any]:
        timeline = self.get_or_create_timeline(work_id)
        if timeline.remove_event(event_id):
            self._save_timeline(work_id)
            return {"status": "deleted"}
        return {"status": "error", "error": "event_not_found"}

    def get_event(self, work_id: str, event_id: str) -> Dict[str, Any]:
        timeline = self.get_or_create_timeline(work_id)
        event = timeline.events.get(event_id)
        if not event:
            return {"status": "error", "error": "event_not_found"}
        return {"status": "ok", "event": event.to_dict()}

    def list_events(
        self,
        work_id: str,
        event_type: Optional[TimelineEventType] = None,
        character_id: Optional[str] = None,
        faction_id: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        timeline = self.get_or_create_timeline(work_id)

        events = list(timeline.events.values())

        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if character_id:
            events = [e for e in events if character_id in e.characters]
        if faction_id:
            events = [e for e in events if faction_id in e.factions]
        if start_time is not None:
            events = [e for e in events if e.timestamp >= start_time]
        if end_time is not None:
            events = [e for e in events if e.timestamp <= end_time]

        events.sort(key=lambda e: (e.timestamp, e.relative_order))
        events = events[:limit]

        return {
            "status": "ok",
            "work_id": work_id,
            "events": [e.to_dict() for e in events],
            "count": len(events),
        }

    def get_chronology(self, work_id: str, max_events: int = 50) -> Dict[str, Any]:
        timeline = self.get_or_create_timeline(work_id)
        events = timeline.get_events_sorted()[:max_events]
        return {
            "status": "ok",
            "work_id": work_id,
            "events": [e.to_dict() for e in events],
            "count": len(events),
        }

    # --- Link Operations ---

    def add_link(
        self,
        work_id: str,
        source_id: str,
        target_id: str,
        relation: TemporalRelation,
        strength: float = 1.0,
        evidence: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        timeline = self.get_or_create_timeline(work_id)

        if source_id not in timeline.events or target_id not in timeline.events:
            return {"status": "error", "error": "event_not_found"}

        link = TimelineLink(
            source_id=source_id,
            target_id=target_id,
            relation=relation,
            strength=strength,
            evidence=evidence or [],
        )

        timeline.add_link(link)
        self._save_timeline(work_id)
        return {"status": "created", "link": link.to_dict()}

    def remove_link(self, work_id: str, source_id: str, target_id: str, relation: TemporalRelation) -> Dict[str, Any]:
        timeline = self.get_or_create_timeline(work_id)
        if timeline.remove_link(source_id, target_id, relation):
            self._save_timeline(work_id)
            return {"status": "removed"}
        return {"status": "error", "error": "link_not_found"}

    def get_links(self, work_id: str, event_id: Optional[str] = None) -> Dict[str, Any]:
        timeline = self.get_or_create_timeline(work_id)

        links = list(timeline.links.values())
        if event_id:
            links = [l for l in links if l.source_id == event_id or l.target_id == event_id]

        return {
            "status": "ok",
            "work_id": work_id,
            "links": [l.to_dict() for l in links],
        }

    # --- Thread Operations ---

    def create_thread(
        self,
        work_id: str,
        thread_id: str,
        name: str,
        description: str = "",
        color: str = "#888888",
        character_ids: Optional[List[str]] = None,
        is_main: bool = False,
    ) -> Dict[str, Any]:
        timeline = self.get_or_create_timeline(work_id)

        if thread_id in timeline.threads:
            return {"status": "error", "error": "thread_exists"}

        thread = NarrativeThread(
            thread_id=thread_id,
            work_id=work_id,
            name=name,
            description=description,
            color=color,
            character_ids=character_ids or [],
            is_main=is_main,
        )

        timeline.add_thread(thread)
        self._save_timeline(work_id)
        return {"status": "created", "thread": thread.to_dict()}

    def update_thread(
        self,
        work_id: str,
        thread_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[str] = None,
        character_ids: Optional[List[str]] = None,
        is_main: Optional[bool] = None,
    ) -> Dict[str, Any]:
        timeline = self.get_or_create_timeline(work_id)
        thread = timeline.threads.get(thread_id)
        if not thread:
            return {"status": "error", "error": "thread_not_found"}

        if name is not None:
            thread.name = name
        if description is not None:
            thread.description = description
        if color is not None:
            thread.color = color
        if character_ids is not None:
            thread.character_ids = character_ids
        if is_main is not None:
            thread.is_main = is_main
            if is_main:
                timeline.main_thread_id = thread_id

        thread.updated_at = time.time()
        self._save_timeline(work_id)
        return {"status": "updated", "thread": thread.to_dict()}

    def delete_thread(self, work_id: str, thread_id: str) -> Dict[str, Any]:
        timeline = self.get_or_create_timeline(work_id)
        if timeline.remove_thread(thread_id):
            self._save_timeline(work_id)
            return {"status": "deleted"}
        return {"status": "error", "error": "thread_not_found"}

    def list_threads(self, work_id: str) -> Dict[str, Any]:
        timeline = self.get_or_create_timeline(work_id)
        return {
            "status": "ok",
            "work_id": work_id,
            "threads": [t.to_dict() for t in timeline.threads.values()],
        }

    def get_thread(self, work_id: str, thread_id: str) -> Dict[str, Any]:
        timeline = self.get_or_create_timeline(work_id)
        thread = timeline.threads.get(thread_id)
        if not thread:
            return {"status": "error", "error": "thread_not_found"}
        events = timeline.get_thread_events(thread_id)
        return {
            "status": "ok",
            "thread": thread.to_dict(),
            "events": [e.to_dict() for e in events],
        }

    def add_event_to_thread(self, work_id: str, thread_id: str, event_id: str) -> Dict[str, Any]:
        timeline = self.get_or_create_timeline(work_id)
        thread = timeline.threads.get(thread_id)
        if not thread:
            return {"status": "error", "error": "thread_not_found"}
        if event_id not in timeline.events:
            return {"status": "error", "error": "event_not_found"}

        if event_id not in thread.event_ids:
            thread.event_ids.append(event_id)
            thread.event_ids.sort(key=lambda eid: timeline.events[eid].timestamp)
            thread.updated_at = time.time()
            self._save_timeline(work_id)
        return {"status": "added"}

    # --- Chronology Validation (Jan Integration) ---

    def validate_chronology(
        self,
        work_id: str,
        new_event: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Valida que un nuevo evento no contradiga la cronología establecida."""
        timeline = self.get_or_create_timeline(work_id)

        new_timestamp = new_event.get("timestamp", 0)
        new_type = new_event.get("event_type", "canon")
        new_desc = new_event.get("description", "").lower()

        conflicts = []
        warnings = []

        # Check for temporal paradoxes
        for event in timeline.events.values():
            if event.event_id == new_event.get("event_id"):
                continue

            # Flashback validation
            if new_type == "flashback" and new_timestamp >= event.timestamp:
                warnings.append({
                    "type": "flashback_timing",
                    "message": f"Flashback ({new_timestamp}) no es anterior a evento existente ({event.timestamp})",
                    "existing_event": event.to_dict(),
                })

            # Flashforward validation
            if new_type == "flashforward" and new_timestamp <= event.timestamp:
                warnings.append({
                    "type": "flashforward_timing",
                    "message": f"Flashforward ({new_timestamp}) no es posterior a evento existente ({event.timestamp})",
                    "existing_event": event.to_dict(),
                })

            # Causality check
            if "causes" in new_desc and "caused by" in event.description.lower():
                conflicts.append({
                    "type": "causality_loop",
                    "message": f"Posible bucle causal con '{event.title}'",
                    "existing_event": event.to_dict(),
                })

            # Contradiction keywords
            contradictions = [
                ("murió", "sobrevivió"),
                ("sobrevivió", "murió"),
                ("antes", "después"),
                ("después", "antes"),
                ("nunca", "siempre"),
            ]
            for a, b in contradictions:
                if a in new_desc and b in event.description.lower():
                    conflicts.append({
                        "type": "temporal_contradiction",
                        "message": f"Contradicción temporal: '{a}' vs '{b}' con '{event.title}'",
                        "existing_event": event.to_dict(),
                    })

        return {
            "status": "ok",
            "valid": len(conflicts) == 0 and len(warnings) == 0,
            "conflicts": conflicts,
            "warnings": warnings,
        }

    def check_event_sequence(self, work_id: str, event_ids: List[str]) -> Dict[str, Any]:
        """Verifica que una secuencia de eventos sea cronológicamente coherente en el orden dado."""
        timeline = self.get_or_create_timeline(work_id)

        events = []
        for eid in event_ids:
            event = timeline.events.get(eid)
            if event:
                events.append(event)

        issues = []
        for i in range(len(events) - 1):
            curr = events[i]
            next_e = events[i + 1]
            if curr.timestamp > next_e.timestamp:
                issues.append({
                    "type": "sequence_violation",
                    "message": f"'{curr.title}' ({curr.timestamp}) ocurre después de '{next_e.title}' ({next_e.timestamp})",
                    "event_a": curr.to_dict(),
                    "event_b": next_e.to_dict(),
                })

        return {
            "status": "ok",
            "valid": len(issues) == 0,
            "issues": issues,
            "sorted_events": [e.to_dict() for e in events],
        }

    def get_timeline_stats(self, work_id: str) -> Dict[str, Any]:
        timeline = self.get_or_create_timeline(work_id)

        by_type = {}
        for event in timeline.events.values():
            t = event.event_type.value
            by_type[t] = by_type.get(t, 0) + 1

        time_span = 0
        if timeline.events:
            timestamps = [e.timestamp for e in timeline.events.values() if e.timestamp > 0]
            if timestamps:
                time_span = max(timestamps) - min(timestamps)

        return {
            "status": "ok",
            "work_id": work_id,
            "total_events": len(timeline.events),
            "total_links": len(timeline.links),
            "total_threads": len(timeline.threads),
            "by_type": by_type,
            "time_span": time_span,
            "main_thread": timeline.main_thread_id,
        }

    def export_timeline(self, work_id: str) -> Dict[str, Any]:
        """Exporta la línea de tiempo completa para visualización."""
        timeline = self.get_or_create_timeline(work_id)

        nodes = []
        for event in timeline.events.values():
            nodes.append({
                "id": event.event_id,
                "label": event.title,
                "type": event.event_type.value,
                "timestamp": event.timestamp,
                "description": event.description,
                "characters": event.characters,
                "color": self._get_event_color(event.event_type),
            })

        edges = []
        for link in timeline.links.values():
            edges.append({
                "source": link.source_id,
                "target": link.target_id,
                "relation": link.relation.value,
                "strength": link.strength,
            })

        threads = []
        for thread in timeline.threads.values():
            thread_events = timeline.get_thread_events(thread.thread_id)
            threads.append({
                "id": thread.thread_id,
                "name": thread.name,
                "color": thread.color,
                "is_main": thread.is_main,
                "event_count": len(thread_events),
                "events": [e.event_id for e in thread_events],
            })

        return {
            "status": "ok",
            "work_id": work_id,
            "nodes": nodes,
            "edges": edges,
            "threads": threads,
            "stats": self.get_timeline_stats(work_id),
        }

    def import_timeline(self, work_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Importa datos de la línea de tiempo desde un backup (formato export_timeline)."""
        try:
            timeline = self.get_or_create_timeline(work_id)
            
            # Clear existing data
            timeline.events.clear()
            timeline.links.clear()
            timeline.threads.clear()
            
            # Import events (nodes in export format)
            for node in data.get("nodes", []):
                event_id = node.get("id")
                if event_id:
                    # Convert export format back to TimelineEvent
                    from backend.story_memory.timeline_manager import TimelineEvent, TimelineEventType
                    event = TimelineEvent(
                        event_id=event_id,
                        title=node.get("label", ""),
                        event_type=TimelineEventType(node.get("type", "CANON")),
                        timestamp=node.get("timestamp", 0),
                        description=node.get("description", ""),
                        characters=node.get("characters", []),
                    )
                    timeline.events[event_id] = event
            
            # Import links (edges in export format)
            for edge in data.get("edges", []):
                from backend.story_memory.timeline_manager import TimelineLink, TemporalRelation
                link = TimelineLink(
                    source_id=edge.get("source", ""),
                    target_id=edge.get("target", ""),
                    relation=TemporalRelation(edge.get("relation", "BEFORE")),
                    strength=edge.get("strength", 1.0),
                )
                link_key = f"{link.source_id}->{link.target_id}:{link.relation.value}"
                timeline.links[link_key] = link
            
            # Import threads
            for thread_data in data.get("threads", []):
                from backend.story_memory.timeline_manager import NarrativeThread
                thread = NarrativeThread(
                    thread_id=thread_data.get("id", ""),
                    name=thread_data.get("name", ""),
                    color=thread_data.get("color", "#888888"),
                    is_main=thread_data.get("is_main", False),
                )
                timeline.threads[thread.thread_id] = thread
            
            # Save to disk
            self._save_timeline(work_id)
            return {"status": "ok", "work_id": work_id, "imported": True}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _get_event_color(self, event_type: TimelineEventType) -> str:
        colors = {
            TimelineEventType.CANON: "#4CAF50",
            TimelineEventType.CONTINUITY: "#2196F3",
            TimelineEventType.CHAPTER: "#FF9800",
            TimelineEventType.SCENE: "#FFC107",
            TimelineEventType.FLASHBACK: "#9C27B0",
            TimelineEventType.FLASHFORWARD: "#E91E63",
            TimelineEventType.BACKSTORY: "#607D8B",
            TimelineEventType.PROLOGUE: "#00BCD4",
            TimelineEventType.EPILOGUE: "#795548",
        }
        return colors.get(event_type, "#888888")


_timeline_manager: Optional[TimelineManager] = None
_lock_init = threading.Lock()


def get_timeline_manager(store_dir: Optional[str] = None) -> TimelineManager:
    global _timeline_manager
    if _timeline_manager is None:
        with _lock_init:
            if _timeline_manager is None:
                _timeline_manager = TimelineManager(store_dir=store_dir)
    return _timeline_manager


def reset_timeline_manager() -> None:
    global _timeline_manager
    with _lock_init:
        _timeline_manager = None