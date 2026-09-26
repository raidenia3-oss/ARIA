"""Audio Pipeline for AURA - Real-time bidirectional voice processing.

- VAD: Silero VAD if available, otherwise energy-based RMS VAD.
- STT: Faster-Whisper (base/small) in Spanish.
- Integrates with brain/orchestrator for agent routing.
"""

from __future__ import annotations

import io
import logging
import math
import queue
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURAAudioPipeline")

try:
    import numpy as np
except Exception:
    np = None

try:
    import soundfile as sf
except Exception:
    sf = None

try:
    from faster_whisper import WhisperModel
except Exception:
    WhisperModel = None

try:
    import torch
except Exception:
    torch = None

try:
    from silero_vad import load_silero_vad, read_audio, VADIterator
except Exception:
    load_silero_vad = None
    read_audio = None
    VADIterator = None


AUDIO_SAMPLE_RATE = 16000
AUDIO_FRAME_MS = 30
VAD_THRESHOLD = 0.5
VAD_MIN_SILENCE_MS = 500
STT_MODEL_SIZE = "base"
STT_LANGUAGE = "es"
RMS_SPEECH_THRESHOLD = 0.02
RMS_SILENCE_THRESHOLD = 0.008
MIN_SPEECH_MS = 300


@dataclass
class SpeechSegment:
    start_ms: int
    end_ms: int
    audio_bytes: bytes
    sample_rate: int = AUDIO_SAMPLE_RATE
    transcribed: bool = False
    text: str = ""
    confidence: float = 0.0


class EnergyVAD:
    def __init__(self, speech_threshold: float = RMS_SPEECH_THRESHOLD, silence_threshold: float = RMS_SILENCE_THRESHOLD, min_speech_ms: int = MIN_SPEECH_MS) -> None:
        self.speech_threshold = speech_threshold
        self.silence_threshold = silence_threshold
        self.min_speech_ms = min_speech_ms
        self._speech_start: Optional[float] = None
        self._last_speech: Optional[float] = None

    def process(self, frame_bytes: bytes, timestamp_ms: int) -> Optional[SpeechSegment]:
        if np is None:
            return None
        try:
            samples = np.frombuffer(frame_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            rms = math.sqrt(float(np.mean(samples ** 2)))
        except Exception:
            return None
        now = time.time()
        if rms > self.speech_threshold:
            if self._speech_start is None:
                self._speech_start = now
            self._last_speech = now
            return None
        if self._speech_start is not None and self._last_speech is not None:
            if now - self._last_speech > VAD_MIN_SILENCE_MS / 1000.0:
                start_ms = int((self._speech_start - (now - self._last_speech)) * 1000)
                end_ms = int(self._last_speech * 1000)
                seg = SpeechSegment(start_ms=max(0, start_ms), end_ms=end_ms, audio_bytes=b"")
                self._speech_start = None
                self._last_speech = None
                return seg
        return None


class SileroVAD:
    def __init__(self, threshold: float = VAD_THRESHOLD) -> None:
        self.threshold = threshold
        self._model = None
        self._iterator = None
        self._load_model()

    def _load_model(self) -> None:
        if load_silero_vad is None or torch is None:
            return
        try:
            self._model = load_silero_vad()
            self._iterator = VADIterator(self._model)
        except Exception:
            self._model = None
            self._iterator = None

    def process(self, frame_bytes: bytes, timestamp_ms: int) -> Optional[SpeechSegment]:
        if self._iterator is None or read_audio is None:
            return None
        try:
            audio = read_audio(io.BytesIO(frame_bytes), sampling_rate=AUDIO_SAMPLE_RATE)
            results = self._iterator(audio, return_seconds=False)
            if results:
                for res in results:
                    if res.get("type") == "speech":
                        start = int(res.get("start", 0) * 1000)
                        end = int(res.get("end", 0) * 1000)
                        return SpeechSegment(start_ms=start, end_ms=end, audio_bytes=frame_bytes)
        except Exception:
            pass
        return None


class AudioPipeline:
    def __init__(self, brain: Any = None) -> None:
        self.brain = brain
        self._vad = self._init_vad()
        self._stt_model = self._init_stt()
        self._segments: List[SpeechSegment] = []
        self._buffer = bytearray()
        self._last_ts = 0
        self._processing = False
        self._queue: "queue.Queue[bytes]" = queue.Queue()
        threading.Thread(target=self._pipeline_loop, daemon=True).start()

    def _init_vad(self):
        if SileroVAD is not None:
            try:
                return SileroVAD()
            except Exception:
                pass
        return EnergyVAD()

    def _init_stt(self):
        if WhisperModel is None:
            return None
        try:
            return WhisperModel(STT_MODEL_SIZE, device="cpu", compute_type="int8")
        except Exception:
            return None

    def push_audio(self, audio_bytes: bytes, timestamp_ms: Optional[int] = None) -> None:
        if timestamp_ms is None:
            timestamp_ms = int(time.time() * 1000)
        self._buffer.extend(audio_bytes)
        self._last_ts = timestamp_ms
        self._try_vad()

    def _try_vad(self) -> None:
        frame_size = int(AUDIO_SAMPLE_RATE * AUDIO_FRAME_MS / 1000) * 2
        while len(self._buffer) >= frame_size:
            frame = bytes(self._buffer[:frame_size])
            del self._buffer[:frame_size]
            seg = self._vad.process(frame, self._last_ts)
            if seg:
                seg.audio_bytes = frame
                self._segments.append(seg)
                self._queue.put(frame)

    def _pipeline_loop(self) -> None:
        while True:
            try:
                frame = self._queue.get(timeout=1)
            except Exception:
                continue
            if self._stt_model is None:
                continue
            try:
                segments, info = self._stt_model.transcribe(
                    io.BytesIO(frame),
                    beam_size=5,
                    language=STT_LANGUAGE,
                    task="transcribe",
                )
                text_parts = []
                for s in segments:
                    text_parts.append(s.text)
                text = " ".join(text_parts).strip()
                if text and self.brain is not None:
                    try:
                        self.brain.record_conversation(device="webrtc", role="user", prompt=text, response="", provider="stt")
                    except Exception:
                        pass
            except Exception:
                pass

    def get_status(self) -> Dict[str, Any]:
        return {
            "vad": type(self._vad).__name__,
            "stt": "faster-whisper" if self._stt_model else "disabled",
            "buffered_bytes": len(self._buffer),
            "queued_frames": self._queue.qsize(),
            "segments": len(self._segments),
        }
