"""PARTE 4: AUDIO MONITORING PRO (300 lines) — Audio análisis avanzado.

Funciones async:
- detect_audio_advanced(): RMS, bands, type detection, beat detection
- speech_recognition_streaming(): Whisper streaming, realtime
- music_analysis(): Genre, BPM, key, mood detection
"""

from __future__ import annotations

import asyncio
import json
import math
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import sounddevice as sd

    HAS_SOUNDDEVICE = True
except ImportError:
    HAS_SOUNDDEVICE = False

try:
    from faster_whisper import WhisperModel

    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False

try:
    import vosk

    HAS_VOSK = True
except ImportError:
    HAS_VOSK = False

try:
    import wave

    HAS_WAVE = True
except ImportError:
    HAS_WAVE = False

try:
    import win32gui

    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


@dataclass
class AudioAnalysisResult:
    audio_detected: bool = False
    volume: float = 0.0
    rms_level: float = 0.0
    type: str = "unknown"
    beats_per_minute: Optional[int] = None
    transcription: str = ""
    speech_confidence: float = 0.0
    language: str = "unknown"
    is_command: bool = False
    is_music: bool = False
    genre: str = ""
    bpm: Optional[int] = None
    key: str = ""
    mood: str = ""
    frequency_bands: Dict[str, float] = field(default_factory=dict)


BAND_FREQS = {
    "sub_bass": (20, 60),
    "bass": (60, 250),
    "low_mid": (250, 500),
    "mid": (500, 2000),
    "upper_mid": (2000, 4000),
    "presence": (4000, 6000),
    "brilliance": (6000, 20000),
}

COMMAND_KEYWORDS = [
    "genera",
    "crea",
    "haz",
    "muéstrame",
    "dime",
    "cuéntame",
    "story",
    "historia",
    "character",
    "personaje",
    "world",
    "mundo",
    "prompt",
    "imagen",
    "anime",
    "modo",
    "ayuda",
    "hola",
]


