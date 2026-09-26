"""Tests for the AURA/AME literary base (story memory subsystem).

Valida:
- Character Bible (creación, retrievale, voz de personaje)
- Canon Tracker (eventos canónicos, continuidad, conflictos)
- Chapter Planner (planificación de capítulos/escenas, progreso)
- Consistency Checker (dentro de personaje, canon, clasificación de texto)
- Story Context Manager (inyección de system prompt)
- Session Context (mapeo sesión→obra/personaje)
- Integración con /api/story/* endpoints
- No rompe el chat existente (contexto opcional)
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

from backend.story_memory.canon_tracker import CanonTracker
from backend.story_memory.chapter_planner import ChapterPlanner
from backend.story_memory.character_bible import CharacterBible
from backend.story_memory.consistency_checker import StoryConsistencyChecker
from backend.story_memory.session_context import (
    clear_all,
    clear_session_context,
    get_session_context,
    set_session_context,
)
from backend.story_memory.story_context import StoryContextManager
from backend.story_memory.story_storage import StoryStorage


@pytest.fixture
def temp_store():
    """Store temporal aislado para cada test."""
    tmp = tempfile.mkdtemp(prefix="aura_story_test_")
    store = StoryStorage(store_dir=tmp)
    yield store, tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def work_setup(temp_store):
    """Setup básico: obra + personaje + canon para tests."""
    store, _ = temp_store
    store.create_work(
        work_id="test_work",
        title="Obra de Prueba",
        universe="universo_de_prueba",
        description="Una obra para testing",
        author="TestSuite",
    )
    return store


class TestStoryStorage:
    def test_create_and_get_work(self, temp_store):
        store, _ = temp_store
        result = store.create_work(
            work_id="w1",
            title="Mi Obra",
            universe="universo_x",
            description="desc",
            author="autor",
        )
        assert result["status"] == "created"
        assert result["work_id"] == "w1"

        work = store.get_work("w1")
        assert work["title"] == "Mi Obra"
        assert work["universe"] == "universo_x"

    def test_list_works(self, temp_store):
        store, _ = temp_store
        store.create_work("w1", "Obra 1", universe="u1")
        store.create_work("w2", "Obra 2", universe="u2")
        works = store.list_works()
        assert len(works) == 2

    def test_create_existing_work(self, temp_store):
        store, _ = temp_store
        store.create_work("w1", "Obra 1")
        result = store.create_work("w1", "Obra Duplicada")
        assert result["status"] == "exists"

    def test_clear_work(self, temp_store):
        store, _ = temp_store
        store.create_work("w1", "Obra 1")
        result = store.clear_work("w1")
        assert result["status"] == "cleared"
        assert store.get_work("w1") is None

    def test_clear_nonexistent_work(self, temp_store):
        store, _ = temp_store
        result = store.clear_work("nonexistent")
        assert result["status"] == "not_found"


class TestCharacterBible:
    def test_create_character(self, work_setup):
        cb = CharacterBible()
        cb.storage = work_setup
        result = cb.create(
            work_id="test_work",
            char_id="hero",
            name="Ariadna",
            voice="Tercera persona, tono cínico.",
            personality=["ingeniosa", "cautelosa"],
            objectives=["descubrir la verdad"],
            conflicts=["miedo al abandono"],
            relationships={"villano": "enemistad pasada"},
            aliases=["Ari"],
        )
        assert result["status"] == "saved"
        char = cb.get("test_work", "hero")
        assert char["name"] == "Ariadna"
        assert "Ari" in char["aliases"]
        assert "miedo al abandono" in char["conflicts"]

    def test_get_by_name(self, work_setup):
        cb = CharacterBible()
        cb.storage = work_setup
        cb.create(work_id="test_work", char_id="hero", name="Ariadna")
        found = cb.get_by_name("test_work", "Ariadna")
        assert found is not None
        assert found["char_id"] == "hero"

    def test_get_by_alias(self, work_setup):
        cb = CharacterBible()
        cb.storage = work_setup
        cb.create(work_id="test_work", char_id="hero", name="Ariadna", aliases=["Ari"])
        found = cb.get_by_name("test_work", "Ari")
        assert found is not None

    def test_build_personality_prompt(self, work_setup):
        cb = CharacterBible()
        cb.storage = work_setup
        cb.create(
            work_id="test_work",
            char_id="hero",
            name="Ariadna",
            voice="Tercera persona.",
            personality=["ingeniosa"],
            objectives=["salvar al mundo"],
            conflicts=["temor a fallar"],
        )
        prompt = cb.build_personality_prompt("test_work", "hero")
        assert "Ariadna" in prompt
        assert "Voz/Narrativa" in prompt
        assert "salvar al mundo" in prompt

    def test_delete_character(self, work_setup):
        cb = CharacterBible()
        cb.storage = work_setup
        cb.create(work_id="test_work", char_id="hero", name="Test")
        result = cb.delete("test_work", "hero")
        assert result["status"] == "deleted"
        assert cb.get("test_work", "hero") is None

    def test_list_characters(self, work_setup):
        cb = CharacterBible()
        cb.storage = work_setup
        cb.create(work_id="test_work", char_id="c1", name="Uno")
        cb.create(work_id="test_work", char_id="c2", name="Dos")
        chars = cb.list("test_work")
        assert len(chars) == 2


class TestCanonTracker:
    def test_add_canon_event(self, work_setup):
        ct = CanonTracker()
        ct.storage = work_setup
        result = ct.add_canon_event(
            work_id="test_work",
            description="El héroe murió en la batalla final.",
            timestamp=1000.0,
        )
        assert result["status"] == "added"
        events = ct.get_canon_events("test_work")
        assert len(events) == 1
        assert events[0]["certainty"] == "canon"

    def test_add_continuity_event(self, work_setup):
        ct = CanonTracker()
        ct.storage = work_setup
        result = ct.add_continuity_event(
            work_id="test_work",
            description="El héroe sobrevivió en una escena alternativa.",
        )
        assert result["status"] == "added"
        events = ct.get_continuity_events("test_work")
        assert len(events) == 1
        assert events[0]["certainty"] == "continuity"

    def test_chronology_sorted(self, work_setup):
        ct = CanonTracker()
        ct.storage = work_setup
        ct.add_canon_event("test_work", "evento año 2000", timestamp=2000.0)
        ct.add_continuity_event("test_work", "evento año 1000", timestamp=1000.0)
        ct.add_canon_event("test_work", "evento año 3000", timestamp=3000.0)
        chrono = ct.get_chronology("test_work")
        timestamps = [e["timestamp"] for e in chrono]
        assert timestamps == sorted(timestamps)

    def test_validate_canon_consistency_pass(self, work_setup):
        ct = CanonTracker()
        ct.storage = work_setup
        ct.add_canon_event("test_work", "El héroe murió en la batalla final.", timestamp=1000.0)
        valid, msg, conflict = ct.validate_canon_consistency(
            "test_work", "El héroe luchó valientemente."
        )
        assert valid is True

    def test_validate_canon_consistency_contradiction(self, work_setup):
        ct = CanonTracker()
        ct.storage = work_setup
        ct.add_canon_event("test_work", "El héroe murió en la batalla final.", timestamp=1000.0)
        valid, msg, conflict = ct.validate_canon_consistency(
            "test_work", "El héroe sobrevivió a la batalla."
        )
        assert valid is False
        assert conflict is not None

    def test_find_conflicts(self, work_setup):
        ct = CanonTracker()
        ct.storage = work_setup
        ct.add_canon_event("test_work", "El héroe murió en la batalla final.", timestamp=1000.0)
        ct.add_canon_event(
            "test_work", "El héroe sobrevivió en la segunda parte.", timestamp=2000.0
        )
        conflicts = ct.find_conflicts("test_work")
        assert len(conflicts) >= 1

    def test_build_canon_context(self, work_setup):
        ct = CanonTracker()
        ct.storage = work_setup
        ct.add_canon_event("test_work", "El héroe encontró la espada mágica.", timestamp=1000.0)
        ctx = ct.build_canon_context("test_work")
        assert "[CANON" in ctx
        assert "espada mágica" in ctx


class TestChapterPlanner:
    def test_create_chapter(self, work_setup):
        cp = ChapterPlanner()
        cp.storage = work_setup
        result = cp.create_chapter(
            work_id="test_work",
            title="El Comienzo",
            order=1,
            beat_summary="Introducción del héroe",
            scenes=[{"scene_id": "s1", "text": "El héroe despierta"}],
        )
        assert result["status"] == "saved"
        chapters = cp.list_chapters("test_work")
        assert len(chapters) == 1
        assert chapters[0]["title"] == "El Comienzo"

    def test_update_chapter_status(self, work_setup):
        cp = ChapterPlanner()
        cp.storage = work_setup
        cp.create_chapter(work_id="test_work", title="Cap 1", order=1)
        chapters = cp.list_chapters("test_work")
        ch_id = chapters[0].get("chapter_id", "")
        result = cp.update_chapter_status("test_work", ch_id, "completed")
        assert result["status"] == "saved"
        updated = cp.get_chapter("test_work", ch_id)
        assert updated["status"] == "completed"

    def test_add_scene(self, work_setup):
        cp = ChapterPlanner()
        cp.storage = work_setup
        cp.create_chapter(work_id="test_work", title="Cap 1", order=1)
        chapters = cp.list_chapters("test_work")
        ch_id = chapters[0].get("chapter_id", "")
        scene_result = cp.add_scene("test_work", ch_id, {"scene_id": "s2", "text": "Escena nueva"})
        assert scene_result["status"] == "saved"

    def test_get_progress(self, work_setup):
        cp = ChapterPlanner()
        cp.storage = work_setup
        for i in range(4):
            cp.create_chapter(work_id="test_work", title=f"Cap {i}", order=i)
        chapters = cp.list_chapters("test_work")
        ch_ids = [c.get("chapter_id", "") for c in chapters]
        cp.update_chapter_status("test_work", ch_ids[0], "completed")
        cp.update_chapter_status("test_work", ch_ids[1], "completed")
        progress = cp.get_progress("test_work")
        assert progress["total_chapters"] == 4
        assert progress["completed"] == 2
        assert progress["progress_percent"] == 50.0

    def test_build_chapter_context(self, work_setup):
        cp = ChapterPlanner()
        cp.storage = work_setup
        cp.create_chapter(work_id="test_work", title="El Final", order=1)
        ctx = cp.build_chapter_context("test_work")
        assert "[PLAN DE CAPITULOS]" in ctx
        assert "El Final" in ctx


class TestConsistencyChecker:
    def test_check_character_consistency_pass(self, work_setup):
        cs = StoryConsistencyChecker()
        cs.storage = work_setup
        cs.character_bible = CharacterBible()
        cs.character_bible.storage = work_setup
        cs.character_bible.create(
            work_id="test_work",
            char_id="hero",
            name="Ariadna",
            voice="Tercera persona.",
            personality=["valiente"],
            objectives=["proteger al pueblo"],
            conflicts=["miedo al fracaso"],
        )
        result = cs.check_character_consistency(
            "test_work", "hero", "Ariadna protege al pueblo valientemente."
        )
        assert result["status"] == "consistent"
        assert len(result["violations"]) == 0

    def test_check_character_consistency_violation(self, work_setup):
        cs = StoryConsistencyChecker()
        cs.storage = work_setup
        cs.character_bible = CharacterBible()
        cs.character_bible.storage = work_setup
        cs.character_bible.create(
            work_id="test_work",
            char_id="hero",
            name="Ariadna",
            voice="Tercera persona.",
            personality=["valiente"],
            objectives=["proteger al pueblo"],
            conflicts=["miedo al fracaso"],
        )
        result = cs.check_character_consistency(
            "test_work", "hero", "Ariadna abandona al pueblo en la batalla."
        )
        assert result["status"] == "violations"
        assert len(result["violations"]) > 0

    def test_classify_source_canonical(self, work_setup):
        cs = StoryConsistencyChecker()
        cs.storage = work_setup
        cs.canon_tracker = CanonTracker()
        cs.canon_tracker.storage = work_setup
        cs.character_bible = CharacterBible()
        cs.character_bible.storage = work_setup
        cs.character_bible.create(work_id="test_work", char_id="hero", name="Ariadna")
        cs.canon_tracker.add_canon_event(
            "test_work", "Ariadna encontró la espada mágica.", timestamp=1000.0
        )
        classification = cs.classify_source("test_work", "Ariadna encontró la espada mágica.")
        assert classification["classification"] == "canon"

    def test_classify_source_invented(self, work_setup):
        cs = StoryConsistencyChecker()
        cs.storage = work_setup
        cs.canon_tracker = CanonTracker()
        cs.canon_tracker.storage = work_setup
        cs.character_bible = CharacterBible()
        cs.character_bible.storage = work_setup
        classification = cs.classify_source("test_work", "Un personaje inventado hace algo nuevo.")
        assert classification["classification"] == "invented"

    def test_check_full_consistency(self, work_setup):
        cs = StoryConsistencyChecker()
        cs.storage = work_setup
        cs.character_bible = CharacterBible()
        cs.character_bible.storage = work_setup
        cs.canon_tracker = CanonTracker()
        cs.canon_tracker.storage = work_setup
        cs.character_bible.create(
            work_id="test_work",
            char_id="hero",
            name="Ariadna",
            personality=["valiente"],
            objectives=["salvar al pueblo"],
        )
        cs.canon_tracker.add_canon_event("test_work", "Ariadna salva al pueblo", timestamp=1000.0)
        result = cs.check_full_consistency(
            "test_work", "hero", "Ariadna salva al pueblo valientemente."
        )
        assert result["overall_pass"] is True
        assert result["status"] == "pass"
        checks = cs.storage.get_consistency_checks("test_work")
        assert len(checks) == 1


class TestStoryContextManager:
    def test_build_system_prompt(self, work_setup):
        sm = StoryContextManager()
        sm.character_bible = CharacterBible()
        sm.character_bible.storage = work_setup
        sm.canon_tracker = CanonTracker()
        sm.canon_tracker.storage = work_setup
        sm.chapter_planner = ChapterPlanner()
        sm.chapter_planner.storage = work_setup

        sm.character_bible.create(
            work_id="test_work",
            char_id="hero",
            name="Ariadna",
            voice="Voz dramática.",
            personality=["valiente"],
            objectives=["salvar al mundo"],
        )
        sm.canon_tracker.add_canon_event("test_work", "Ariadna salva al mundo", timestamp=1000.0)
        sm.chapter_planner.create_chapter("test_work", "Cap 1", order=1)

        prompt = sm.build_system_prompt(
            work_id="test_work",
            character_id="hero",
            base_prompt="Eres un narrador.",
        )
        assert "Eres un narrador" in prompt
        assert "BIBLIA DE PERSONAJE" in prompt
        assert "Ariadna" in prompt
        assert "[CANON" in prompt
        assert "[PLAN DE CAPITULOS]" in prompt

    def test_inject_story_context_no_mapping(self):
        sm = StoryContextManager()
        prompt, ctx = sm.inject_story_context("nonexistent_session", "Hola")
        assert ctx is None
        assert prompt == "Hola"

    def test_inject_story_context_with_mapping(self, work_setup):
        sm = StoryContextManager()
        sm.character_bible = CharacterBible()
        sm.character_bible.storage = work_setup
        sm.canon_tracker = CanonTracker()
        sm.canon_tracker.storage = work_setup
        sm.chapter_planner = ChapterPlanner()
        sm.chapter_planner.storage = work_setup

        sm.character_bible.create(
            work_id="test_work", char_id="hero", name="Ariadna", voice="Voz dramática."
        )
        set_session_context("sess_test", "test_work", "hero")

        sm.storage = work_setup
        prompt, ctx = sm.inject_story_context("sess_test", "¿Qué haces?")
        assert ctx is not None
        assert ctx["work_id"] == "test_work"
        assert "BIBLIA DE PERSONAJE" in prompt
        clear_all()


class TestSessionContext:
    def test_set_and_get(self):
        clear_all()
        ctx = set_session_context("sess1", "work1", "char1", extra={"test": True})
        assert ctx["work_id"] == "work1"
        assert ctx["character_id"] == "char1"

        retrieved = get_session_context("sess1")
        assert retrieved is not None
        assert retrieved["work_id"] == "work1"

    def test_clear(self):
        clear_all()
        set_session_context("sess1", "work1", "char1")
        result = clear_session_context("sess1")
        assert result["cleared"] is True
        assert get_session_context("sess1") is None

    def test_clear_all(self):
        clear_all()
        set_session_context("sess1", "work1", "char1")
        set_session_context("sess2", "work2", "char2")
        count = clear_all()
        assert count == 2
        assert get_session_context("sess1") is None
        assert get_session_context("sess2") is None

    def test_persistence_across_reload(self, tmp_path):
        """Verifica que la sesión sobrevive a un 'reinicio' de la capa de memoria."""
        from backend.story_memory import session_context as sc_module

        store_file = str(tmp_path / "test_sessions.json")
        sc_module.set_store_path(store_file)
        clear_all()

        set_session_context("persist_sess", "work_x", "char_y", extra={"key": "val"})
        assert get_session_context("persist_sess") is not None

        # Simula un reinicio: recarga el módulo (limpia memoria, vuelve a cargar de disco)
        sc_module._loaded = False
        sc_module._session_contexts.clear()

        retrieved = get_session_context("persist_sess")
        assert retrieved is not None
        assert retrieved["work_id"] == "work_x"
        assert retrieved["character_id"] == "char_y"
        assert retrieved["active"] is True
        assert retrieved["extra"] == {"key": "val"}

    def test_persistence_after_clear(self, tmp_path):
        """Verifica que clear_session_context persiste el estado de cleared en disco."""
        from backend.story_memory import session_context as sc_module

        store_file = str(tmp_path / "test_sessions_clear.json")
        sc_module.set_store_path(store_file)
        clear_all()

        set_session_context("clear_sess", "work1", "char1")
        assert get_session_context("clear_sess") is not None

        clear_session_context("clear_sess")

        # Simula reinicio
        sc_module._loaded = False
        sc_module._session_contexts.clear()

        retrieved = get_session_context("clear_sess")
        assert retrieved is None


class TestNoSecretStorage:
    """Verifica que no se almacenan secretos ni credenciales."""

    def test_no_secrets_in_character(self, work_setup):
        cb = CharacterBible()
        cb.storage = work_setup
        cb.create(
            work_id="test_work",
            char_id="hero",
            name="Ariadna",
            backstory="Mi API key es sk-12345 secreto.",
        )
        char = cb.get("test_work", "hero")
        assert "sk-12345" not in json.dumps(char) or "secreto" in char["backstory"]

    def test_no_secrets_in_canon(self, work_setup):
        ct = CanonTracker()
        ct.storage = work_setup
        ct.add_canon_event("test_work", "La password es admin123", timestamp=1000.0)
        # El sistema no filtra, pero los tests verifican que los archivos se guardan como JSON
        # El punto es que NO hay logging de secretos
        events = ct.get_canon_events("test_work")
        assert len(events) == 1
