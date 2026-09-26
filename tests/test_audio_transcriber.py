"""Tests Bloque 37 — Local Whisper STT Engine (sin inferencia real).

Valida contra la API real del módulo (engine auto/stub):
- LocalWhisperTranscriber: formatos, tmp dir, cleanup, pipeline async.
- Transcripción "real" mockeando engine_available + _load_model (faster-whisper).
- Motor stub (entorno sin torch): transcripción determinista sin nube.
- Endpoints REST /api/audio/transcribe y /transcribe/canon: 200, 415, 422, 503, 401.
- status() no expone rutas ni secretos.
- App mínima FastAPI con el router de audio (sin cargar backend.main).
"""

from __future__ import annotations

import io
import os
import struct
import time
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.audio.transcriber as tr
from backend.audio.routes import router as audio_router
from backend.audio.transcriber import (
    LocalWhisperTranscriber,
    UnsupportedAudioFormat,
    reset_transcriber,
)


@pytest.fixture()
def transcriber(tmp_path, monkeypatch):
    # engine="stub" → available=True sin necesidad de torch (entorno de CI/tests).
    t = LocalWhisperTranscriber(tmp_dir=str(tmp_path / "tmp_audio"), engine="stub")
    monkeypatch.setattr(tr, "get_transcriber", lambda: t)
    monkeypatch.setattr("backend.audio.routes.get_transcriber", lambda: t)
    reset_transcriber()
    yield t
    reset_transcriber()


def make_wav_bytes(seconds: float = 0.2, freq: int = 440, rate: int = 8000) -> bytes:
    """Genera un WAV mono 16-bit válido para uploads."""
    n = int(rate * seconds)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        for i in range(n):
            val = int(12000 * (i % freq) / freq)
            w.writeframesraw(struct.pack("<h", val - 6000))
    return buf.getvalue()


class _FakeSegment:
    def __init__(self, text):
        self.text = text


def _fake_model(lang="es", dur=1.5):
    model = MagicMock()
    info = SimpleNamespace(language=lang, duration=dur)
    model.transcribe.return_value = (
        [_FakeSegment("El héroe"), _FakeSegment("cruza el umbral")],
        info,
    )
    return model


def _force_real_engine(transcriber, monkeypatch):
    """Fuerza engine_available=True + modelo mockeado para tests de inferencia 'real'."""
    monkeypatch.setattr(type(transcriber), "engine_available", property(lambda self: True))
    monkeypatch.setattr(transcriber, "_load_model", lambda: _fake_model())


# -- Formatos y tmp dir -----------------------------------------------------------


def test_unsupported_format_rejected(transcriber):
    with pytest.raises(UnsupportedAudioFormat):
        transcriber.save_upload("malware.exe", b"\x00")


@pytest.mark.parametrize("ext", [".ogg", ".wav", ".mp3", ".m4a", ".webm", ".flac"])
def test_supported_extensions_accepted(transcriber, ext):
    path = transcriber.save_upload(f"nota{ext}", b"x")
    assert path.exists()
    assert path.suffix == ext


def test_save_upload_sanitizes_filename(transcriber):
    path = transcriber.save_upload("../../etc/passwd.wav", b"x")
    assert ".." not in path.name and "/" not in path.name


def test_cleanup_removes_old_files(transcriber):
    old = transcriber.save_upload("old.wav", b"x")
    new = transcriber.save_upload("new.wav", b"y")
    past = time.time() - 7200
    os.utime(old, (past, past))
    removed = transcriber.cleanup(max_age_secs=3600)
    assert removed == 1
    assert not old.exists()
    assert new.exists()


# -- Motor stub (sin torch) -------------------------------------------------------


def test_stub_engine_produces_local_deterministic_text(transcriber):
    path = transcriber.save_upload("clip.wav", make_wav_bytes())
    result = transcriber.transcribe_file(path)
    assert result["engine"] == "stub"
    assert "STT local stub" in result["text"]
    assert result["language"] == transcriber.language


def test_stub_never_leaks_audio_to_cloud(transcriber):
    """El stub procesa localmente: el texto no contiene datos del audio."""
    payload = b"audio-secreto-que-no-debe-salir" * 10
    path = transcriber.save_upload("secreto.wav", payload)
    result = transcriber.transcribe_file(path)
    assert b"audio-secreto" not in result["text"].encode("utf-8")


# -- Inferencia "real" mockeada (engine_available forzado) --------------------------


def test_transcribe_file_with_mocked_model(transcriber, monkeypatch):
    _force_real_engine(transcriber, monkeypatch)
    path = transcriber.save_upload("clip.wav", make_wav_bytes())
    result = transcriber.transcribe_file(path)
    assert result["text"] == "El héroe cruza el umbral"
    assert result["language"] == "es"
    assert result["engine"] == "faster-whisper"


@pytest.mark.asyncio
async def test_transcribe_bytes_pipeline_cleans_tmp(transcriber, monkeypatch):
    _force_real_engine(transcriber, monkeypatch)
    result = await transcriber.transcribe_bytes("voz.wav", make_wav_bytes())
    assert "héroe" in result["text"]
    assert list(transcriber.tmp_dir.glob("*")) == []


