"""Unit tests for Bloque 74 - Offline Voice Interaction Engine."""

from __future__ import annotations

import asyncio
import base64
import io
import wave
from pathlib import Path

import pytest

from backend.audio.voice import (
    VoiceEventType,
    VoiceInteractionEngine,
    VoiceSession,
    VoiceSessionStatus,
    VoiceStatus,
    get_voice_engine,
    reset_voice_engine,
)


@pytest.fixture
def engine():
    reset_voice_engine()
    e = VoiceInteractionEngine()
    yield e
    reset_voice_engine()


class TestVoiceSession:
    def test_to_dict(self):
        s = VoiceSession(session_id="abc", status=VoiceSessionStatus.LISTENING, transcript="hola")
        d = s.to_dict()
        assert d["session_id"] == "abc"
        assert d["status"] == "listening"
        assert d["transcript"] == "hola"

    def test_default_status(self):
        s = VoiceSession(session_id="x")
        assert s.status == VoiceSessionStatus.IDLE
        assert s.audio_chunks == 0


class TestVoiceStatus:
    def test_to_dict(self):
        s = VoiceStatus(
            available=True,
            stt_available=True,
            tts_available=False,
            stt_engine="stub",
            tts_engine="disabled",
            sample_rate=16000,
            active_sessions=1,
            total_sessions=2,
            running=True,
        )
        d = s.to_dict()
        assert d["available"] is True
        assert d["stt_engine"] == "stub"
        assert d["sample_rate"] == 16000


class TestVoiceInteractionEngine:
    def test_create_and_get_session(self, engine):
        s = engine.create_session({"source": "test"})
        assert s.session_id
        fetched = engine.get_session(s.session_id)
        assert fetched is not None
        assert fetched.metadata["source"] == "test"

    def test_list_sessions(self, engine):
        engine.create_session()
        engine.create_session()
        assert len(engine.list_sessions()) == 2

    def test_close_session(self, engine):
        s = engine.create_session()
        assert engine.close_session(s.session_id) is True
        assert engine.close_session(s.session_id) is False

    def test_close_missing_session(self, engine):
        assert engine.close_session("missing") is False

    def test_receive_audio_chunk(self, engine):
        s = engine.create_session()
        n = engine.receive_audio_chunk(s.session_id, b"\x00\x00" * 100)
        assert n == 1
        s2 = engine.get_session(s.session_id)
        assert s2.audio_chunks == 1

    def test_receive_audio_missing_session(self, engine):
        assert engine.receive_audio_chunk("missing", b"\x00\x00") == 0

    def test_status(self, engine):
        st = engine.status()
        assert isinstance(st, VoiceStatus)
        assert st.stt_engine  # non-empty string
        assert st.sample_rate == 16000

    def test_singleton(self):
        reset_voice_engine()
        a = get_voice_engine()
        b = get_voice_engine()
        assert a is b
        reset_voice_engine()

    def test_process_missing_session(self, engine):
        result = asyncio.run(engine.process_session("missing"))
        assert result["ok"] is False
        assert result["reason"] == "session_not_found"

    def test_process_empty_session(self, engine):
        s = engine.create_session()
        result = asyncio.run(engine.process_session(s.session_id))
        assert result["ok"] is True
        assert result["reason"] == "empty"


class TestVoiceEventType:
    def test_values(self):
        assert VoiceEventType.SESSION_STARTED.value == "session_started"
        assert VoiceEventType.TRANSCRIPT.value == "transcript"
        assert VoiceEventType.TTS_DONE.value == "tts_done"
        assert VoiceEventType.ERROR.value == "error"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
