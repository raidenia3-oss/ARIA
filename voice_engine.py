"""AURA Voice Engine — wake-word, STT, TTS, executive summary.

Modes:
- Embedded: no HTTP required, runs inside the desktop app.
- External: can call external APIs if configured.

Usage:
    from voice_engine import VoiceEngine
    engine = VoiceEngine()
    engine.start_listening()
"""

from __future__ import annotations

import json
import os
import queue
import re
import tempfile
import threading
import time
import urllib.request
import wave
from typing import Any, Callable, Dict, List, Optional


class _SentenceChunker:
    """Acumula tokens del stream LLM y corta en frases para TTS token-a-token."""
    ENDERS = ".!?\u2026\n"

    def __init__(self, min_len: int = 24, max_len: int = 200) -> None:
        self.min_len = min_len
        self.max_len = max_len
        self.buf = ""

    def reset(self) -> None:
        self.buf = ""

    def feed(self, token: str) -> List[str]:
        self.buf += token or ""
        return self._drain(False)

    def flush(self) -> List[str]:
        out = self._drain(True)
        rest = self.buf.strip()
        self.buf = ""
        if rest:
            out.append(rest)
        return out

    def _drain(self, final: bool) -> List[str]:
        out: List[str] = []
        while True:
            cut = -1
            i = 0
            while i < len(self.buf):
                ch = self.buf[i]
                if ch in self.ENDERS:
                    nxt = self.buf[i + 1:i + 2]
                    ok_next = nxt in ("", " ", "\n", "\t", "\r", '"', "'", ")", "]", "\u00bb")
                    if ok_next and (final or len(self.buf[:i + 1].strip()) >= self.min_len):
                        cut = i + 1
                        break
                i += 1
            if cut < 0:
                if len(self.buf) >= self.max_len:
                    cut = self.max_len
                else:
                    break
            piece = self.buf[:cut].strip()
            self.buf = self.buf[cut:].lstrip()
            if piece:
                out.append(piece)
        return out


class TtsStreamer:
    """TTS incremental: habla por frases mientras el LLM sigue streameando."""

    def __init__(self, rate: int = 170, volume: float = 1.0) -> None:
        self.rate = rate
        self.volume = volume
        self.chunker = _SentenceChunker()
        self._q: queue.Queue = queue.Queue()
        self._speaking = threading.Event()
        self._stop = threading.Event()
        self._spoken = 0
        self._errors = 0
        try:
            import pyttsx3  # noqa: F401
            self._engine_ok = True
        except Exception:
            self._engine_ok = False
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def available(self) -> bool:
        return bool(self._engine_ok)

    def is_busy(self) -> bool:
        return self._speaking.is_set() or not self._q.empty()

    def start_turn(self) -> None:
        self.chunker.reset()
        self._spoken = 0
        self._errors = 0

    def feed(self, token: str) -> List[str]:
        done = self.chunker.feed(token)
        for s in done:
            self.enqueue(s)
        return done

    def flush(self) -> List[str]:
        done = self.chunker.flush()
        for s in done:
            self.enqueue(s)
        return done

    def enqueue(self, sentence: str) -> None:
        text = (sentence or "").strip()
        if text:
            self._q.put(text)

    def stop(self) -> None:
        self._stop.set()
        try:
            while True:
                self._q.get_nowait()
        except Exception:
            pass

    def _worker(self) -> None:
        if not self._engine_ok:
            while not self._stop.is_set():
                try:
                    self._q.get(timeout=0.2)
                except Exception:
                    pass
            return
        import pyttsx3
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", self.rate)
            engine.setProperty("volume", self.volume)
        except Exception:
            self._engine_ok = False
            self._errors += 1
            return
        while not self._stop.is_set():
            try:
                text = self._q.get(timeout=0.2)
            except Exception:
                continue
            self._speaking.set()
            try:
                engine.say(text)
                engine.runAndWait()
                self._spoken += 1
            except Exception:
                self._errors += 1
            finally:
                self._speaking.clear()


