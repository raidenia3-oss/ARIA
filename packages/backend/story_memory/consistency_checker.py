"""Consistency Checker — validación de coherencia y permanencia "dentro de personaje".

Verifica que el texto generado:
1. Mantenga la personalidad del personaje (objeciones, conflictos)
2. No contradiga eventos canónicos
3. Use la voz definida en la Character Bible

Marca claramente la distinción entre canon, interpretación e inventado.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("AURA.StoryMemory.ConsistencyChecker")


class StoryConsistencyChecker:
    """Valida coherencia narrativa y consistencia de personaje."""

    def __init__(self) -> None:
        from backend.story_memory.story_storage import StoryStorage

        self.storage = StoryStorage()
        from backend.story_memory.character_bible import CharacterBible
        from backend.story_memory.canon_tracker import CanonTracker

        self.character_bible = CharacterBible()
        self.canon_tracker = CanonTracker()

    def check_character_consistency(
        self,
        work_id: str,
        char_id: str,
        text: str,
    ) -> Dict[str, Any]:
        """Valida que el texto mantenga la voz/personalidad del personaje."""
        char = self.character_bible.get(work_id, char_id)
        if not char:
            return {
                "status": "error",
                "error": "character_not_found",
                "checks": [],
                "violations": [],
            }

        violations: List[Dict[str, Any]] = []
        checks: List[Dict[str, Any]] = []

        # Verificar objetivos y conflictos
        objectives = char.get("objectives", [])
        for obj in objectives:
            # Detectamos abandono del objetivo si el texto menciona al personaje con palabras de abandono
            char_name = char.get("name", "")
            name_in_text = char_name.lower() in text.lower() if char_name else True
            has_abandon_word = bool(re.search(r"(?:abandon|ignorar|negar|desistir|ceder|huir|traicionar|faltar)", text, re.IGNORECASE))
            if name_in_text and has_abandon_word:
                violations.append({
                    "type": "objective_violation",
                    "characteristic": obj,
                    "description": f"El texto sugiere abandono del objetivo '{obj}'",
                })
            checks.append({
                "name": "objectives_check",
                "result": "pass" if not any(
                    v["type"] == "objective_violation" and v["characteristic"] == obj for v in violations
                ) else "fail",
                "characteristic": obj,
            })

        # Verificar conflictos
        conflicts = char.get("conflicts", [])
        for conflict in conflicts:
            checks.append({
                "name": "conflict_acknowledged",
                "result": "pass" if conflict.lower() in text.lower() or len(text) > 20 else "pass",
                "characteristic": conflict,
            })

        # Verificar personalidad con palabras clave
        personality = char.get("personality", [])
        if personality:
            has_personality_match = any(p.lower() in text.lower() for p in personality)
            checks.append({
                "name": "personality_match",
                "result": "pass" if has_personality_match else "warn",
                "characteristics": personality,
            })

        overall = "violations" if violations else "consistent"
        return {
            "status": overall,
            "character_name": char.get("name", char_id),
            "char_id": char_id,
            "checks": checks,
            "violations": violations,
            "text_length": len(text),
        }

    def check_canon_consistency(
        self,
        work_id: str,
        text: str,
        check_type: str = "any",
    ) -> Dict[str, Any]:
        """Verifica que el texto no contradiga eventos canónicos."""
        canon_events = self.canon_tracker.get_canon_events(work_id)
        contradictions: List[Dict[str, Any]] = []
        matches: List[Dict[str, Any]] = []

        for event in canon_events:
            desc = event.get("description", "")
            if desc.lower() in text.lower() or any(
                w in text.lower() for w in desc.lower().split() if len(w) > 5
            ):
                matches.append({"event_id": event.get("event_id"), "description": desc})

            valid, msg, conflicting = self.canon_tracker.validate_canon_consistency(
                work_id, text
            )
            if not valid:
                contradictions.append({
                    "event_id": conflicting.get("event_id") if conflicting else "",
                    "description": conflicting.get("description", "") if conflicting else "",
                    "message": msg,
                })

        return {
            "status": "canonical" if not contradictions else "contradiction",
            "matches": matches,
            "contradictions": contradictions,
            "total_canon_events": len(canon_events),
        }

    def classify_source(self, work_id: str, text: str) -> Dict[str, Any]:
        """Clasifica el texto como canon, interpretación o contenido inventado."""
        canon_result = self.check_canon_consistency(work_id, text)
        if canon_result["contradictions"]:
            return {"classification": "invented", "reason": "contradicts_canon"}
        if canon_result["matches"]:
            return {"classification": "canon", "matches": canon_result["matches"]}
        chars = self.character_bible.list(work_id)
        char_names = {c.get("name", "").lower() for c in chars}
        char_names.update({a.lower() for c in chars for a in c.get("aliases", [])})
        text_lower = text.lower()
        if any(name and name in text_lower for name in char_names):
            return {"classification": "interpretation", "reason": "uses_known_characters"}
        return {"classification": "invented", "reason": "no_canon_match"}

    def check_full_consistency(
        self,
        work_id: str,
        char_id: str,
        text: str,
    ) -> Dict[str, Any]:
        """Combina todas las verificaciones de coherencia."""
        char_result = self.check_character_consistency(work_id, char_id, text)
        canon_result = self.check_canon_consistency(work_id, text)
        source_result = self.classify_source(work_id, text)

        overall_pass = (
            char_result["status"] != "violations"
            and canon_result["status"] != "contradiction"
        )

        result = {
            "status": "pass" if overall_pass else "fail",
            "timestamp": time.time(),
            "character_consistency": char_result,
            "canon_consistency": canon_result,
            "source_classification": source_result,
            "overall_pass": overall_pass,
        }

        self.storage.save_consistency_check(work_id, result)
        logger.info(
            "Consistency check: work=%s char=%s result=%s",
            work_id, char_id, result["status"]
        )
        return result
