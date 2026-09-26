"""Utility functions for AURA WebRTC client — Module 30 frontend integration.

Funciones de utilidad para signaling WebRTC (signaling-only, sin aiortc),
captura de audio con PyAudio, y gestion de estados de voz.
Disenadas para trabajar con el backend AURA en http://localhost:8000/api/webrtc/.
"""

from __future__ import annotations

import base64
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np

try:
    import pyaudio
except ImportError:
    pyaudio = None

try:
    import websockets
except ImportError:
    websockets = None


SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 960
FORMAT = pyaudio.paInt16 if pyaudio else 8
FRAME_WIDTH = 2


@dataclass
class WebRTCSignal:
    sdp: str
    type: str
    session_id: str
    sdp_version: str = "0"

    def to_dict(self) -> Dict[str, Any]:
        return {"sdp": self.sdp, "type": self.type, "session_id": self.session_id}


@dataclass
class IceCandidate:
    candidate: str
    sdp_mid: str
    sdp_mline_index: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate": self.candidate,
            "sdp_mid": self.sdp_mid,
            "sdp_mline_index": self.sdp_mline_index,
        }


@dataclass
class AudioConfig:
    sample_rate: int = SAMPLE_RATE
    channels: int = CHANNELS
    chunk_size: int = CHUNK_SIZE
    format: int = FORMAT


class VoiceStateManager:
    """Gestiona estados de voz: Listening, Processing, Speaking."""

    STATES = ("listening", "processing", "speaking")

    def __init__(self, threshold: float = 500.0) -> None:
        self.threshold = threshold
        self.current_state: str = "listening"
        self._last_change: float = time.time()

    def update(self, audio_chunk: bytes) -> str:
        energy = rms_energy(audio_chunk)
        now = time.time()
        if energy > self.threshold:
            self.current_state = "speaking"
        elif self.current_state == "speaking":
            self.current_state = "processing"
            self._last_change = now
        elif self.current_state == "processing" and now - self._last_change > 0.5:
            self.current_state = "listening"
        return self.current_state


def generate_sdp_offer(session_id: str = "") -> WebRTCSignal:
    """Genera un SDP offer para signaling (signaling-only, sin aiortc)."""
    if not session_id:
        session_id = str(uuid.uuid4())
    sdp = (
        "v=0\r\n"
        f"o=- {int(time.time())} 1 IN IP4 0.0.0.0\r\n"
        "s=AURA-WebRTC\r\n"
        "t=0 0\r\n"
        "m=audio 9 UDP/TLS/RTP/SAVPF 0\r\n"
        "c=IN IP4 0.0.0.0\r\n"
        "a=rtpmap:0 PCMU/8000\r\n"
    )
    return WebRTCSignal(sdp=sdp, type="offer", session_id=session_id)


def generate_ice_candidate(sdp_mid: str = "audio", sdp_mline_index: int = 0) -> IceCandidate:
    """Genera un ICE candidate para signaling (sin STUN/TURN)."""
    candidate = "candidate:0 1 UDP 2122252031 0.0.0.0 0 typ host"
    return IceCandidate(candidate=candidate, sdp_mid=sdp_mid, sdp_mline_index=sdp_mline_index)


def parse_sdp_answer(sdp_answer: str) -> Dict[str, Any]:
    """Parsea un SDP answer del servidor."""
    lines = sdp_answer.strip().split("\r\n")
    result: Dict[str, Any] = {"lines": lines, "media": [], "session": {}}
    current_media: Optional[Dict[str, Any]] = None
    for line in lines:
        parts = line.split(" ", 1)
        if not parts:
            continue
        key = parts[0]
        value = parts[1] if len(parts) > 1 else ""
        if key.startswith("m="):
            if current_media:
                result["media"].append(current_media)
            current_media = {"type": "audio", "line": line}
        elif key.startswith("a="):
            if current_media:
                attr_key = value.split(":")[0] if ":" in value else value
                current_media[attr_key] = value
            else:
                result["session"][key] = value
    if current_media:
        result["media"].append(current_media)
    return result


def audio_chunk_to_base64(chunk: bytes) -> str:
    """Codifica un chunk de audio PCM a base64 para transmision."""
    return base64.b64encode(chunk).decode("ascii")


def base64_to_audio_chunk(b64_data: str) -> bytes:
    """Decodifica base64 a chunk de audio PCM."""
    return base64.b64decode(b64_data)


def rms_energy(pcm_data: bytes) -> float:
    """Calcula la energia RMS de un chunk de audio PCM int16."""
    samples = np.frombuffer(pcm_data, dtype=np.int16)
    if len(samples) == 0:
        return 0.0
    return float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))


def create_audio_config(
    sample_rate: int = SAMPLE_RATE,
    channels: int = CHANNELS,
    chunk_size: int = CHUNK_SIZE,
) -> AudioConfig:
    """Crea una configuracion de audio para captura."""
    fmt = pyaudio.paInt16 if pyaudio else FORMAT
    return AudioConfig(sample_rate=sample_rate, channels=channels, chunk_size=chunk_size, format=fmt)


def list_audio_devices() -> List[Dict[str, Any]]:
    """Lista dispositivos de audio de entrada disponibles usando PyAudio."""
    if pyaudio is None:
        return []
    pa = pyaudio.PyAudio()
    devices: List[Dict[str, Any]] = []
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if info.get("maxInputChannels", 0) > 0:
            devices.append({
                "index": i,
                "name": info.get("name", ""),
                "max_input_channels": int(info.get("maxInputChannels", 0)),
                "sample_rate": int(info.get("defaultSampleRate", 0)),
            })
    pa.terminate()
    return devices


def create_default_config() -> AudioConfig:
    return create_audio_config()
