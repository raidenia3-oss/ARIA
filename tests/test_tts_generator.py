"""Tests Bloque 46 - Local TTS Voice Narration Engine.

Valida:
- Síntesis de texto a audio (WAV) con motores disponibles.
- Fallback chain: Piper > Kokoro > pyttsx3 > gTTS > fallback.
- Character voice mapping via Character Bible.
- Endpoints REST /api/audio/tts/*.
- Limpieza de archivos temporales.
"""

from __future__ import annotations

import asyncio
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.audio.tts_generator import (
    LocalTTSEngine,
    TTSGenerator,
    VoiceProfile,
    get_tts_generator,
    reset_tts_generator,
)
from backend.story_memory.character_bible import CharacterBible
from backend.story_memory.story_storage import StoryStorage


@pytest.fixture
def temp_story_dir(tmp_path, monkeypatch):
    story_dir = str(tmp_path / "story_memory")
    os.makedirs(story_dir, exist_ok=True)
    monkeypatch.setenv("AURA_STORY_DIR", story_dir)
    monkeypatch.setenv("AURA_TTS_TMP_DIR", str(tmp_path / "tts_output"))
    monkeypatch.setenv("AURA_TTS_ENGINE", "fallback")  # Forzar fallback para tests
    return story_dir


@pytest.fixture
def tts(temp_story_dir):
    reset_tts_generator()
    g = get_tts_generator(store_dir=temp_story_dir)
    yield g
    reset_tts_generator()


@pytest.fixture
def work_with_chars(temp_story_dir):
    storage = StoryStorage(store_dir=temp_story_dir)
    storage.create_work(
        work_id="tts_w", title="Obra TTS", universe="U", description="d", author="t"
    )
    cb = CharacterBible()
    cb.create(work_id="tts_w", char_id="hero", name="Aldric", voice="voz_heroica")
    cb.create(work_id="tts_w", char_id="villain", name="Malakar", voice="voz_oscura")
    return temp_story_dir


def test_engine_fallback_available():
    """El motor fallback siempre debe estar disponible si numpy+soundfile."""
    engine = LocalTTSEngine(engine="fallback")
    assert engine.available is True
    assert engine.backend_name == "fallback"


def test_synthesize_basic(tts):
    result = tts.synthesize_text("Hola mundo", work_id="w1")
    assert result.audio_path.endswith(".wav")
    assert result.duration_sec > 0
    assert result.sample_rate == 22050
    assert result.engine == "fallback"
    assert result.text_chars == 10


def test_synthesize_empty_text_raises(tts):
    with pytest.raises(ValueError):
        tts.synthesize_text("")


def test_synthesize_with_voice_override(tts):
    result = tts.synthesize_text("Test", voice_id="custom_voice")
    assert result.voice_id == "custom_voice"


def test_synthesize_chapter_returns_multiple(tts):
    chapter = "Párrafo uno.\n\nPárrafo dos.\n\nPárrafo tres."
    results = tts.synthesize_chapter("w1", chapter)
    assert len(results) == 3
    for r in results:
        assert r.audio_path.endswith(".wav")


def test_voice_profile_mapping(tts):
    vp = VoiceProfile(
        voice_id="custom_voice",
        name="Narrador",
        language="es",
        gender="male",
        style="dramatic",
        speed=1.2,
    )
    tts.set_voice_profile("w1", "hero", vp)
    profile = tts.get_voice_profile("w1", "hero")
    assert profile is not None
    assert profile.voice_id == "custom_voice"
    assert profile.speed == 1.2


def test_character_voice_mapping_from_bible(tts, work_with_chars):
    reset_tts_generator()
    g = get_tts_generator(store_dir=work_with_chars)
    g._load_character_voices("tts_w")
    hero_vp = g.get_voice_profile("tts_w", "hero")
    assert hero_vp is not None
    assert hero_vp.voice_id == "voz_heroica"
    villain_vp = g.get_voice_profile("tts_w", "villain")
    assert villain_vp is not None
    assert villain_vp.voice_id == "voz_oscura"
    reset_tts_generator()


