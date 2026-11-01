"""Canon Tracker — gestión de canon, continuidad y cronología.

Distingue tres categorías de eventos narrativos:
- canon: hechos establecidos oficialmente (firmativos)
- continuity: eventos derivados o de continuidad (no contradictorios)
- invented: contenido original creado por el usuario/IA (no canónico)

Cada evento lleva un timestamp para orden cronológico y un nivel de certeza.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("AURA.StoryMemory.CanonTracker")


class CanonTracker:
    """Gestión de eventos canónicos y de continuidad por obra."""

    def __init__(self) -> None:
        from backend.story_memory.story_storage import StoryStorage

        self.storage = StoryStorage()

    def add_canon_event(
        self,
        work_id: str,
        description: str,
        timestamp: float = 0,
        scene_ref: str = "",
        source: str = "user",
    ) -> Dict[str, Any]:
        event = {
            "description": description,
            "timestamp": timestamp or time.time(),
            "scene_ref": scene_ref,
            "source": source,
            "certainty": "canon",
        }
        return self.storage.add_canon_event(work_id, event)

    def add_continuity_event(
        self,
        work_id: str,
        description: str,
        timestamp: float = 0,
        scene_ref: str = "",
        source: str = "user",
    ) -> Dict[str, Any]:
        event = {
            "description": description,
            "timestamp": timestamp or time.time(),
            "scene_ref": scene_ref,
            "source": source,
            "certainty": "continuity",
        }
        return self.storage.add_continuity_event(work_id, event)

    def get_canon_events(self, work_id: str) -> List[Dict[str, Any]]:
        events = self.storage.get_canon_events(work_id)
        for e in events:
            e.setdefault("certainty", "canon")
        return events

    def get_continuity_events(self, work_id: str) -> List[Dict[str, Any]]:
        events = self.storage.get_continuity_events(work_id)
        for e in events:
            e.setdefault("certainty", "continuity")
        return events

    def get_all_events(self, work_id: str) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        events.extend(self.get_canon_events(work_id))
        events.extend(self.get_continuity_events(work_id))
        events.sort(key=lambda x: x.get("timestamp", 0))
        return events

    def get_chronology(self, work_id: str, max_events: int = 50) -> List[Dict[str, Any]]:
        all_events = self.get_all_events(work_id)
        return all_events[:max_events]

    def validate_canon_consistency(
        self, work_id: str, new_description: str
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Verifica que un nuevo evento canónico no contradiga eventos existentes.

        Retorna (is_valid, message, existing_event).
        """
        canon_events = self.get_canon_events(work_id)
        for event in canon_events:
            existing = event.get("description", "").lower()
            new = new_description.lower()
            contradictions = [
                ("murió", "sobrevivió"),
                ("sobrevivió", "murió"),
                ("regresó", "desapareció"),
                ("desapareció", "regresó"),
                ("aceptó", "rechazó"),
                ("rechazó", "aceptó"),
            ]
            for a, b in contradictions:
                if a in new and b in existing:
                    return False, f"Contradicción: '{b}' vs '{a}'", event
        return True, "consistente", None

    def find_conflicts(self, work_id: str) -> List[Dict[str, Any]]:
        """Busca contradicciones entre eventos de canon."""
        conflicts: List[Dict[str, Any]] = []
        canon = self.get_canon_events(work_id)
        for i, a in enumerate(canon):
            for b in canon[i + 1:]:
                contradictions = [
                    ("murió", "sobrevivió"),
                    ("sobrevivió", "murió"),
                    ("regresó", "desapareció"),
                    ("desapareció", "regresó"),
                ]
                for term_a, term_b in contradictions:
                    if term_a in a.get("description", "").lower() and term_b in b.get("description", "").lower():
                        conflicts.append({
                            "event_a": a,
                            "event_b": b,
                            "contradiction": f"{term_a} vs {term_b}",
                        })
        return conflicts

    def build_canon_context(self, work_id: str, max_items: int = 10) -> str:
        """Construye el bloque de contexto canónico para inyección en system prompt."""
        events = self.get_chronology(work_id, max_events=max_items)
        if not events:
            return ""
        lines = ["[CANON — Eventos establecidos]"]
        for e in events:
            ts = e.get("timestamp", 0)
            source = e.get("source", "unknown")
            certainty = e.get("certainty", "canon")
            lines.append(f"  [{source}/{certainty}] {ts:.0f}: {e.get('description', '')}")
        return "\n".join(lines)
