"""Character persona manager for AURA - Module 27.

Importacion y parseo de tarjetas de personaje (formato PNG V2/JSON),
inyeccion de prompts de personalidad y cambio dinamico de contexto.
"""

from __future__ import annotations

import base64
import json
import os
import struct
import time
import uuid
import zlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class CharacterCard:
    card_id: str
    name: str
    description: str
    personality: str
    scenario: str
    first_mes: str
    mes_example: str
    system_prompt: str
    tags: List[str]
    avatar: str
    format: str
    raw: Dict[str, Any]
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "card_id": self.card_id,
            "name": self.name,
            "description": self.description,
            "personality": self.personality,
            "scenario": self.scenario,
            "first_mes": self.first_mes,
            "mes_example": self.mes_example,
            "system_prompt": self.system_prompt,
            "tags": self.tags,
            "format": self.format,
            "created_at": self.created_at,
        }


class CharacterCardParser:
    """Parsea tarjetas de personaje PNG V2, JSON y base64."""

    PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

    def __init__(self) -> None:
        self._cache: Dict[str, CharacterCard] = {}
        self._max_cache = 200

    def parse_file(self, filepath: str) -> Optional[CharacterCard]:
        if not os.path.isfile(filepath):
            return None
        with open(filepath, "rb") as f:
            data = f.read()
        return self.parse_bytes(data, source=filepath)

    def parse_base64(self, b64_data: str) -> Optional[CharacterCard]:
        try:
            if b64_data.startswith("data:"):
                b64_data = b64_data.split(",", 1)[-1]
            raw = base64.b64decode(b64_data)
            return self.parse_bytes(raw, source="base64")
        except Exception:
            return None

    def parse_json(self, json_str: str) -> Optional[CharacterCard]:
        try:
            data = json.loads(json_str)
            return self._from_json(data, source="json")
        except (json.JSONDecodeError, ValueError):
            return None

    def parse_bytes(self, data: bytes, source: str = "") -> Optional[CharacterCard]:
        if data[:8] == self.PNG_SIGNATURE:
            char_json = self._extract_png_text(data)
            if char_json:
                return self._from_json(char_json, source="png_v2")
        else:
            try:
                text = data.decode("utf-8")
                return self._from_json(json.loads(text), source="json")
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
                pass
        return None

    def parse(self, input_data: Any, source: str = "") -> Optional[CharacterCard]:
        if isinstance(input_data, bytes):
            return self.parse_bytes(input_data, source)
        if isinstance(input_data, str):
            stripped = input_data.strip()
            if stripped.startswith("{"):
                return self.parse_json(stripped)
            if os.path.isfile(stripped):
                return self.parse_file(stripped)
            if stripped.startswith(("data:image", "data:application")) or len(stripped) > 100:
                return self.parse_base64(stripped)
            return self.parse_json(stripped)
        return None

    def _extract_png_text(self, data: bytes) -> Optional[Dict[str, Any]]:
        pos = 8
        while pos + 8 <= len(data):
            length = struct.unpack(">I", data[pos : pos + 4])[0]
            chunk_type = data[pos + 4 : pos + 8].decode("ascii", errors="replace")
            chunk_start = pos + 8
            chunk_data = data[chunk_start : chunk_start + length]
            pos = chunk_start + length + 4

            if chunk_type in ("tEXt", "iTXt", "zTXt"):
                try:
                    text = self._decode_text_chunk(chunk_type, chunk_data)
                    if text is None:
                        continue
                    null_idx = text.find("\x00")
                    if null_idx == -1:
                        continue
                    keyword = text[:null_idx]
                    value = text[null_idx + 1 :]
                    if keyword.strip() in ("chara", "cc", "Comment"):
                        return json.loads(value.replace("\x00", ""))
                except (json.JSONDecodeError, ValueError):
                    continue
        return None

    @staticmethod
    def _decode_text_chunk(chunk_type: str, chunk_data: bytes) -> Optional[str]:
        try:
            if chunk_type == "tEXt":
                return chunk_data.decode("latin-1")
            if chunk_type == "iTXt":
                parts = chunk_data.split(b"\x00")
                if len(parts) >= 5:
                    return parts[4].decode("utf-8", errors="replace")
                return chunk_data.decode("utf-8", errors="replace")
            if chunk_type == "zTXt":
                null_idx = chunk_data.find(b"\x00")
                if null_idx == -1:
                    return None
                compressed = chunk_data[null_idx + 2 :]
                return zlib.decompress(compressed).decode("utf-8", errors="replace")
        except Exception:
            return None
        return None

    def _from_json(self, data: Dict[str, Any], source: str) -> CharacterCard:
        card_data = data.get("data", data) if isinstance(data, dict) else {}
        if not isinstance(card_data, dict):
            card_data = {}

        card_id = card_data.get("extension", {}).get("id") or f"card-{uuid.uuid4().hex[:12]}"
        name = card_data.get("name", "Unknown Character")
        card = CharacterCard(
            card_id=str(card_id),
            name=str(name),
            description=str(card_data.get("description", "")),
            personality=str(card_data.get("personality", "")),
            scenario=str(card_data.get("scenario", "")),
            first_mes=str(card_data.get("first_mes", "")),
            mes_example=str(card_data.get("mes_example", "")),
            system_prompt=str(card_data.get("system_prompt", "")),
            tags=list(card_data.get("tags", []) or []),
            avatar=str(card_data.get("avatar", "")),
            format=source,
            raw=data,
        )
        if len(self._cache) >= self._max_cache:
            oldest = min(self._cache, key=lambda k: self._cache[k].created_at)
            del self._cache[oldest]
        self._cache[card.card_id] = card
        return card

    def cached(self, card_id: str) -> Optional[CharacterCard]:
        return self._cache.get(card_id)