def test_cleanup_removes_old_files(tts, tmp_path):
    tts.synthesize_text("Test 1")
    tts.synthesize_text("Test 2")
    import time

    time.sleep(0.1)
    # Simular archivos antiguos
    old_file = tts.tts_engine.tmp_dir / "tts_old.wav"
    old_file.write_bytes(b"fake")
    import os

    os.utime(old_file, (time.time() - 4000, time.time() - 4000))
    removed = tts.cleanup(max_age_secs=3600)
    assert removed >= 1
    assert not old_file.exists()


def test_status_returns_info(tts):
    status = tts.status()
    assert status["status"] == "ok"
    assert "engine" in status
    assert "available" in status
    assert "sample_rate" in status


def test_list_voices(tts):
    voices = tts.tts_engine.list_voices()
    assert isinstance(voices, dict)


# --- REST endpoints tests ---


def _rest_setup(monkeypatch, tmp_path):
    from backend.audio import tts_routes as tr
    from backend.audio.tts_routes import router

    story_dir = str(tmp_path / "story")
    os.makedirs(story_dir, exist_ok=True)
    monkeypatch.setenv("AURA_STORY_DIR", story_dir)
    monkeypatch.setenv("AURA_TTS_TMP_DIR", str(tmp_path / "tts_output"))
    monkeypatch.setenv("AURA_TTS_ENGINE", "fallback")
    reset_tts_generator()
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    yield client
    reset_tts_generator()


def test_rest_status(monkeypatch, tmp_path):
    for client in _rest_setup(monkeypatch, tmp_path):
        r = client.get("/api/audio/tts/status")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        assert "engine" in r.json()


def test_rest_voices(monkeypatch, tmp_path):
    for client in _rest_setup(monkeypatch, tmp_path):
        r = client.get("/api/audio/tts/voices")
        assert r.status_code == 200
        assert "backend" in r.json()
        assert "voices" in r.json()


def test_rest_synthesize(monkeypatch, tmp_path):
    for client in _rest_setup(monkeypatch, tmp_path):
        r = client.post("/api/audio/tts/synthesize", json={"text": "Hola TTS"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "audio_url" in data
        assert data["duration_sec"] > 0


def test_rest_synthesize_empty_fails(monkeypatch, tmp_path):
    for client in _rest_setup(monkeypatch, tmp_path):
        r = client.post("/api/audio/tts/synthesize", json={"text": ""})
        assert r.status_code == 422


def test_rest_synthesize_chapter(monkeypatch, tmp_path):
    for client in _rest_setup(monkeypatch, tmp_path):
        r = client.post(
            "/api/audio/tts/synthesize/chapter",
            json={"text": "Capítulo 1.\n\nCapítulo 2.", "work_id": "w1"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["count"] == 2
        assert len(data["segments"]) == 2


def test_rest_file_download(monkeypatch, tmp_path):
    for client in _rest_setup(monkeypatch, tmp_path):
        r = client.post("/api/audio/tts/synthesize", json={"text": "Descarga test"})
        assert r.status_code == 200
        audio_url = r.json()["audio_url"]
        filename = audio_url.split("/")[-1]
        d = client.get(f"/api/audio/tts/file/{filename}")
        assert d.status_code == 200
        assert d.headers["content-type"] == "audio/wav"


def test_rest_voice_map_set_get(monkeypatch, tmp_path):
    for client in _rest_setup(monkeypatch, tmp_path):
        r = client.post(
            "/api/audio/tts/voice-map",
            params={"work_id": "w1", "char_id": "hero"},
            json={
                "voice_id": "es_ES",
                "name": "Hero Voice",
                "language": "es",
                "gender": "male",
                "style": "heroic",
                "speed": 1.1,
                "pitch": 1.0,
                "volume": 1.0,
            },
        )
        assert r.status_code == 200
        assert r.json()["voice_id"] == "es_ES"
        g = client.get("/api/audio/tts/voice-map/w1/hero")
        assert g.status_code == 200
        assert g.json()["voice_id"] == "es_ES"
        assert g.json()["style"] == "heroic"
