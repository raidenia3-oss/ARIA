"""AuraWebRTCClient — Cliente WebRTC de senializacion para AURA.

Se comunica con el backend AURA (signaling-only WebRTC) para:
- Crear sesiones (POST /api/webrtc/offer)
- Enviar ICE candidates (POST /api/webrtc/ice-candidates)
- Transmitir audio (POST /api/webrtc/audio)
- Transmitir video/fotogramas (POST /api/webrtc/frame)
- Consultar estado (GET /api/webrtc/status)
- Conectar via WebSocket (WS /api/webrtc/ws/{session_id})
"""

from __future__ import annotations

import asyncio
import base64
import json
import queue
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

try:
    import pyaudio
except ImportError:
    pyaudio = None

try:
    import websockets
except ImportError:
    websockets = None

from frontend.webrtc.aura_webrtc_utils import (
    AudioConfig,
    IceCandidate,
    VoiceStateManager,
    create_audio_config,
    generate_ice_candidate,
    generate_sdp_offer,
    list_audio_devices,
    parse_sdp_answer,
    audio_chunk_to_base64,
    base64_to_audio_chunk,
    rms_energy,
)


DEFAULT_BASE_URL = "http://localhost:8000"


@dataclass
class WebRTCConfig:
    base_url: str = DEFAULT_BASE_URL
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    voice_threshold: float = 500.0
    audio_config: AudioConfig = field(default_factory=create_audio_config)


