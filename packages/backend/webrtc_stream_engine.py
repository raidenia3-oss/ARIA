"""WebRTC stream engine for AURA - Module 29.

Procesamiento en tiempo real de flujos de audio y video via WebRTC,
deteccion de actividad de voz (VAD) y analisis de fotogramas sin latencia.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from io import BytesIO
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from fastapi import WebSocket

from backend.self_healing import SelfHealingRuntime


class WebRTCSessionState(str, Enum):
    NEW = "new"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    FAILED = "failed"
    CLOSED = "closed"


@dataclass
class IceCandidate:
    candidate: str
    sdp_mid: str
    sdp_mline_index: int

    def to_dict(self) -> Dict[str, Any]:
        return {"candidate": self.candidate, "sdp_mid": self.sdp_mid, "sdp_mline_index": self.sdp_mline_index}


@dataclass
class WebRTCSession:
    session_id: str
    sdp_offer: str
    sdp_answer: str = ""
    ice_candidates: List[Dict[str, Any]] = field(default_factory=list)
    state: str = WebRTCSessionState.NEW.value
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    last_activity: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    frame_count: int = 0
    audio_chunks: int = 0
    vad_events: int = 0

    def touch(self) -> None:
        self.last_activity = datetime.utcnow().isoformat() + "Z"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "state": self.state,
            "ice_candidate_count": len(self.ice_candidates),
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "frame_count": self.frame_count,
            "audio_chunks": self.audio_chunks,
            "vad_events": self.vad_events,
        }


class FrameProcessor:
    """Procesa fotogramas de video con analisis sin latencia (PIL + numpy)."""

    def __init__(self) -> None:
        self._frame_count = 0
        self._processed_count = 0
        self._errors = 0
        self._last_result: Optional[Dict[str, Any]] = None

    def process_frame(self, frame_data: Any) -> Dict[str, Any]:
        self._frame_count += 1
        try:
            raw = self._decode(frame_data)
            from io import BytesIO
            from PIL import Image
            import numpy as np

            img = Image.open(BytesIO(raw))
            arr = np.array(img)
            mean_brightness = float(np.mean(arr)) if arr.size > 0 else 0.0
            std_brightness = float(np.std(arr)) if arr.size > 0 else 0.0

            result = {
                "processed": True,
                "frame_index": self._processed_count,
                "width": img.width,
                "height": img.height,
                "format": img.format or "unknown",
                "mode": img.mode,
                "mean_brightness": round(mean_brightness, 2),
                "std_brightness": round(std_brightness, 2),
                "pixel_count": int(arr.size),
                "processed_at": datetime.utcnow().isoformat() + "Z",
            }
            self._processed_count += 1
            self._last_result = result
            return result
        except ImportError:
            return self._fallback_process(raw if "raw" in dir() else frame_data)
        except Exception as exc:
            self._errors += 1
            return {"processed": False, "error": str(exc), "frame_index": self._frame_count}

    def process_batch(self, frames: List[Any]) -> List[Dict[str, Any]]:
        return [self.process_frame(f) for f in frames]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_frames": self._frame_count,
            "processed": self._processed_count,
            "errors": self._errors,
            "success_rate": round(self._processed_count / max(1, self._frame_count) * 100, 1),
        }

    @staticmethod
    def _decode(frame_data: Any) -> bytes:
        if isinstance(frame_data, str):
            if frame_data.startswith("data:"):
                frame_data = frame_data.split(",", 1)[-1]
            return base64.b64decode(frame_data)
        if isinstance(frame_data, bytes):
            return frame_data
        if isinstance(frame_data, dict):
            raw = frame_data.get("data", "")
            if isinstance(raw, str):
                return base64.b64decode(raw)
        return b""

    def _fallback_process(self, frame_data: Any) -> Dict[str, Any]:
        raw = self._decode(frame_data)
        fmt = "unknown"
        if raw[:3] == b"\xff\xd8\xff":
            fmt = "jpeg"
        elif raw[:8] == b"\x89PNG\r\n\x1a\n":
            fmt = "png"
        elif raw[:6] in (b"GIF87a", b"GIF89a"):
            fmt = "gif"
        self._processed_count += 1
        return {
            "processed": True,
            "format": fmt,
            "size_bytes": len(raw),
            "processed_at": datetime.utcnow().isoformat() + "Z",
        }


class VoiceActivityDetector:
    """Deteccion de actividad de voz (VAD) basada en energia con numpy."""

    def __init__(self, sample_rate: int = 16000, frame_ms: int = 30, energy_threshold: float = 0.01) -> None:
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.energy_threshold = energy_threshold
        self._total_chunks = 0
        self._speech_chunks = 0
        self._silence_chunks = 0
        self._last_speech: float = 0.0

    def is_speech(self, audio_data: Any) -> bool:
        self._total_chunks += 1
        try:
            raw = self._decode_audio(audio_data)
            if not raw:
                self._silence_chunks += 1
                return False

            import numpy as np
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
            if len(samples) == 0:
                self._silence_chunks += 1
                return False

            samples /= 32768.0
            rms = float(np.sqrt(np.mean(samples ** 2)))
            is_speech = rms > self.energy_threshold

            if is_speech:
                self._speech_chunks += 1
                self._last_speech = time.time()
            else:
                self._silence_chunks += 1

            return is_speech
        except ImportError:
            self._silence_chunks += 1
            return False
        except Exception:
            self._silence_chunks += 1
            return False

    def detect_activity(self, audio_chunks: List[Any]) -> Dict[str, Any]:
        results: List[bool] = []
        speech_count = 0
        for chunk in audio_chunks:
            is_sp = self.is_speech(chunk)
            results.append(is_sp)
            if is_sp:
                speech_count += 1
        return {
            "chunks": len(audio_chunks),
            "speech_count": speech_count,
            "silence_count": len(audio_chunks) - speech_count,
            "speech_ratio": round(speech_count / max(1, len(audio_chunks)), 4),
            "results": [{"speech": r} for r in results],
            "detected_at": datetime.utcnow().isoformat() + "Z",
        }

    def get_stats(self) -> Dict[str, Any]:
        total = self._total_chunks
        return {
            "total_chunks": total,
            "speech_chunks": self._speech_chunks,
            "silence_chunks": self._silence_chunks,
            "speech_ratio": round(self._speech_chunks / max(1, total), 4),
            "last_speech_ts": self._last_speech,
        }

    @staticmethod
    def _decode_audio(audio_data: Any) -> bytes:
        if isinstance(audio_data, str):
            if audio_data.startswith("data:"):
                audio_data = audio_data.split(",", 1)[-1]
            return base64.b64decode(audio_data)
        if isinstance(audio_data, bytes):
            return audio_data
        if isinstance(audio_data, dict):
            raw = audio_data.get("data", "")
            if isinstance(raw, str):
                return base64.b64decode(raw)
        return b""


class WebRTCStreamEngine:
    """Motor de stream WebRTC con procesamiento de video/audio y deteccion de VAD."""

    def __init__(self, self_healing: Optional[SelfHealingRuntime] = None) -> None:
        self.sessions: Dict[str, WebRTCSession] = {}
        self.frame_processor = FrameProcessor()
        self.vad = VoiceActivityDetector()
        self.self_healing = self_healing
        self._max_sessions = 100
        self._closed_sessions = 0

    def create_session(self, sdp_offer: str, client_id: str = "") -> WebRTCSession:
        session_id = f"webrtc-{int(time.time() * 1000000)}-{client_id or hashlib.md5(sdp_offer.encode()).hexdigest()[:8]}"
        session = WebRTCSession(
            session_id=session_id,
            sdp_offer=sdp_offer,
        )
        self.sessions[session_id] = session
        if len(self.sessions) > self._max_sessions:
            oldest = min(self.sessions.values(), key=lambda s: s.created_at)
            del self.sessions[oldest.session_id]
            self._closed_sessions += 1
        return session

    def handle_offer(self, sdp_offer: str) -> Dict[str, Any]:
        session = self.create_session(sdp_offer)
        sdp_answer = self._generate_sdp_answer(sdp_offer)
        session.sdp_answer = sdp_answer
        session.state = WebRTCSessionState.CONNECTING.value
        return {
            "session_id": session.session_id,
            "sdp_answer": sdp_answer,
            "state": session.state,
        }

    def handle_ice_candidate(self, session_id: str, candidate: Dict[str, Any]) -> Dict[str, Any]:
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "session_not_found", "session_id": session_id}
        ice = IceCandidate(
            candidate=candidate.get("candidate", ""),
            sdp_mid=candidate.get("sdp_mid", ""),
            sdp_mline_index=candidate.get("sdp_mline_index", 0),
        )
        session.ice_candidates.append(ice.to_dict())
        session.touch()
        if session.state == WebRTCSessionState.CONNECTING.value:
            session.state = WebRTCSessionState.CONNECTED.value
        return {"session_id": session_id, "ice_added": True, "candidate_count": len(session.ice_candidates)}

    def process_frame(self, session_id: str, frame_data: Any) -> Dict[str, Any]:
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "session_not_found"}
        result = self.frame_processor.process_frame(frame_data)
        session.frame_count += 1
        session.touch()
        return {"session_id": session_id, "frame_result": result}

    def process_audio(self, session_id: str, audio_data: Any) -> Dict[str, Any]:
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "session_not_found"}
        is_speech = self.vad.is_speech(audio_data)
        session.audio_chunks += 1
        if is_speech:
            session.vad_events += 1
        session.touch()
        return {
            "session_id": session_id,
            "is_speech": is_speech,
            "audio_chunks": session.audio_chunks,
            "vad_events": session.vad_events,
        }

    def get_status(self) -> Dict[str, Any]:
        active = sum(1 for s in self.sessions.values() if s.state == WebRTCSessionState.CONNECTED.value)
        return {
            "active_sessions": active,
            "total_sessions": len(self.sessions),
            "closed_sessions": self._closed_sessions,
            "frame_processor": self.frame_processor.get_stats(),
            "vad": self.vad.get_stats(),
            "sessions": [s.to_dict() for s in self.sessions.values()],
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    def end_session(self, session_id: str) -> bool:
        session = self.sessions.pop(session_id, None)
        if session:
            session.state = WebRTCSessionState.CLOSED.value
            self._closed_sessions += 1
            return True
        return False

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        session = self.sessions.get(session_id)
        return session.to_dict() if session else None

    @staticmethod
    def _generate_sdp_answer(sdp_offer: str) -> str:
        lines = sdp_offer.splitlines()
        answer_lines: List[str] = []
        for line in lines:
            if line.startswith("a=grp:"):
                answer_lines.append(line.replace("a=grp:LS", "a=grp:SL"))
            elif line.startswith("m="):
                answer_lines.append(line)
            else:
                answer_lines.append(line)
        if not answer_lines:
            answer_lines = ["v=0", "o=- 0 0 IN IP4 0.0.0.0", "s=-", "t=0 0", "m=audio 9 UDP/TLS/RTP/SAVPF 0", "c=IN IP4 0.0.0.0"]
        return "\r\n".join(answer_lines)

    async def websocket_handler(self, websocket: WebSocket) -> None:
        session_id: Optional[str] = None
        try:
            await websocket.accept()
            await websocket.send_json({"type": "ready", "message": "AURA WebRTC signaling ready"})

            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    await websocket.send_json({"type": "error", "error": "invalid_json"})
                    continue

                mtype = msg.get("type", "")

                if mtype == "offer":
                    result = self.handle_offer(msg.get("sdp", ""))
                    session_id = result["session_id"]
                    await websocket.send_json({"type": "answer", "session_id": session_id, "sdp_answer": result["sdp_answer"]})

                elif mtype == "ice":
                    result = self.handle_ice_candidate(msg.get("session_id", ""), msg.get("candidate", {}))
                    await websocket.send_json({"type": "ice_ack", "result": result})

                elif mtype == "frame":
                    result = self.process_frame(msg.get("session_id", ""), msg.get("data"))
                    await websocket.send_json({"type": "frame_result", "result": result})

                elif mtype == "audio":
                    result = self.process_audio(msg.get("session_id", ""), msg.get("data"))
                    await websocket.send_json({"type": "vad_result", "result": result})

                elif mtype == "status":
                    await websocket.send_json({"type": "status", "status": self.get_status()})

                else:
                    await websocket.send_json({"type": "error", "error": f"unknown_type: {mtype}"})

        except Exception as exc:
            if session_id:
                await websocket.send_json({"type": "disconnected", "session_id": session_id, "error": str(exc)})
        finally:
            if session_id:
                self.end_session(session_id)
            await websocket.close()