class VoiceEngine:
    def __init__(self) -> None:
        self.listening = False
        self.wake_word = "hey aura"
        # Alineado con WakeWordDetector.WAKE_WORDS del backend (antes tenía "hey aura" duplicado).
        self.wake_words = ["hey aura", "hola aura", "ok aura", "oye aura", "aura"]
        self.last_transcript = ""
        self.last_command = ""
        self.command_history: List[Dict[str, Any]] = []
        self.events: queue.Queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None   # antes: threadinging (typo)
        self._stt_available = False
        self._tts_available = False
        self._mic_available = False
        self._sd_available = False
        # STT real vía backend (faster-whisper/vosk) cuando no hay speech_recognition.
        self.backend_base = os.environ.get("AURA_BACKEND_URL", "http://127.0.0.1:8000")
        self.stt_engine = os.environ.get("AURA_STT_ENGINE", "whisper")
        self.on_wake_command = None   # callback(texto) que la app usa para mandar al chat
        # Fase 3: TTS incremental (hablar por frases mientras el LLM streamea).
        self.tts_stream = TtsStreamer()
        self._check_dependencies()

    def _check_dependencies(self) -> None:
        try:
            import speech_recognition as sr
            self._stt_available = True
        except Exception:
            pass
        try:
            import pyttsx3
            self._tts_available = True
        except Exception:
            pass
        try:
            import pyaudio
            self._mic_available = True
        except Exception:
            pass
        try:
            import sounddevice  # type: ignore
            self._sd_available = True
        except Exception:
            pass

    def get_capabilities(self) -> Dict[str, bool]:
        return {
            "stt": self._stt_available or self._sd_available,
            "tts": self._tts_available,
            "mic": self._mic_available or self._sd_available,
            "pyaudio": self._mic_available,
            "sounddevice": self._sd_available,
            "backend_stt": self._sd_available,
        }

    def start_listening(self) -> None:
        if self.listening:
            return
        self.listening = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop_listening(self) -> None:
        self.listening = False

    def _listen_loop(self) -> None:
        recognizer = None
        mic = None
        if self._stt_available and self._mic_available:
            try:
                import speech_recognition as sr
                recognizer = sr.Recognizer()
                mic = sr.Microphone()
                with mic as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.5)
            except Exception:
                recognizer = None
                mic = None

        while self.listening:
            transcript = ""
            source = "speech_recognition"
            if recognizer and mic:
                try:
                    with mic as source_mic:
                        audio = recognizer.listen(source_mic, timeout=1, phrase_time_limit=5)
                    transcript = recognizer.recognize_google(audio, language="es-ES")
                except Exception:
                    transcript = ""
            elif self._sd_available:
                transcript = self._listen_via_backend()
                source = "backend_stt"
            else:
                transcript = self._simulate_transcript()
                source = "simulated"

            if not transcript:
                continue

            self.last_transcript = transcript
            self.events.put({"type": "transcript", "text": transcript, "source": source})

            if self._is_wake_word(transcript):
                self.events.put({"type": "wake_word", "text": transcript, "source": source})
                command = self._extract_command(transcript)
                self.last_command = command
                result = self.execute_command(command)
                self.command_history.append({
                    "timestamp": time.time(),
                    "transcript": transcript,
                    "command": command,
                    "response": result.get("response", ""),
                })
                self.events.put({
                    "type": "command", "command": command, "text": transcript,
                    "result": result, "source": source,
                })
                if self.on_wake_command:
                    try:
                        self.on_wake_command(transcript)
                    except Exception:
                        pass

    def _listen_via_backend(self) -> str:
        """Ruta real: sounddevice -> WAV -> /api/voice/listen (faster-whisper + wake)."""
        wav_path = self._record_wav()
        if not wav_path:
            self.events.put({"type": "mic_error", "text": "sin audio del microfono"})
            return ""
        data = self._stt_via_backend(wav_path)
        try:
            os.remove(wav_path)
        except Exception:
            pass
        if data.get("status") != "ok":
            detail = data.get("error", data.get("stt", {}))
            self.events.put({"type": "stt_error", "text": str(detail)[:120]})
            return ""
        return (data.get("text") or "").strip()

    def _record_wav(self, max_seconds: float = 6.0, silence_rms: float = 0.012) -> Optional[str]:
        """Graba del microfono con sounddevice hasta detectar silencio. WAV 16kHz mono."""
        try:
            import numpy as np
            import sounddevice as sd
        except Exception:
            return None
        rate = 16000
        block = int(rate * 0.25)
        frames: List[Any] = []
        try:
            silent_blocks = 0
            started = False
            deadline = time.time() + max_seconds
            with sd.InputStream(samplerate=rate, channels=1, dtype="int16", blocksize=block) as stream:
                while time.time() < deadline and self.listening:
                    data, _overflowed = stream.read(block)
                    arr = np.asarray(data, dtype=np.float32) / 32768.0
                    rms = float(np.sqrt(np.mean(np.square(arr))))
                    if rms > silence_rms:
                        started = True
                        silent_blocks = 0
                        frames.append(np.asarray(data).copy())
                    elif started:
                        silent_blocks += 1
                        frames.append(np.asarray(data).copy())
                        if silent_blocks >= 3:
                            break
        except Exception:
            return None
        if not frames:
            return None
        try:
            path = os.path.join(tempfile.gettempdir(), f"aura-mic-{int(time.time() * 1000)}.wav")
            with wave.open(path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(rate)
                wf.writeframes(np.concatenate(frames).tobytes())
            return path
        except Exception:
            return None

    def _stt_via_backend(self, wav_path: str) -> Dict[str, Any]:
        """POST del WAV a /api/voice/listen. Devuelve {status, text, detected, command}."""
        try:
            payload = json.dumps({"audio_path": wav_path, "engine": self.stt_engine}).encode()
            req = urllib.request.Request(
                f"{self.backend_base}/api/voice/listen",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read())
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def _simulate_transcript(self) -> str:
        samples = [
            "hey aura, estado del sistema",
            "hey aura, resumen de campañas",
            "hey aura, correos pendientes",
            "hey aura, levantar servicios",
            "hey aura, estado",
            "hey aura, ayuda",
        ]
        if not hasattr(self, '_sim_counter'):
            self._sim_counter = 0
        self._sim_counter += 1
        if self._sim_counter % 8 == 0:
            import random
            return random.choice(samples)
        return ""

    def _is_wake_word(self, text: str) -> bool:
        lower = text.lower()
        return any(w in lower for w in self.wake_words)

    def _extract_command(self, text: str) -> str:
        lower = text.lower()
        if any(g in lower for g in ["estado", "status", "estás", "andas"]):
            return "system_status"
        if any(g in lower for g in ["campañas", "campaign", "marketing", "anuncios"]):
            return "campaign_summary"
        if any(g in lower for g in ["correos", "email", "gmail", "bandeja"]):
            return "email_summary"
        if any(g in lower for g in ["levantar", "start", "iniciar", "arrancar", "servicios"]):
            return "start_services"
        if any(g in lower for g in ["ayuda", "help", "qué puedes"]):
            return "help"
        if any(g in lower for g in ["logs", "registros", "errores"]):
            return "show_logs"
        if any(g in lower for g in ["entrenar", "train", "modelo"]):
            return "start_training"
        return "unknown"

    def execute_command(self, command: str) -> Dict[str, Any]:
        responses = {
            "system_status": {
                "response": "Sistema operativo. Backend activo, servicios estables. CPU: 45%, RAM: 62%.",
                "data": {"cpu": "45%", "ram": "62%", "backend": "active", "frontend": "active"},
            },
            "campaign_summary": {
                "response": "Campañas activas: 3. CTR promedio: 2.4%. Gasto diario: $150. ROI: 3.2x. Mejor campaña: Verano 2024.",
                "data": {"campaigns": 3, "ctr": "2.4%", "spend": "$150", "roi": "3.2x"},
            },
            "email_summary": {
                "response": "Tienes 12 correos no leídos. 2 de alta prioridad. Reunión de equipo en 30 minutos. Cliente XYZ solicitó propuesta.",
                "data": {"unread": 12, "high_priority": 2, "next_meeting": "30 min"},
            },
            "start_services": {
                "response": "Iniciando backend, frontend y HF Space.",
                "data": {"services": ["backend", "frontend", "hf-space"]},
            },
            "show_logs": {
                "response": "Últimos logs: 3 errores en backend, 1 warning en frontend. Todo estable.",
                "data": {"errors": 3, "warnings": 1},
            },
            "start_training": {
                "response": "Entrenamiento iniciado. Modelo: Qwen/Qwen2.5-1.5B. Dataset: training-data.jsonl.",
                "data": {"model": "Qwen/Qwen2.5-1.5B", "dataset": "training-data.jsonl"},
            },
            "help": {
                "response": "Comandos disponibles: estado, campañas, correos, levantar servicios, logs, entrenar, ayuda.",
                "data": {"commands": ["estado", "campañas", "correos", "levantar servicios", "logs", "entrenar", "ayuda"]},
            },
            "unknown": {
                "response": "Comando no reconocido. Próximamente integración con API real.",
                "data": {},
            },
        }
        result = responses.get(command, responses["unknown"])
        self.events.put({"type": "response", "text": result["response"], "data": result.get("data")})
        return result

    def speak(self, text: str) -> None:
        """Encola TTS incremental (no bloquea; el worker habla por frases)."""
        self.events.put({"type": "tts", "text": text})
        try:
            self.tts_stream.enqueue(text)
        except Exception:
            pass

    def get_events(self) -> List[Dict[str, Any]]:
        result = []
        while not self.events.empty():
            try:
                result.append(self.events.get_nowait())
            except queue.Empty:
                break
        return result

    def get_status(self) -> Dict[str, Any]:
        return {
            "listening": self.listening,
            "wake_word": self.wake_word,
            "last_transcript": self.last_transcript,
            "last_command": self.last_command,
            "capabilities": self.get_capabilities(),
            "history_count": len(self.command_history),
        }

    def get_history(self) -> List[Dict[str, Any]]:
        return self.command_history[-10:]