class AuraWebRTCClient:
    """Cliente WebRTC de senializacion para AURA."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")
        self.session_id: Optional[str] = None
        self.sdp_answer: Optional[str] = None
        self._voice_state = VoiceStateManager()
        self._websocket = None
        self._connected = False
        self._audio_devices = list_audio_devices()
        self.tts_chunk_queue: "queue.Queue[bytes]" = queue.Queue()
        self._audio_ws_task: Optional[Any] = None

    @property
    def is_connected(self) -> bool:
        return self._connected and self.session_id is not None

    @property
    def voice_state(self) -> str:
        return self._voice_state.current_state

    def set_voice_state(self, state: str) -> str:
        return self._voice_state.set_state(state)

    def get_audio_devices(self) -> List[Dict[str, Any]]:
        return list(self._audio_devices)

    async def create_session(self) -> Dict[str, Any]:
        """Crea una sesion WebRTC enviando un SDP offer al servidor."""
        offer = generate_sdp_offer()
        self.session_id = offer.session_id
        payload = {"sdp_offer": offer.sdp, "client_id": "aura_cli"}
        try:
            resp = requests.post(f"{self.base_url}/api/webrtc/offer", json=payload, timeout=10)
            resp.raise_for_status()
            result = resp.json()
            self.sdp_answer = result.get("sdp_answer")
            self._connected = True
            return {
                "session_id": self.session_id,
                "sdp_answer": self.sdp_answer,
                "state": result.get("state", "created"),
                "ice_servers": result.get("ice_servers", []),
            }
        except requests.RequestException as exc:
            self._connected = False
            raise ConnectionError(f"Error creating WebRTC session: {exc}")

    async def send_ice_candidate(self, candidate: Optional[IceCandidate] = None) -> Dict[str, Any]:
        """Envia un ICE candidate al servidor para conexion."""
        if not self.session_id:
            raise ConnectionError("No active WebRTC session")
        ice = candidate or generate_ice_candidate()
        payload = {"session_id": self.session_id, "candidate": ice.to_dict()}
        try:
            resp = requests.post(f"{self.base_url}/api/webrtc/ice-candidates", json=payload, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            raise ConnectionError(f"Error sending ICE candidate: {exc}")

    async def send_audio_chunk(self, audio_data: bytes) -> Dict[str, Any]:
        """Envia un chunk de audio PCM al servidor para procesamiento VAD."""
        if not self.session_id:
            raise ConnectionError("No active WebRTC session")
        voice_state = self._voice_state.update(audio_data)
        payload = {"session_id": self.session_id, "data": audio_chunk_to_base64(audio_data)}
        try:
            resp = requests.post(f"{self.base_url}/api/webrtc/audio", json=payload, timeout=10)
            resp.raise_for_status()
            result = resp.json()
            return {"voice_state": voice_state, **result}
        except requests.RequestException as exc:
            raise ConnectionError(f"Error sending audio chunk: {exc}")

    async def send_video_frame(self, frame_data: bytes, width: int = 640, height: int = 480) -> Dict[str, Any]:
        """Envia un frame de video al servidor."""
        if not self.session_id:
            raise ConnectionError("No active WebRTC session")
        payload = {
            "session_id": self.session_id,
            "data": audio_chunk_to_base64(frame_data),
            "width": width,
            "height": height,
        }
        try:
            resp = requests.post(f"{self.base_url}/api/webrtc/frame", json=payload, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            raise ConnectionError(f"Error sending video frame: {exc}")

    async def get_status(self) -> Dict[str, Any]:
        """Consulta el estado de la sesion WebRTC."""
        try:
            params = {"session_id": self.session_id} if self.session_id else {}
            resp = requests.get(f"{self.base_url}/api/webrtc/status", params=params, timeout=5)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException:
            return {"status": "disconnected", "connected": False}

    async def connect_websocket(self, on_message=None) -> None:
        """Conecta via WebSocket para signaling bidireccional."""
        if not self.session_id:
            raise ConnectionError("No active WebRTC session — call create_session() first")
        if websockets is None:
            raise ImportError("websockets library is required for WebSocket connections")
        ws_url = f"ws://{self.base_url.replace('http://', '').replace('https://', '')}/api/webrtc/ws/{self.session_id}"
        async with websockets.connect(ws_url) as ws:
            self._websocket = ws
            await ws.send(json.dumps({"type": "status"}))
            while True:
                try:
                    raw = await ws.recv()
                    msg = json.loads(raw)
                    if on_message:
                        on_message(msg)
                except (websockets.ConnectionClosed, json.JSONDecodeError):
                    break

    async def connect_audio_websocket(self, on_tts_chunk=None) -> None:
        """Conecta al WebSocket bidireccional de audio para STT/TTS."""
        if not self.session_id:
            raise ConnectionError("No active WebRTC session")
        if websockets is None:
            raise ImportError("websockets library is required for WebSocket connections")
        ws_url = f"ws://{self.base_url.replace('http://', '').replace('https://', '')}/ws/webrtc/audio/{self.session_id}"
        try:
            async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as ws:
                self._audio_ws = ws
                async def _send_audio():
                    while True:
                        chunk = await asyncio.get_event_loop().run_in_executor(None, self.tts_chunk_queue.get)
                        if chunk:
                            await ws.send(json.dumps({"type": "tts", "data": audio_chunk_to_base64(chunk)}))
                asyncio.create_task(_send_audio())
                while True:
                    try:
                        raw = await ws.recv()
                        msg = json.loads(raw)
                        if msg.get("type") == "audio" and on_tts_chunk:
                            chunk = base64_to_audio_chunk(msg.get("data", ""))
                            if chunk:
                                on_tts_chunk(chunk)
                    except (websockets.ConnectionClosed, json.JSONDecodeError):
                        break
        except Exception:
            pass

    def end_session(self) -> Dict[str, Any]:
        """Cierra la sesion WebRTC actual."""
        if self.session_id:
            session_id = self.session_id
            self.session_id = None
            self.sdp_answer = None
            self._connected = False
            return {"status": "ended", "session_id": session_id}
        return {"status": "no_active_session"}


class VoiceStreamingEngine:
    """Captura de audio en hilo separado para streaming WebRTC."""

    def __init__(self, client: AuraWebRTCClient, audio_config: Optional[AudioConfig] = None) -> None:
        self.client = client
        self.config = audio_config or create_audio_config()
        self._stream = None
        self._pa = None
        self._running = False
        self._thread: Optional[Any] = None

    def start(self) -> None:
        if self._running or pyaudio is None:
            return
        self._pa = pyaudio.PyAudio()
        self._stream = self._pa.open(
            format=self.config.format,
            channels=self.config.channels,
            rate=self.config.sample_rate,
            input=True,
            frames_per_buffer=self.config.chunk_size,
        )
        self._running = True
        import threading
        self._thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        if self._pa:
            self._pa.terminate()
            self._pa = None
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None

    def _stream_loop(self) -> None:
        import asyncio
        while self._running:
            try:
                data = self._stream.read(self.config.chunk_size, exception_on_overflow=False)
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(self.client.send_audio_chunk(data))
                finally:
                    loop.close()
            except Exception:
                pass
            time.sleep(0.01)


class VoiceStreamingEngine:
    """Captura de audio en hilo separado para streaming WebRTC."""

    def __init__(self, client: AuraWebRTCClient, audio_config: Optional[AudioConfig] = None) -> None:
        self.client = client
        self.config = audio_config or create_audio_config()
        self._stream = None
        self._pa = None
        self._running = False
        self._thread: Optional[Any] = None
        self._output_stream = None
        self._output_pa = None
        self._tts_thread: Optional[Any] = None

    def start(self) -> None:
        if self._running or pyaudio is None:
            return
        self._pa = pyaudio.PyAudio()
        self._stream = self._pa.open(
            format=self.config.format,
            channels=self.config.channels,
            rate=self.config.sample_rate,
            input=True,
            frames_per_buffer=self.config.chunk_size,
        )
        self._output_pa = pyaudio.PyAudio()
        self._output_stream = self._output_pa.open(
            format=self.config.format,
            channels=self.config.channels,
            rate=self.config.sample_rate,
            output=True,
            frames_per_buffer=self.config.chunk_size,
        )
        self._running = True
        self._thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._thread.start()
        self._tts_thread = threading.Thread(target=self._tts_listener_loop, daemon=True)
        self._tts_thread.start()

    def stop(self) -> None:
        self._running = False
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        if self._pa:
            self._pa.terminate()
            self._pa = None
        if self._output_stream:
            self._output_stream.stop_stream()
            self._output_stream.close()
            self._output_stream = None
        if self._output_pa:
            self._output_pa.terminate()
            self._output_pa = None
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None
        if self._tts_thread:
            self._tts_thread.join(timeout=3)
            self._tts_thread = None

    def _stream_loop(self) -> None:
        import asyncio
        while self._running:
            try:
                data = self._stream.read(self.config.chunk_size, exception_on_overflow=False)
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(self.client.send_audio_chunk(data))
                finally:
                    loop.close()
            except Exception:
                pass
            time.sleep(0.01)

    def _tts_listener_loop(self) -> None:
        while self._running:
            try:
                chunk = self.client.tts_chunk_queue.get(timeout=1)
                if self._output_stream and chunk:
                    try:
                        self._output_stream.write(chunk)
                    except Exception:
                        pass
            except Exception:
                pass

    def enqueue_tts_chunk(self, chunk: bytes) -> None:
        self.client.tts_chunk_queue.put(chunk)
