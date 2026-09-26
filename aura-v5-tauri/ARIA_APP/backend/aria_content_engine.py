"""ARIA Content Engine — Integrates ContentGenerator with ARIA observer."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ContentSuggestion:
    suggestion_type: str
    content_sample: str
    full_generator_endpoint: str
    confidence: float = 0.0


@dataclass
class InteractiveStoryState:
    scene: str
    branches: List[str] = field(default_factory=list)
    history: List[str] = field(default_factory=list)


class AriaContentEngine:
    """Integrates ContentGenerator with ARIA observer for context-aware suggestions."""

    CONTENT_TYPES = {
        "anime": "story",
        "game": "character",
        "design": "world",
        "reading": "prompt",
        "programming": "world",
        "music": "prompt",
    }

    def __init__(self, ai_provider=None) -> None:
        try:
            from backend.generation.content_generator import (
                AnimePromptOptimizer,
                CharacterDesigner,
                ContentLibrary,
                StoryGenerator,
                WorldBuilder,
            )
        except Exception:
            from generation.content_generator import (
                AnimePromptOptimizer,
                CharacterDesigner,
                ContentLibrary,
                StoryGenerator,
                WorldBuilder,
            )
        self.story_gen = StoryGenerator(ai_provider)
        self.char_designer = CharacterDesigner()
        self.world_builder = WorldBuilder()
        self.prompt_opt = AnimePromptOptimizer()
        self.content_lib = ContentLibrary()
        self._active_stories: Dict[str, InteractiveStoryState] = {}

    async def suggest_content(self, user_context: dict) -> Dict[str, Any]:
        """ARIA observa qué hace y propone contenido."""
        activity = user_context.get("activity", "unknown")
        app = user_context.get("current_app", "unknown")
        searches = user_context.get("searches", [])
        interests = []
        for s in searches:
            q = s.get("query", "")
            if q:
                interests.append(q.lower())

        suggestion_type = "general"
        for key, stype in self.CONTENT_TYPES.items():
            for interest in interests:
                if key in interest.lower():
                    suggestion_type = stype
                    break
            if suggestion_type != "general":
                break

        if app and app != "unknown":
            app_lower = app.lower()
            if any(w in app_lower for w in ["anime", "cartoon", "demon", "slime", "sword"]):
                suggestion_type = "story"
            elif any(w in app_lower for w in ["editor", "code", "dev", "vscode"]):
                suggestion_type = "world"
            elif any(w in app_lower for w in ["browser", "search", "google"]):
                suggestion_type = "character"

        samples = {
            "story": "La leyenda del héroe que despertó en un mundo olvidado...",
            "character": "Nombre: Rin Shadowmere — Nombre: un vigía nocturno con habilidades de rastreo.",
            "world": "Mundo de Cristal — un continente flotante donde la magia es la gravedad.",
            "prompt": "fantasy warrior, dynamic pose, anime style, masterpiece, ultra detailed",
            "general": "Sugerencia: ¿Quieres crear una historia, personaje o mundo?",
        }

        confidence = 0.3 + len(interests) * 0.1
        if app != "unknown":
            confidence += 0.2
        confidence = min(confidence, 1.0)

        return {
            "suggestion_type": suggestion_type,
            "content_sample": samples.get(suggestion_type, samples["general"]),
            "full_generator_endpoint": f"/api/aria/generate/{suggestion_type}",
            "confidence": round(confidence, 2),
            "context_used": {
                "activity": activity,
                "app": app,
                "interests": interests[:5],
            },
        }

    async def generate_interactive_story(
        self, user_input: str, story_id: str = "default"
    ) -> Dict[str, Any]:
        """Genera continuación interactiva de historia."""
        if story_id not in self._active_stories:
            self._active_stories[story_id] = InteractiveStoryState(
                scene=user_input,
                history=[user_input],
            )
        state = self._active_stories[story_id]

        next_scene = f"Continuando desde: {user_input[:80]}... " + (
            "El protagonista evalúa sus opciones mientras el viento cambia. "
            "Cada decisión acerca al desenlace o aleja de él."
        )

        branches = [
            f"Avanzar hacia lo desconocido — {state.scene[:40]}...",
            f"Buscar aliados en la aldea cercana",
            f"Investigar el objeto misterioso que apareció",
            f"Retirarse y planificar una estrategia diferente",
        ]

        state.scene = next_scene
        state.branches = branches
        state.history.append(next_scene)

        return {
            "next_scene": next_scene,
            "branches": branches,
            "story_id": story_id,
            "history_length": len(state.history),
        }

    async def personalize_content(self, content: str, user_profile: dict) -> str:
        """Ajusta contenido al estilo del usuario."""
        preferences = user_profile.get("preferences", {})
        style = preferences.get("response_style", "balanced")
        interests = user_profile.get("interests", [])

        personalized = content
        if style == "detailed":
            if len(personalized) < 300:
                personalized += " Detalle adicional: profundiza en los motivos internos del personaje y cómo su trauma influye en cada decisión."
        elif style == "concise":
            if len(personalized) > 200:
                idx = personalized.find(". ")
                if idx > 0:
                    personalized = personalized[: idx + 1]

        if interests:
            topic = interests[0]
            if topic.lower() not in personalized.lower():
                personalized += f" Considerando el interés en '{topic}', el contexto se enriquece con elementos temáticos relevantes."

        return personalized

    async def generate_from_context(
        self, context: dict, content_type: str = None
    ) -> Dict[str, Any]:
        """Genera contenido basado en contexto ARIA completo."""
        suggestion = await self.suggest_content(context)
        ctype = content_type or suggestion["suggestion_type"]

        if ctype == "story":
            result = await self.story_gen.generate_story(
                f"Historia basada en contexto: {context.get('current_app', 'aventura')}",
                length="medium",
                context=context,
            )
        elif ctype == "character":
            result = await self.char_designer.design_character(
                role="hero", traits=["mysterious", "strong"]
            )
        elif ctype == "world":
            result = await self.world_builder.build_world("fantasy", "medium")
        else:
            result = {"content": suggestion["content_sample"]}

        saved = self.content_lib.save(
            type_=ctype,
            content_text=json.dumps(result)[:500],
            metadata={"context": context, "suggestion_confidence": suggestion["confidence"]},
            context=json.dumps(context),
        )
        result["saved_id"] = saved
        return result
