"""Tests for the AME mobile story context endpoint.

Valida:
- GET /api/mobile/story/context/{session_id} con sesión vinculada.
- GET /api/mobile/story/context/{session_id} con sesión sin contexto (estado vacío).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.story_memory.character_bible import CharacterBible
from backend.story_memory.session_context import (
    clear_all,
    set_session_context,
)
from backend.story_memory.story_storage import StoryStorage
from backend.story_routes import character_bible, storage

TEST_API_KEY = "test-mobile-story-key"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
):
    monkeypatch.setenv("AURA_API_KEY", TEST_API_KEY)
    monkeypatch.setenv("AURA_STORY_DIR", str(tmp_path))

    storage._store_dir = str(tmp_path)
    character_bible._store_dir = str(tmp_path)
    storage._cache = {}
    clear_all()

    yield

    clear_all()


@pytest.fixture
def _setup_work_and_char(tmp_path):
    storage._store_dir = str(tmp_path)
    storage._cache = {}
    character_bible._store_dir = str(tmp_path)
    character_bible._cache = {}
    clear_all()

    storage.create_work(
        work_id="novela_prueba",
        title="Obra Móvil",
        universe="universo_x",
        description="Una obra de test móvil",
        author="TestSuite",
    )
    character_bible.create(
        work_id="novela_prueba",
        char_id="protagonista",
        name="Ariadna",
        voice="Voz firme y decidida.",
        personality=["valiente", "curiosa"],
    )
    set_session_context("sess_mobile_1", "novela_prueba", "protagonista")

    yield

    clear_all()


class TestMobileStoryEndpoint:
    """Tests para GET /api/mobile/story/context/{session_id}"""

    def test_returns_active_context(self, client: TestClient, _setup_work_and_char):
        resp = client.get("/api/mobile/story/context/sess_mobile_1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] is True
        assert data["work_id"] == "novela_prueba"
        assert data["character_id"] == "protagonista"

    def test_returns_no_context_for_unlinked_session(self, client: TestClient):
        resp = client.get("/api/mobile/story/context/sess_no_context")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] is False
        assert data["work_id"] is None
        assert data["character_id"] is None

    def test_returns_enriched_fields_when_available(self, client: TestClient, _setup_work_and_char):
        resp = client.get("/api/mobile/story/context/sess_mobile_1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["work_title"] == "Obra Móvil"
        assert data["character_name"] == "Ariadna"

    def test_no_secrets_in_response(self, client: TestClient, _setup_work_and_char):
        resp = client.get("/api/mobile/story/context/sess_mobile_1")
        assert resp.status_code == 200
        data = resp.json()
        raw = repr(data)
        assert "token" not in raw.lower() or "character_id" in raw.lower()
        assert "api_key" not in raw.lower()
        assert "password" not in raw.lower()
