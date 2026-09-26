"""Tests Bloque 46 - Local TTS Voice Narration Engine.

Valida (100% offline, stdlib+wave):
- Sintesis texto -> WAV valido (RIFF/WAVE, PCM 16-bit mono 22050 Hz).
- Texto mas largo => audio mas largo; determinismo por backend.
- Character Voice Mapping (perfiles por personaje en TTSGenerator).
- Endpoints REST /api/audio/tts/* (status, voices, synthesize, chapter, file).
- Sin dependencias cloud; sin regresion STT.
"""

from __future__ import annotations

import io
import wave
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.audio.tts_generator import (
    LocalTTSEngine,
    TTSGenerator,
    VoiceProfile,
    reset_tts_generator,
)
from backend.audio.tts_routes import router as tts_router


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_TTS_TMP_DIR", str(tmp_path / "tts"))
    monkeypatch.setenv("AURA_TTS_ENGINE", "fallback")
    return LocalTTSEngine(engine="fallback", tmp_dir=str(tmp_path / "tts"))


@pytest.fixture
def gen(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_TTS_TMP_DIR", str(tmp_path / "tts"))
    monkeypatch.setenv("AURA_TTS_ENGINE", "fallback")
    reset_tts_generator()
    g = TTSGenerator(engine=LocalTTSEngine(engine="fallback", tmp_dir=str(tmp_path / "tts")))
    yield g
    reset_tts_generator()


def _wav_info(raw: bytes):
    with wave.open(io.BytesIO(raw), "rb") as w:
        return {
            "channels": w.getnchannels(),
            "width": w.getsampwidth(),
            "rate": w.getframerate(),
            "frames": w.getnframes(),
            "duration": w.getnframes() / float(w.getframerate()),
        }


def test_fallback_backend_available(engine):
    assert engine.backend_name == "fallback"
    assert engine.available is True
    st = engine.status()
    assert st["available"] is True
    assert st["supported_backends"]["fallback"] is True


def test_wav_header_and_format(engine):
    res = engine.synthesize("Hola mundo")
    raw = Path(res.audio_path).read_bytes()
    assert raw[:4] == b"RIFF"
    assert raw[8:12] == b"WAVE"
    info = _wav_info(raw)
    assert info["channels"] == 1
    assert info["width"] == 2
    assert info["rate"] == 22050
    assert info["frames"] > 1000
    assert info["duration"] > 0.3
    assert res.format == "wav"
    assert res.text_chars == len("Hola mundo")


def test_deterministic_same_text(engine):
    a = Path(engine.synthesize("El heroe cruza el puente").audio_path).read_bytes()
    b = Path(engine.synthesize("El heroe cruza el puente").audio_path).read_bytes()
    assert a == b


def test_longer_text_longer_audio(engine):
    s = _wav_info(Path(engine.synthesize("Hola").audio_path).read_bytes())["frames"]
    lg = _wav_info(Path(engine.synthesize("Hola mundo cruel").audio_path).read_bytes())["frames"]
    assert lg > s


def test_empty_rejected(engine):
    with pytest.raises(ValueError):
        engine.synthesize("   ")


def test_voice_mapping_roundtrip(gen):
    gen.set_voice_profile("w1", "hero", VoiceProfile(voice_id="es_ES", name="Heroe"))
    vp = gen.get_voice_profile("w1", "hero")
    assert vp is not None and vp.voice_id == "es_ES"
    res = gen.synthesize_text("A la batalla", work_id="w1", char_id="hero")
    assert res.voice_id == "es_ES"
    assert Path(res.audio_path).exists()


def test_chapter_paragraphs(gen):
    results = gen.synthesize_chapter("w1", "Primer parrafo.\n\nSegundo parrafo.")
    assert len(results) == 2
    assert all(Path(r.audio_path).exists() for r in results)


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_TTS_TMP_DIR", str(tmp_path / "tts"))
    monkeypatch.setenv("AURA_TTS_ENGINE", "fallback")
    reset_tts_generator()
    app = FastAPI()
    app.include_router(tts_router)
    client = TestClient(app)
    yield client
    reset_tts_generator()


def test_rest_status_and_voices(tmp_path, monkeypatch):
    for client in _client(tmp_path, monkeypatch):
        s = client.get("/api/audio/tts/status")
        assert s.status_code == 200
        assert s.json()["available"] is True
        v = client.get("/api/audio/tts/voices")
        assert v.status_code == 200
        assert v.json()["status"] == "ok"


def test_rest_synthesize_and_file(tmp_path, monkeypatch):
    for client in _client(tmp_path, monkeypatch):
        r = client.post("/api/audio/tts/synthesize", json={"text": "Hola AME"})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["format"] == "wav"
        fname = Path(body["audio_url"]).name
        f = client.get(f"/api/audio/tts/file/{fname}")
        assert f.status_code == 200
        assert f.headers["content-type"] == "audio/wav"
        assert f.content[:4] == b"RIFF"


def test_rest_validation(tmp_path, monkeypatch):
    for client in _client(tmp_path, monkeypatch):
        assert client.post("/api/audio/tts/synthesize", json={"text": ""}).status_code == 422
        assert client.get("/api/audio/tts/file/nope.wav").status_code == 404


def test_rest_chapter_and_voicemap(tmp_path, monkeypatch):
    for client in _client(tmp_path, monkeypatch):
        m = client.post(
            "/api/audio/tts/voice-map",
            params={"work_id": "w1", "char_id": "hero"},
            json={"voice_id": "es_ES", "name": "Heroe"},
        )
        assert m.status_code == 200
        g = client.get("/api/audio/tts/voice-map/w1/hero")
        assert g.status_code == 200
        assert g.json()["voice_id"] == "es_ES"
        ch = client.post(
            "/api/audio/tts/synthesize/chapter",
            json={"text": "Uno.\n\nDos.", "work_id": "w1", "char_id": "hero"},
        )
        assert ch.status_code == 200
        assert ch.json()["count"] == 2
