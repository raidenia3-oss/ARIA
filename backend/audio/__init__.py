"""AURA Local Audio — STT (Bloque 37) + TTS (Bloque 46) 100% local."""

from backend.audio.transcriber import (
    LocalWhisperTranscriber,
    get_transcriber,
    reset_transcriber,
)
from backend.audio.tts_generator import (
    LocalTTSEngine,
    TTSGenerator,
    VoiceProfile,
    TTSResult,
    get_tts_generator,
    reset_tts_generator,
)
from backend.audio.routes import router as audio_router
from backend.audio.tts_routes import router as tts_router
from backend.audio.wake_word import (
    DialogueEngine,
    DialogueSession,
    DialogueState,
    RingBuffer,
    VoskWakeDetector,
    WakeWordConfig,
    WakeWordEvent,
    wake_word_engine,
)
from backend.audio.wake_word_routes import router as wake_word_router
from backend.audio.voice import (
    VoiceInteractionEngine,
    VoiceSession,
    VoiceSessionStatus,
    VoiceEventType,
    VoiceStatus,
    get_voice_engine,
    reset_voice_engine,
)
from backend.audio.voice_routes import router as voice_router

__all__ = [
    "LocalWhisperTranscriber",
    "get_transcriber",
    "reset_transcriber",
    "LocalTTSEngine",
    "TTSGenerator",
    "VoiceProfile",
    "TTSResult",
    "get_tts_generator",
    "reset_tts_generator",
    "audio_router",
    "tts_router",
    "DialogueEngine",
    "DialogueSession",
    "DialogueState",
    "RingBuffer",
    "VoskWakeDetector",
    "WakeWordConfig",
    "WakeWordEvent",
    "wake_word_engine",
    "wake_word_router",
    "VoiceInteractionEngine",
    "VoiceSession",
    "VoiceSessionStatus",
    "VoiceEventType",
    "VoiceStatus",
    "get_voice_engine",
    "reset_voice_engine",
    "voice_router",
]

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
