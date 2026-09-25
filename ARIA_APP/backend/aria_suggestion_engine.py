"""ARIA Suggestion Engine — Connects observer data to content generation."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Suggestion:
    suggestion_id: str
    title: str
    preview: str
    endpoint: str
    suggestion_type: str
    reason: str
    context: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    created_at: float = 0.0
    full_content: Optional[str] = None


@dataclass
class UserProfile:
    interests: List[str] = field(default_factory=list)
    preferred_types: List[str] = field(default_factory=list)
    rejected_suggestions: List[str] = field(default_factory=list)
    accepted_suggestions: List[str] = field(default_factory=list)
    interaction_count: int = 0
    response_style: str = "balanced"


class SuggestionEngine:
    """Connects observer context to content generator endpoints."""

    SUGGESTION_TITLES: Dict[str, str] = {
        "story": "[STORY] Nueva Historia Contextual",
        "character": "[CHAR] Diseño de Personaje",
        "world": "[WORLD] Construccion de Mundo",
        "prompt": "[PROMPT] Prompt Optimizado",
        "general": "[INFO] Sugerencia ARIA",
    }

    SUGGESTION_PREVIEWS: Dict[str, str] = {
        "story": "Genera una historia basada en tu actividad actual...",
        "character": "Crea un personaje adaptado a tu contexto...",
        "world": "Construye un mundo con reglas coherentes...",
        "prompt": "Optimiza un prompt para generación de imágenes...",
        "general": "Explora opciones de contenido creativo...",
    }

    def __init__(self) -> None:
        self._suggestions: Dict[str, Suggestion] = {}
        self._profiles: Dict[str, UserProfile] = {}
        self._db_path = str(Path.home() / ".aria" / "suggestions.db")
        self._init_db()
        self._active_loop = False

    def _init_db(self) -> None:
        db_dir = Path.home() / ".aria"
        db_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                suggestion_id TEXT UNIQUE,
                title TEXT,
                preview TEXT,
                endpoint TEXT,
                suggestion_type TEXT,
                context TEXT,
                status TEXT,
                created_at REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                suggestion_id TEXT,
                action TEXT,
                timestamp REAL
            )
        """)
        conn.commit()
        conn.close()

    async def generate_live_suggestions(
        self, context: dict, count: int = 3
    ) -> List[Dict[str, Any]]:
        suggestions: List[Dict[str, Any]] = []

        intent_type = context.get("intent_type") or context.get("category") or "general"
        keywords = context.get("keywords", []) or []
        mood_val = context.get("mood") or "idle"
        mood_intensity = context.get("intensity", 0)

        intent_map = {
            "design": "character",
            "storytelling": "story",
            "creation": "world",
            "research": "prompt",
            "security": "prompt",
            "media": "prompt",
            "communication": "story",
            "general": "story",
        }
        if intent_type in intent_map:
            intent_type = intent_map[intent_type]

        candidate_types = [intent_type, "story", "character", "world", "prompt"]
        seen = set()
        deduped = []
        for t in candidate_types:
            if t not in seen:
                seen.add(t)
                deduped.append(t)
        candidate_types = deduped[:count]

        mood = {"mood": mood_val, "intensity": mood_intensity}
        intent = {"intent": intent_type, "confidence": 0.5, "category": intent_type}

        for i, stype in enumerate(candidate_types):
            if len(suggestions) >= count:
                break

            sid = f"sig_{uuid.uuid4().hex[:12]}"
            title = self.SUGGESTION_TITLES.get(stype, "💡 Sugerencia ARIA")
            preview = self.SUGGESTION_PREVIEWS.get(
                stype, "Contenido creativo basado en tu contexto..."
            )
            endpoint_map = {
                "story": "/api/aria/generate/story",
                "character": "/api/aria/generate/character",
                "world": "/api/aria/generate/world",
                "prompt": "/api/aria/generate/prompt",
                "general": "/api/aria/content/suggest",
            }
            endpoint = endpoint_map.get(stype, "/api/aria/content/suggest")

            reason_parts = []
            if keywords and i == 0:
                reason_parts.append(f"Detectado: {', '.join(keywords[:4])}")
            if intent.get("confidence", 0) > 0.3:
                reason_parts.append(
                    f"Intención: {intent.get('intent')} ({intent.get('confidence', 0):.0%})"
                )
            reason = "; ".join(reason_parts) or "Actividad detectada"

            suggestion = Suggestion(
                suggestion_id=sid,
                title=title,
                preview=preview,
                endpoint=endpoint,
                suggestion_type=stype,
                reason=reason,
                context={"intent": intent, "keywords": keywords, "mood": mood},
                status="pending",
                created_at=time.time(),
            )
            self._suggestions[sid] = suggestion
            suggestions.append(
                {
                    "suggestion_id": sid,
                    "title": title,
                    "preview": preview,
                    "endpoint": endpoint,
                    "suggestion_type": stype,
                    "reason": reason,
                    "confidence": intent.get("confidence", 0.5),
                }
            )

            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "INSERT OR REPLACE INTO suggestions (suggestion_id, title, preview, endpoint, suggestion_type, context, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (sid, title, preview, endpoint, stype, json.dumps(context), "pending", time.time()),
            )
            conn.commit()
            conn.close()

        return suggestions

    async def accept_suggestion(self, suggestion_id: str) -> Dict[str, Any]:
        suggestion = self._suggestions.get(suggestion_id)
        if not suggestion:
            conn = sqlite3.connect(self._db_path)
            row = conn.execute(
                "SELECT * FROM suggestions WHERE suggestion_id = ?", (suggestion_id,)
            ).fetchone()
            conn.close()
            if row:
                suggestion = Suggestion(
                    suggestion_id=row[1],
                    title=row[2],
                    preview=row[3],
                    endpoint=row[4],
                    suggestion_type=row[5],
                    reason="",
                    context=json.loads(row[6] or "{}"),
                    status=row[7],
                    created_at=row[8],
                )
            else:
                return {"status": "error", "message": "Sugerencia no encontrada"}

        suggestion.status = "accepted"
        profile = self._get_or_create_profile()
        profile.accepted_suggestions.append(suggestion_id)
        profile.interaction_count += 1

        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "UPDATE suggestions SET status = 'accepted' WHERE suggestion_id = ?", (suggestion_id,)
        )
        conn.execute(
            "INSERT INTO feedback (suggestion_id, action, timestamp) VALUES (?, ?, ?)",
            (suggestion_id, "accept", time.time()),
        )
        conn.commit()
        conn.close()

        return {
            "status": "accepted",
            "suggestion_id": suggestion_id,
            "suggestion_type": suggestion.suggestion_type,
            "endpoint": suggestion.endpoint,
            "message": f"Ejecutando: {suggestion.title}",
        }

    async def learn_from_rejection(self, suggestion_id: str) -> Dict[str, Any]:
        suggestion = self._suggestions.get(suggestion_id)
        if not suggestion:
            conn = sqlite3.connect(self._db_path)
            row = conn.execute(
                "SELECT * FROM suggestions WHERE suggestion_id = ?", (suggestion_id,)
            ).fetchone()
            conn.close()
            if row:
                suggestion = Suggestion(
                    suggestion_id=row[1],
                    title=row[2],
                    preview=row[3],
                    endpoint=row[4],
                    suggestion_type=row[5],
                    reason="",
                    context=json.loads(row[6] or "{}"),
                    status=row[7],
                    created_at=row[8],
                )
            else:
                return {
                    "status": "rejected",
                    "suggestion_id": suggestion_id,
                    "message": "Sugerencia no encontrada",
                }

        suggestion.status = "rejected"
        profile = self._get_or_create_profile()
        profile.rejected_suggestions.append(suggestion_id)
        profile.interaction_count += 1

        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "UPDATE suggestions SET status = 'rejected' WHERE suggestion_id = ?", (suggestion_id,)
        )
        conn.execute(
            "INSERT INTO feedback (suggestion_id, action, timestamp) VALUES (?, ?, ?)",
            (suggestion_id, "reject", time.time()),
        )
        conn.commit()
        conn.close()

        return {
            "status": "rejected",
            "suggestion_id": suggestion_id,
            "message": "Sugerencia marcada como irrelevante. ARIA ajustará futuras recomendaciones.",
        }

    async def personalize_suggestions(self, user_profile: dict) -> List[Dict[str, Any]]:
        profile = self._get_or_create_profile()
        for key in ["interests", "preferred_types", "rejected_suggestions"]:
            if key in user_profile:
                setattr(profile, key, user_profile[key])

        conn = sqlite3.connect(self._db_path)
        rows = conn.execute(
            "SELECT * FROM suggestions WHERE status = 'pending' ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
        conn.close()

        personalized: List[Dict[str, Any]] = []
        for row in rows:
            stype = row[5]
            title = row[2]
            preview = row[3]
            endpoint = row[4]
            sid = row[1]

            if sid in profile.rejected_suggestions:
                continue

            boost = 1.0
            if profile.preferred_types and stype in profile.preferred_types:
                boost += 0.5
            if profile.interests:
                for interest in profile.interests:
                    if interest.lower() in (title + " " + preview + " " + str(row[6])).lower():
                        boost += 0.3

            personalized.append(
                {
                    "suggestion_id": sid,
                    "title": title,
                    "preview": preview,
                    "endpoint": endpoint,
                    "suggestion_type": stype,
                    "personalization_score": round(boost, 2),
                }
            )

        personalized.sort(key=lambda x: x.get("personalization_score", 0), reverse=True)
        return personalized[:5]

    def _get_or_create_profile(self) -> UserProfile:
        if "default" not in self._profiles:
            self._profiles["default"] = UserProfile()
        return self._profiles["default"]
