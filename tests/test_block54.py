"""Tests for BLOQUE 54 - AURA Local Wake-Word & Hands-Free Voice Dialogue Engine."""

import io
import json
import wave
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_wav(seconds=1.0, sr=16000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"\x00\x00" * int(sr * seconds))
    return buf.getvalue()


class TestRingBuffer:
    def test_add_and_get_wav(self):
        from backend.audio.wake_word import RingBuffer

        rb = RingBuffer(2.0, 16000)
        rb.add(b"\x00\x00" * 1600)
        wav = rb.get_wav()
        assert isinstance(wav, bytes)
        assert len(wav) > 44

    def test_clear(self):
        from backend.audio.wake_word import RingBuffer

        rb = RingBuffer(2.0, 16000)
        rb.add(b"\x00\x00" * 1600)
        rb.clear()
        assert rb._total_samples == 0


class TestDialogueEngine:
    def test_singleton_exists(self):
        from backend.audio.wake_word import wake_word_engine

        assert wake_word_engine is not None

    def test_state_idle_initially(self):
        from backend.audio.wake_word import DialogueState, wake_word_engine

        assert wake_word_engine.state == DialogueState.IDLE

    def test_new_session(self):
        from backend.audio.wake_word import DialogueState, wake_word_engine

        s = wake_word_engine._new_session()
        assert s.session_id
        assert s.state == DialogueState.IDLE
        assert wake_word_engine.state == DialogueState.IDLE

    def test_status(self):
        from backend.audio.wake_word import wake_word_engine

        st = wake_word_engine.status()
        assert "running" in st
        assert "state" in st
        assert "wake_word_detector" in st
        assert "audio_capture" in st

    def test_register_ws(self):
        from backend.audio.wake_word import wake_word_engine

        ws = MagicMock()
        wake_word_engine.register_ws(ws)
        assert ws in wake_word_engine._ws_clients
        wake_word_engine.unregister_ws(ws)
        assert ws not in wake_word_engine._ws_clients


class TestWakeWordRoutes:
    def test_status_endpoint(self):
        from fastapi.testclient import TestClient

        from backend.main import app

        c = TestClient(app)
        r = c.get("/api/audio/wake-word/status")
        assert r.status_code == 200
        data = r.json()
        assert "state" in data

    def test_sessions_endpoint(self):
        from fastapi.testclient import TestClient

        from backend.main import app

        c = TestClient(app)
        r = c.get("/api/audio/wake-word/sessions")
        assert r.status_code == 200
        assert "sessions" in r.json()

    def test_stop_endpoint(self):
        from fastapi.testclient import TestClient

        from backend.main import app

        c = TestClient(app)
        r = c.post("/api/audio/wake-word/stop")
        assert r.status_code == 200
        assert r.json()["running"] is False