async def detect_audio_advanced(
    sample_rate: int = 16000,
    block_size: int = 1024,
    duration_ms: int = 500,
) -> AudioAnalysisResult:
    """Detecta audio avanzado: RMS + bandas + tipo + beats."""
    if not HAS_SOUNDDEVICE or not HAS_NUMPY:
        return AudioAnalysisResult(audio_detected=False, volume=0.0)

    try:
        audio_buffer = sd.rec(
            frames=int(sample_rate * duration_ms / 1000),
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
        )
        sd.wait()

        samples = audio_buffer.flatten()
        if len(samples) == 0:
            return AudioAnalysisResult()

        rms = math.sqrt(sum(s * s for s in samples) / len(samples))
        volume = min(rms / 32768.0 * 100, 100)
        audio_detected = volume > 5.0

        fft_size = min(len(samples), 2048)
        if HAS_NUMPY and fft_size > 0:
            fft_data = np.fft.rfft(samples[:fft_size].astype(np.float64))
            magnitudes = np.abs(fft_data)[: len(fft_data) // 2]
            freqs = np.fft.rfftfreq(fft_size, 1.0 / sample_rate)

            frequency_bands = {}
            max_freq = freqs[-1] if len(freqs) > 0 else sample_rate / 2
            for band_name, (low, high) in BAND_FREQS.items():
                low_idx = int((low / max_freq) * len(magnitudes)) if max_freq > 0 else 0
                high_idx = (
                    int((high / max_freq) * len(magnitudes)) if max_freq > 0 else len(magnitudes)
                )
                high_idx = min(high_idx, len(magnitudes))
                if high_idx > low_idx:
                    avg_mag = float(np.mean(magnitudes[low_idx:high_idx]))
                    frequency_bands[band_name] = round(avg_mag, 4)

            audio_type = "silence"
            total_energy = float(np.sum(magnitudes))
            if total_energy > 1000:
                if volume > 60:
                    audio_type = "loud_audio"
                elif volume > 30:
                    audio_type = "moderate_audio"
                else:
                    audio_type = "quiet_audio"

            is_music = _detect_music_pattern(magnitudes, sample_rate)
            bpm = _estimate_bpm(magnitudes, sample_rate) if is_music else None

            return AudioAnalysisResult(
                audio_detected=audio_detected,
                volume=round(volume, 2),
                rms_level=round(rms / 32768.0, 4),
                type=audio_type,
                beats_per_minute=bpm,
                frequency_bands=frequency_bands,
                is_music=is_music,
            )
    except Exception:
        pass

    return AudioAnalysisResult(audio_detected=False, volume=0.0)


async def speech_recognition_streaming(
    audio_buffer: Optional[bytes] = None,
    sample_rate: int = 16000,
    language: str = "es",
    stream_chunk_ms: int = 300,
) -> AudioAnalysisResult:
    """Transcripción speech streaming en tiempo real."""
    result = AudioAnalysisResult()

    if audio_buffer is None:
        if not HAS_SOUNDDEVICE:
            return result
        try:
            audio_buffer = sd.rec(
                frames=int(sample_rate * stream_chunk_ms / 1000),
                samplerate=sample_rate,
                channels=1,
                dtype="int16",
            )
            sd.wait()
        except Exception:
            return result

    if HAS_WHISPER:
        try:
            model = WhisperModel("base", device="cpu", compute_type="int8")
            import numpy as np

            if isinstance(audio_buffer, bytes):
                audio_np = np.frombuffer(audio_buffer, dtype=np.int16).astype(np.float32) / 32768.0
            else:
                audio_np = audio_buffer

            segments, info = model.transcribe(
                audio_np,
                language=language if language != "auto" else None,
                beam_size=5,
                vad_filter=True,
            )

            segments_list = list(segments)
            if segments_list:
                transcription = " ".join(s.text for s in segments_list)
                result.transcription = transcription
                result.speech_confidence = info.avg_logprob
                result.language = info.language or language
                result.language = f"{result.language}-{info.language_code}"
                result.speech_confidence = max(0.0, min(1.0, float(result.speech_confidence) + 0.5))

                transcription_lower = transcription.lower()
                result.is_command = any(kw in transcription_lower for kw in COMMAND_KEYWORDS)

                if not result.is_command:
                    result.mood = _infer_mood_from_text(transcription)

                return result
        except Exception:
            pass

    if HAS_VOSK:
        try:
            model = vosk.Model(lang=language)
            if isinstance(audio_buffer, bytes) and len(audio_buffer) >= 2:
                samples = struct.unpack(f"<{len(audio_buffer)//2}h", audio_buffer)
                import io
                import wave as wf

                wav_io = io.BytesIO()
                with wf.open(wav_io, "wb") as wf_out:
                    wf_out.setnchannels(1)
                    wf_out.setsampwidth(2)
                    wf_out.setframerate(sample_rate)
                    wf_out.writeframes(audio_buffer)
                wav_io.seek(0)
                rec = vosk.KaldiRecognizer(model, sample_rate)
                rec.SetWords(True)
                wav_io.seek(0)
                with wf.open(wav_io, "rb") as wf_in:
                    while True:
                        data = wf_in.readframes(4000)
                        if len(data) == 0:
                            break
                        rec.AcceptWaveform(data)
                res = json.loads(rec.FinalResult())
                result.transcription = res.get("text", "")
                result.language = language
                result.speech_confidence = 0.5
                result.is_command = any(
                    kw in result.transcription.lower() for kw in COMMAND_KEYWORDS
                )
                return result
        except Exception:
            pass

    return result


async def music_analysis(
    audio_buffer: Optional[bytes] = None,
    sample_rate: int = 16000,
) -> AudioAnalysisResult:
    """Análisis musical: genre, BPM, key, mood."""
    result = AudioAnalysisResult(is_music=True)

    if not HAS_NUMPY or not HAS_SOUNDDEVICE:
        result.genre = "unknown"
        result.mood = "neutral"
        return result

    try:
        if audio_buffer is None:
            audio_buffer = sd.rec(
                frames=sample_rate * 3,
                samplerate=sample_rate,
                channels=1,
                dtype="int16",
            )
            sd.wait()

        if isinstance(audio_buffer, bytes) and len(audio_buffer) >= 2:
            samples = np.frombuffer(audio_buffer, dtype=np.int16).astype(np.float32) / 32768.0
        else:
            samples = audio_buffer.astype(np.float32) / 32768.0

        rms = float(np.sqrt(np.mean(samples**2)))
        result.volume = round(rms * 100, 2)

        fft_size = min(len(samples), 4096)
        fft_data = np.fft.rfft(samples[:fft_size])
        magnitudes = np.abs(fft_data)
        freqs = np.fft.rfftfreq(fft_size, 1.0 / sample_rate)

        energy_bass = float(np.mean(magnitudes[:50])) if len(magnitudes) > 50 else 0.0
        energy_mid = float(np.mean(magnitudes[50:200])) if len(magnitudes) > 200 else 0.0
        energy_high = float(np.mean(magnitudes[200:500])) if len(magnitudes) > 500 else 0.0

        if energy_bass > 0.1 and energy_mid < 0.05:
            result.genre = "electronic"
        elif energy_bass > 0.1 and energy_high > 0.08:
            result.genre = "rock"
        elif energy_bass > 0.08 and energy_mid > 0.08:
            result.genre = "metal"
        elif energy_mid > 0.1 and energy_high < 0.05:
            result.genre = "ambient"
        elif energy_high > 0.1:
            result.genre = "classical"
        elif result.volume > 30:
            result.genre = "pop"
        else:
            result.genre = "unknown"

        result.bpm = _estimate_bpm(magnitudes, sample_rate)
        result.key = _detect_key(magnitudes, freqs)
        result.mood = _detect_mood_from_spectra(energy_bass, energy_mid, energy_high, result.volume)

    except Exception:
        result.genre = "unknown"
        result.mood = "neutral"

    return result


def _detect_music_pattern(magnitudes: np.ndarray, sample_rate: int) -> bool:
    """Detecta si hay patrón musical."""
    if len(magnitudes) < 100:
        return False
    energy = magnitudes[:2000]
    mean_e = float(np.mean(energy))
    variance = float(np.var(energy))
    return variance > mean_e * 2 and mean_e > 0.01


def _estimate_bpm(magnitudes: np.ndarray, sample_rate: int) -> Optional[int]:
    """Estima BPM via análisis de energía bajos."""
    if len(magnitudes) < 100 or sample_rate < 8000:
        return None
    bass_energy = magnitudes[:100]
    if np.max(bass_energy) < 0.01:
        return None
    beats = np.where(bass_energy > np.mean(bass_energy) * 1.5)[0]
    if len(beats) < 3:
        return None
    diffs = np.diff(beats)
    avg_diff = int(np.mean(diffs))
    if avg_diff == 0:
        return None
    bpm = int(round(60.0 * sample_rate / (avg_diff * 2)))
    return max(30, min(300, bpm))


def _detect_key(magnitudes: np.ndarray, freqs: np.ndarray) -> str:
    """Detecta tonalidad musical."""
    keys = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    if len(magnitudes) == 0 or len(freqs) == 0:
        return "C"
    peak_idx = int(np.argmax(magnitudes))
    peak_freq = freqs[peak_idx] if peak_idx < len(freqs) else 0
    if peak_freq == 0:
        return "C"
    note_candidates = [261.63 * (2 ** (i / 12)) for i in range(12)]
    closest = min(note_candidates, key=lambda x: abs(x - peak_freq))
    return keys[note_candidates.index(closest)]


def _detect_mood_from_spectra(bass: float, mid: float, high: float, volume: float) -> str:
    """Detecta mood desde espectro."""
    if volume < 10:
        return "calm"
    if bass > 0.2 and mid < 0.1:
        return "energetic"
    if mid > 0.15 and high > 0.1:
        return "happy"
    if bass > 0.15 and high > 0.05:
        return "aggressive"
    if mid > 0.1 and high < 0.05:
        return "melancholic"
    if volume < 30:
        return "relaxed"
    return "neutral"


def _infer_mood_from_text(text: str) -> str:
    """Infiere mood del texto transcrito."""
    text_l = text.lower()
    if any(w in text_l for w in ["feliz", "contento", "happy", "great", "awesome", "excited"]):
        return "happy"
    if any(w in text_l for w in ["triste", "sad", "depressed", "blue", "lonely"]):
        return "sad"
    if any(w in text_l for w in ["enojado", "angry", "furious", "mad", "frustrated"]):
        return "angry"
    if any(w in text_l for w in ["relajado", "calm", "relaxed", "peaceful", "chill"]):
        return "relaxed"
    if any(w in text_l for w in ["estresado", "stressed", "anxious", "nervous", "worried"]):
        return "stressed"
    if any(w in text_l for w in ["create", "build", "design", "write", "code", "genera"]):
        return "creative"
    return "neutral"