def test_transcribe_file_missing_raises(transcriber):
    with pytest.raises(FileNotFoundError):
        transcriber.transcribe_file(Path("no/existe.wav"))


# -- available / status -----------------------------------------------------------


def test_available_true_for_stub_engine(transcriber):
    assert transcriber.available is True
    assert transcriber.engine_available is False
    assert transcriber.engine_name == "stub"


def test_available_false_when_auto_and_no_torch(tmp_path):
    t = LocalWhisperTranscriber(tmp_dir=str(tmp_path / "t"), engine="auto")
    assert t.engine_available is False
    assert t.available is False


def test_status_does_not_leak_paths(transcriber):
    status = transcriber.status()
    assert status["engine"] == "stub"
    assert str(transcriber.tmp_dir) not in str(status)


# -- Endpoints REST ------------------------------------------------------------------


@pytest.fixture()
def client(transcriber):
    app = FastAPI()
    app.include_router(audio_router)
    return TestClient(app)


def test_rest_status_endpoint(client, transcriber):
    r = client.get("/api/audio/transcribe/status")
    assert r.status_code == 200
    body = r.json()
    assert body["engine"] == "stub"
    assert body["available"] is True
    assert ".ogg" in body["supported_extensions"]


def test_rest_transcribe_ok_with_real_engine(client, transcriber, monkeypatch):
    _force_real_engine(transcriber, monkeypatch)
    r = client.post(
        "/api/audio/transcribe",
        files={"file": ("voz.wav", make_wav_bytes(), "audio/wav")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "héroe" in body["text"]


def test_rest_transcribe_ok_with_stub_engine(client, transcriber):
    # Sin torch, el motor stub responde 200 con texto local.
    r = client.post(
        "/api/audio/transcribe",
        files={"file": ("voz.wav", make_wav_bytes(), "audio/wav")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "STT local stub" in body["text"]


def test_rest_transcribe_unsupported_format_415(client, transcriber):
    r = client.post(
        "/api/audio/transcribe",
        files={"file": ("virus.exe", b"\x00", "application/octet-stream")},
    )
    assert r.status_code == 415


def test_rest_transcribe_empty_file_422(client, transcriber):
    r = client.post(
        "/api/audio/transcribe",
        files={"file": ("empty.wav", b"", "audio/wav")},
    )
    assert r.status_code == 422


def test_rest_transcribe_engine_unavailable_503(client, transcriber, monkeypatch):
    # engine="auto" sin torch → available False → 503.
    real = LocalWhisperTranscriber(tmp_dir=str(transcriber.tmp_dir), engine="auto")
    monkeypatch.setattr(tr, "get_transcriber", lambda: real)
    monkeypatch.setattr("backend.audio.routes.get_transcriber", lambda: real)
    r = client.post(
        "/api/audio/transcribe",
        files={"file": ("voz.wav", make_wav_bytes(), "audio/wav")},
    )
    assert r.status_code == 503


def test_rest_transcribe_requires_api_key_when_configured(client, transcriber, monkeypatch):
    monkeypatch.setenv("AURA_API_KEY", "secret-key")
    r = client.post(
        "/api/audio/transcribe",
        files={"file": ("voz.wav", make_wav_bytes(), "audio/wav")},
    )
    assert r.status_code == 401
    r_ok = client.post(
        "/api/audio/transcribe",
        files={"file": ("voz.wav", make_wav_bytes(), "audio/wav")},
        headers={"X-API-Key": "secret-key"},
    )
    assert r_ok.status_code == 200
    assert "secret-key" not in r_ok.text


def test_rest_transcribe_canon_adds_event_and_broadcasts(client, transcriber, monkeypatch):
    _force_real_engine(transcriber, monkeypatch)

    fake_ct = MagicMock()
    fake_ct.add_canon_event.return_value = {"event_id": "evt-123", "status": "added"}
    monkeypatch.setattr("backend.story_memory.canon_tracker.CanonTracker", lambda: fake_ct)

    broadcasted = {}

    class _FakeGateway:
        async def broadcast(self, event_type, payload, work_id=None):
            broadcasted["type"] = event_type
            broadcasted["work_id"] = work_id
            return 1

    import backend.websocket_manager as ws_mod

    monkeypatch.setattr(ws_mod, "ws_gateway", _FakeGateway())

    r = client.post(
        "/api/audio/transcribe/canon",
        files={"file": ("voz.ogg", make_wav_bytes(), "audio/ogg")},
        data={"work_id": "obra_test", "source": "discord"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["work_id"] == "obra_test"
    assert body["event_id"] == "evt-123"
    assert body["canon_added"] is True
    assert fake_ct.add_canon_event.call_args.kwargs["description"].startswith("El héroe")
    assert broadcasted["type"] == "canon_event"


def test_rest_transcribe_canon_requires_work_id(client, transcriber, monkeypatch):
    _force_real_engine(transcriber, monkeypatch)
    r = client.post(
        "/api/audio/transcribe/canon",
        files={"file": ("voz.wav", make_wav_bytes(), "audio/wav")},
        data={"work_id": "   "},
    )
    assert r.status_code == 422
