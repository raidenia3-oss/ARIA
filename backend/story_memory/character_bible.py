"""Character Bible — voz, personalidad, objetivos, conflictos y relaciones por personaje.

Almacena y valida la definición de un personaje dentro de una obra.

Estructura JSON de un personaje:
{
    "char_id": "nombre_unico",
    "name": "Nombre Real",
    "aliases": ["Apodo1", "Apodo2"],
    "species": "humano",
    "age": 34,
    "voice": "Tercera persona, tono cínico, frases cortas.",
    "personality": ["ingenioso", "cauto", "leal"],
    "objectives": ["sobrevivir", "descubrir la verdad"],
    "conflicts": ["con el pasado", "con su propia naturaleza"],
    "relationships": {
        "otro_personaje": "alianza fluctuante"
    },
    "backstory": "Breve resumen de su historia..."
}
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURA.StoryMemory.CharacterBible")


class CharacterBible:
    """Gestión de la biblia de personajes para una obra literaria."""

    def __init__(self) -> None:
        from backend.story_memory.story_storage import StoryStorage

        self.storage = StoryStorage()
        self._cache: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def _cache_key(self, work_id: str) -> str:
        return work_id

    def _load_chars(self, work_id: str) -> Dict[str, Dict[str, Any]]:
        if work_id not in self._cache:
            chars = self.storage.list_characters(work_id)
            self._cache[work_id] = {c["char_id"]: c for c in chars if "char_id" in c}
        return self._cache[work_id]

    def get(self, work_id: str, char_id: str) -> Optional[Dict[str, Any]]:
        chars = self._load_chars(work_id)
        return chars.get(char_id)

    def get_by_name(self, work_id: str, name: str) -> Optional[Dict[str, Any]]:
        chars = self._load_chars(work_id)
        name_lower = name.lower().strip()
        for char in chars.values():
            if char.get("name", "").lower() == name_lower:
                return char
            aliases = char.get("aliases", [])
            if any(a.lower() == name_lower for a in aliases):
                return char
        return None

    def list(self, work_id: str) -> List[Dict[str, Any]]:
        return list(self._load_chars(work_id).values())

    def create(
        self,
        work_id: str,
        char_id: str,
        name: str,
        voice: str = "",
        personality: Optional[List[str]] = None,
        objectives: Optional[List[str]] = None,
        conflicts: Optional[List[str]] = None,
        relationships: Optional[Dict[str, str]] = None,
        aliases: Optional[List[str]] = None,
        species: str = "",
        age: Optional[int] = None,
        backstory: str = "",
    ) -> Dict[str, Any]:
        char_data = {
            "char_id": char_id,
            "name": name,
            "aliases": aliases or [],
            "species": species,
            "age": age,
            "voice": voice,
            "personality": personality or [],
            "objectives": objectives or [],
            "conflicts": conflicts or [],
            "relationships": relationships or {},
            "backstory": backstory,
        }
        result = self.storage.save_character(work_id, char_id, char_data)
        self._cache.pop(work_id, None)
        logger.info("Character created: work=%s char_id=%s name=%s", work_id, char_id, name)
        return {**result, "character": char_data}

    def update(self, work_id: str, char_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        existing = self.get(work_id, char_id)
        if not existing:
            return {"status": "error", "error": "character_not_found"}
        for key in ("voice", "personality", "objectives", "conflicts", "relationships",
                     "aliases", "species", "age", "backstory", "name"):
            if key in updates:
                existing[key] = updates[key]
        result = self.storage.save_character(work_id, char_id, existing)
        self._cache.pop(work_id, None)
        return {**result, "character": existing}

    def delete(self, work_id: str, char_id: str) -> Dict[str, Any]:
        result = self.storage.delete_character(work_id, char_id)
        self._cache.pop(work_id, None)
        return result

    def build_personality_prompt(self, work_id: str, char_id: str) -> str:
        """Construye el system prompt de personalidad para chat/inyección."""
        char = self.get(work_id, char_id)
        if not char:
            return ""
        parts: List[str] = []
        name = char.get("name", char_id)
        parts.append(f"Personaje: {name}")
        if char.get("aliases"):
            parts.append(f"Alias: {', '.join(char['aliases'])}")
        if char.get("species"):
            parts.append(f"Especie: {char['species']}")
        if char.get("age") is not None:
            parts.append(f"Edad: {char['age']}")
        if char.get("voice"):
            parts.append(f"Voz/Narrativa: {char['voice']}")
        if char.get("personality"):
            parts.append(f"Personalidad: {', '.join(char['personality'])}")
        if char.get("objectives"):
            parts.append(f"Objetivos: {', '.join(char['objectives'])}")
        if char.get("conflicts"):
            parts.append(f"Conflictos: {', '.join(char['conflicts'])}")
        if char.get("relationships"):
            rels = "; ".join(f"{k}: {v}" for k, v in char["relationships"].items())
            parts.append(f"Relaciones: {rels}")
        if char.get("backstory"):
            parts.append(f"Historia: {char['backstory']}")
        return "\n".join(parts)
