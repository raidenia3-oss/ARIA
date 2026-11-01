"""Story Context Manager — orquesta CharacterBible, CanonTracker y ChapterPlanner.

Produce el system prompt enriquecido para inyección en /api/chat, permitiendo
respuestas "dentro de personaje" con coherencia canónica y cronológica.

Uso:
    manager = StoryContextManager()
    system_prompt = manager.build_system_prompt(
        work_id="mi_obra",
        character_id="protagonista",
        user_prompt="¿Qué haces ahora?",
    )
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("AURA.StoryMemory.Context")


class StoryContextManager:
    """Orquesta todos los componentes de la base literaria."""

    def __init__(self) -> None:
        from backend.story_memory.character_bible import CharacterBible
        from backend.story_memory.canon_tracker import CanonTracker
        from backend.story_memory.chapter_planner import ChapterPlanner

        self.character_bible = CharacterBible()
        self.canon_tracker = CanonTracker()
        self.chapter_planner = ChapterPlanner()

    def build_character_bible_block(self, work_id: str, char_id: str) -> str:
        """Construye el bloque de biblia de personaje para el system prompt."""
        char = self.character_bible.get(work_id, char_id)
        if not char:
            return ""
        prompt = self.character_bible.build_personality_prompt(work_id, char_id)
        return f"[BIBLIA DE PERSONAJE — {char.get('name', char_id)}]\n{prompt}"

    def build_canon_block(self, work_id: str) -> str:
        """Construye el bloque de contexto canónico."""
        return self.canon_tracker.build_canon_context(work_id)

    def build_chapter_block(self, work_id: str) -> str:
        """Construye el bloque de planificación de capítulos."""
        return self.chapter_planner.build_chapter_context(work_id)

    def build_world_block(self, work_id: str) -> str:
        """Construye el bloque de información de la obra/universo."""
        work = self.character_bible.storage.get_work(work_id)
        if not work:
            return ""
        parts: List[str] = ["[UNIVERSO / OBRA]"]
        parts.append(f"Título: {work.get('title', '')}")
        if work.get("universe"):
            parts.append(f"Universo: {work.get('universe', '')}")
        if work.get("description"):
            parts.append(f"Descripción: {work.get('description', '')}")
        if work.get("author"):
            parts.append(f"Autor: {work.get('author', '')}")
        return "\n".join(parts)

    def build_semantic_lore_block(
        self,
        work_id: str,
        query: str,
        top_k: int = 5,
        max_chars: int = 2000,
    ) -> str:
        """Bloque RAG local opcional (BLOQUE 41): recupera lore por similitud coseno.

        Retorna "" si el índice no existe o la búsqueda falla — nunca rompe el
        flujo de Jan / prompts existentes.
        """
        try:
            from backend.story_memory.vector_rag import get_vector_engine

            engine = get_vector_engine()
            return engine.inject_context(work_id, query, top_k=top_k, max_chars=max_chars)
        except Exception as exc:  # pragma: no cover - defensivo, 100% local
            logger.debug("RAG semántico no disponible para %s: %s", work_id, exc)
            return ""

    def build_system_prompt(
        self,
        work_id: str,
        character_id: str,
        base_prompt: str = "Eres AURA, un asistente de IA avanzado.",
        include_canon: bool = True,
        include_chapters: bool = True,
        semantic_query: Optional[str] = None,
        semantic_top_k: int = 5,
    ) -> str:
        """
        Construye el system prompt completo para chat dentro de personaje.

        Args:
            work_id: identificador de la obra
            character_id: identificador del personaje activo
            base_prompt: prompt base de AURA
            include_canon: incluir eventos canónicos
            include_chapters: incluir plan de capítulos

        Returns:
            System prompt enriquecido listo para pasar al LLM
        """
        parts: List[str] = [base_prompt]
        parts.append("Modo: narrativa dentro de personaje (Character Bible integrada).")

        world_block = self.build_world_block(work_id)
        if world_block:
            parts.append(world_block)

        char_block = self.build_character_bible_block(work_id, character_id)
        if char_block:
            parts.append(char_block)
            parts.append(
                "REGLA: Mantén la voz, personalidad, objetivos y conflictos del personaje. "
                "No rompas caracterización. Evita respuestas genéricas."
            )

        if include_canon:
            canon_block = self.build_canon_block(work_id)
            if canon_block:
                parts.append(canon_block)
                parts.append(
                    "REGLA: Respeta los eventos canónicos. No contradigas hechos establecidos."
                )

        if include_chapters:
            chapter_block = self.build_chapter_block(work_id)
            if chapter_block:
                parts.append(chapter_block)
                parts.append("REGLA: Avanza la trama según el plan de capítulos.")

        if semantic_query:
            lore_block = self.build_semantic_lore_block(
                work_id, semantic_query, top_k=semantic_top_k
            )
            if lore_block:
                parts.append(lore_block)
                parts.append(
                    "REGLA: Usa el contexto [LORE] recuperado como verdad del universo; "
                    "no lo contradigas."
                )

        return "\n\n".join(parts)

    def get_active_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Recupera el contexto literario activo de una sesión (si existe mapping)."""
        from backend.story_memory.session_context import get_session_context

        return get_session_context(session_id)

    def inject_story_context(
        self,
        session_id: str,
        prompt: str,
        enriched_prompt_template: str = "{context}\n\n{prompt}",
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Inyecta contexto narrativo en el prompt del usuario.

        Returns:
            (enriched_prompt, context_info)
        """
        ctx = self.get_active_context(session_id)
        if not ctx:
            return prompt, None

        work_id = ctx.get("work_id", "")
        character_id = ctx.get("character_id", "")
        if not work_id or not character_id:
            return prompt, ctx

        context_parts: List[str] = []

        world = self.build_world_block(work_id)
        if world:
            context_parts.append(world)

        char = self.build_character_bible_block(work_id, character_id)
        if char:
            context_parts.append(char)

        canon = self.build_canon_block(work_id)
        if canon:
            context_parts.append(canon)

        chapters = self.build_chapter_block(work_id)
        if chapters:
            context_parts.append(chapters)

        enriched = enriched_prompt_template.format(
            context="\n\n".join(context_parts),
            prompt=prompt,
        )
        return enriched, ctx
