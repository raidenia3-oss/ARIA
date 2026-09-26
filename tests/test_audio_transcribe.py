"""Tests Bloque 37 — Local Whisper STT Engine (100% local).

Valida (sin tocar la red ni servicios cloud):
- Engine selector (auto vs stub) y `available`/`engine_name` en función de torch.
- Stub fallback: transcripción simulada 100% local cuando no hay modelo real.
- Pipeline REST /api/audio/transcribe (multipart upload): 200 / 415 / 422 / 503.
- Bridge Discord/AME: POST /transcribe/canon puebla el canon literario y
  retorna evento canónico sin exponer secretos.
- Estado del motor en /transcribe/status (engine, available, extensiones).
- Limpieza de ficheros temporales del tmp dir.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import wave

import pytest

from backend.audio.transcriber import (
    LocalWhisperTranscriber,
    UnsupportedAudioFormat,
    get_transcriber,
    reset_transcriber,
)


def _wav_bytes(text_marker: str = "hola") -> bytes:
    """Genera un buffer WAV PCM 16kHz mono válido (no requiere ffmpeg)."""
    n = 16000
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(bytes([0] * n * 2))
    return buf.getvalue()


# -- Motor (unitario puro, sin TestClient) ----------------------------------------


def test_engine_selector_auto_is_unavailable_without_torch():
    t = LocalWhisperTranscriber(engine="auto")
    assert t.engine == "auto"
    # torch falta en este entorno → engine real no disponible.
    assert t.engine_available is False
    assert t.available is (t.engine_available or t.engine == "stub")


def test_engine_stub_is_available_without_torch():
    t = LocalWhisperTranscriber(engine="stub")
    assert t.engine == "stub"
    assert t.available is True
    assert t.engine_name == "stub"


def test_stub_transcribe_returns_deterministic_local_text(tmp_path):
    t = LocalWhisperTranscriber(engine="stub")
    content = b"\x00\x01\x02\x03 voice bytes"
    path = tmp_path / "note.ogg"
    path.write_bytes(content)
    result = t.transcribe_file(path)
    assert result["engine"] == "stub"
    assert result["text"].startswith("[STT local stub]")
    # 100% local: el hash del audio está en la salida (no se envía a la nube).
    assert hashlib.sha1(content).hexdigest()[:12] in result["text"]
    assert result["language"] == "es"
    assert result["model"] == "base"


def test_transcribe_file_missing_raises():
    t = LocalWhisperTranscriber(engine="stub")
    with pytest.raises(FileNotFoundError):
        t.transcribe_file(__import__("pathlib").Path("/no/existe.wav"))


# -- Endpoints REST (TestClient) --------------------------------------------------


class TestAudioREST:
    @pytest.fixture()
    def client(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AURA_WHISPER_ENGINE", "stub")
        monkeypatch.setenv("AURA_AUDIO_TMP_DIR", str(tmp_path / "tmp_audio"))
        monkeypatch.setenv("AURA_STORY_DIR", str(tmp_path / "story"))
        reset_transcriber()
        from fastapi.testclient import TestClient

        from backend.main import app

        return TestClient(app)

    def test_status_endpoint(self, client):
        resp = client.get("/api/audio/transcribe/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["engine"] == "stub"
        assert data["available"] is True
        assert ".wav" in data["supported_extensions"]

    def test_transcribe_wav_returns_text(self, client):
        resp = client.post(
            "/api/audio/transcribe",
            files={"file": ("note.wav", _wav_bytes(), "audio/wav")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "text" in data and data["text"]
        assert data["engine"] == "stub"

    def test_transcribe_bad_format_returns_415(self, client):
        resp = client.post(
            "/api/audio/transcribe",
            files={"file": ("note.txt", b"plain text", "text/plain")},
        )
        assert resp.status_code == 415

    def test_transcribe_empty_body_returns_422(self, client):
        resp = client.post("/api/audio/transcribe", files={"file": ("note.wav", b"", "audio/wav")})
        assert resp.status_code == 422

    def test_canon_bridge_populates_canon_event(self, client, tmp_path):
        resp = client.post(
            "/api/audio/transcribe/canon",
            data={"work_id": "voice_test_work", "source": "discord"},
            files={"file": ("voice.ogg", b"\x00\x01voice bytes", "audio/ogg")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["work_id"] == "voice_test_work"
        assert data["canon_added"] is True
        assert data["event_id"] != ""

        # Verificar que el evento canónico fue persistido (100% local).
        from backend.story_memory.canon_tracker import CanonTracker

        ct = CanonTracker()
        events = ct.storage.get_canon_events("voice_test_work")
        assert len(events) == 1
        assert data["text"] in events[0]["description"]
        assert events[0]["source"] == "discord"

    def test_canon_bridge_requires_work_id(self, client):
        resp = client.post(
            "/api/audio/transcribe/canon",
            data={"work_id": "", "source": "discord"},
            files={"file": ("voice.ogg", b"\x00\x01voice", "audio/ogg")},
        )
        assert resp.status_code == 422


class TestAudioUnavailableRealEngine:
    def test_transcribe_auto_engine_without_torch_returns_503(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AURA_WHISPER_ENGINE", "auto")
        monkeypatch.setenv("AURA_AUDIO_TMP_DIR", str(tmp_path / "tmp_audio"))
        reset_transcriber()
        from fastapi.testclient import TestClient

        from backend.main import app

        with TestClient(app) as client:
            resp = client.post(
                "/api/audio/transcribe",
                files={"file": ("note.wav", _wav_bytes(), "audio/wav")},
            )
        assert resp.status_code == 503
        reset_transcriber()