class PersonaContextBuilder:
    """Construye prompts de sistema e inyecta contexto de personalidad."""

    def __init__(self) -> None:
        self._active: Dict[str, CharacterCard] = {}

    def set_active(self, session_id: str, card: CharacterCard) -> None:
        self._active[session_id] = card

    def get_active(self, session_id: str) -> Optional[CharacterCard]:
        return self._active.get(session_id)

    def clear_active(self, session_id: str) -> None:
        self._active.pop(session_id, None)

    def build_system_prompt(self, card: CharacterCard) -> str:
        parts: List[str] = [
            f"You are {card.name}.",
        ]
        if card.description:
            parts.append(f"Description: {card.description}")
        if card.personality:
            parts.append(f"Personality: {card.personality}")
        if card.scenario:
            parts.append(f"Scenario: {card.scenario}")
        if card.system_prompt:
            parts.append(card.system_prompt)
        if card.tags:
            parts.append(f"Tags: {', '.join(card.tags)}")
        return "\n\n".join(parts)

    def inject_into_messages(
        self,
        messages: List[Dict[str, Any]],
        card: CharacterCard,
    ) -> List[Dict[str, Any]]:
        system_prompt = self.build_system_prompt(card)
        first_mes = card.first_mes if card.first_mes else None

        result: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        if first_mes and not any(m.get("role") == "assistant" for m in messages):
            result.append({"role": "assistant", "content": first_mes})
        result.extend(messages)
        return result

    def build_context(
        self,
        session_id: str,
        messages: List[Dict[str, Any]],
        default_prompt: str = "",
    ) -> List[Dict[str, Any]]:
        card = self._active.get(session_id)
        if card:
            return self.inject_into_messages(messages, card)
        if default_prompt:
            return [{"role": "system", "content": default_prompt}] + messages
        return messages


class DynamicPersonaEngine:
    """Motor de personalidad dinámica con cambio en caliente de contexto de voz/chat."""

    def __init__(self) -> None:
        self.parser = CharacterCardParser()
        self.context_builder = PersonaContextBuilder()
        self.cards: Dict[str, CharacterCard] = {}
        self._load_from_storage()

    def _storage_dir(self) -> str:
        d = os.getenv("AURA_PERSONA_DIR", os.path.join(os.getcwd(), "personas"))
        os.makedirs(d, exist_ok=True)
        return d

    def _load_from_storage(self) -> None:
        sdir = self._storage_dir()
        for filename in os.listdir(sdir):
            filepath = os.path.join(sdir, filename)
            card = self.parser.parse_file(filepath)
            if card:
                self.cards[card.card_id] = card

    def import_card(self, input_data: Any, source: str = "") -> Dict[str, Any]:
        card = self.parser.parse(input_data, source)
        if card is None:
            return {"status": "error", "error": "unable_to_parse_card"}
        self.cards[card.card_id] = card
        sdir = self._storage_dir()
        if card.format == "png_v2":
            ext = ".png"
        else:
            ext = ".json"
        filepath = os.path.join(sdir, f"{card.card_id}{ext}")
        if ext == ".json":
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(card.raw, f, ensure_ascii=False, indent=2)
        return {
            "status": "imported",
            "card_id": card.card_id,
            "name": card.name,
            "source": card.format,
        }

    def list_cards(self) -> List[Dict[str, Any]]:
        return [c.to_dict() for c in self.cards.values()]

    def get_card(self, card_id: str) -> Optional[CharacterCard]:
        return self.cards.get(card_id) or self.parser.cached(card_id)

    def delete_card(self, card_id: str) -> bool:
        card = self.cards.pop(card_id, None)
        if card:
            sdir = self._storage_dir()
            for ext in (".png", ".json"):
                filepath = os.path.join(sdir, f"{card_id}{ext}")
                if os.path.exists(filepath):
                    os.remove(filepath)
            self.context_builder.clear_active(card_id)
            return True
        return False

    def set_persona(self, session_id: str, card_id: str) -> Dict[str, Any]:
        card = self.get_card(card_id)
        if not card:
            return {"status": "error", "error": "card_not_found"}
        self.context_builder.set_active(session_id, card)
        return {"status": "active", "session_id": session_id, "card_id": card_id, "name": card.name}

    def get_persona(self, session_id: str) -> Optional[Dict[str, Any]]:
        card = self.context_builder.get_active(session_id)
        if not card:
            return None
        return {"session_id": session_id, "card_id": card.card_id, "name": card.name, "active": True}

    def build_messages(
        self,
        session_id: str,
        messages: List[Dict[str, Any]],
        default_prompt: str = "",
    ) -> List[Dict[str, Any]]:
        return self.context_builder.build_context(session_id, messages, default_prompt)
