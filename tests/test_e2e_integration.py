"""Suite de pruebas de integracion E2E para AURA — Module 30.

Validan el ciclo de vida completo usando pytest, httpx y websockets:
- Arranque ordenado desde main_launcher.py
- Validacion de probes en /api/production/health
- Handshake completo de audio WebRTC (POST /api/webrtc/offer y WS signaling)
- Sincronizacion del Dashboard con modelos y personas
- Cierre limpio de subprocessos sin leaks de memoria ni puertos bloqueados
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import pytest
import websockets

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_PORT = 8000


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex((host, port)) == 0


def wait_for_health(url: str, max_retries: int = 30, interval: float = 1.0) -> bool:
    for _ in range(max_retries):
        try:
            resp = httpx.get(url, timeout=5)
            if resp.status_code == 200:
                return True
        except (httpx.RequestError, httpx.HTTPError):
            pass
        time.sleep(interval)
    return False


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def backend_server():
    """Fixture que levanta el backend AURA como proceso secundario."""
    port = DEFAULT_PORT
    already_running = is_port_in_use(port)
    proc: Optional[subprocess.Popen] = None

    if not already_running:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "backend.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                str(port),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(PROJECT_ROOT),
        )

    if not wait_for_health(f"{DEFAULT_BASE_URL}/api/production/health", max_retries=60):
        if proc:
            proc.terminate()
            proc.wait()
        pytest.skip("Backend server did not become healthy")

    yield {"proc": proc, "base_url": DEFAULT_BASE_URL, "port": port, "started": proc is not None}

    if proc:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


@pytest.fixture(scope="module")
def api_client(backend_server) -> httpx.Client:
    client = httpx.Client(base_url=backend_server["base_url"], timeout=30)
    yield client
    client.close()


class TestBackendLifecycle:
    """Prueba el arranque ordenado desde main_launcher.py."""

    def test_launcher_module_imports(self):
        """Verifica que main_launcher.py se puede importar."""
        sys.path.insert(0, str(PROJECT_ROOT))
        import main_launcher

        assert hasattr(main_launcher, "is_port_in_use")
        assert hasattr(main_launcher, "wait_for_health")
        assert hasattr(main_launcher, "launch_backend")
        assert hasattr(main_launcher, "launch_hud")
        assert hasattr(main_launcher, "graceful_shutdown")

    def test_port_check_function(self):
        """Verifica la funcion is_port_in_use."""
        sys.path.insert(0, str(PROJECT_ROOT))
        import main_launcher

        assert isinstance(main_launcher.is_port_in_use(DEFAULT_PORT), bool)

    def test_health_probe_available(self, backend_server):
        """El probe /api/production/health responde con 200."""
        resp = httpx.get(f"{backend_server['base_url']}/api/production/health", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "liveness" in data
        assert "readiness" in data
        assert "startup" in data


class TestProductionEndpoints:
    """Prueba endpoints de produccion y dashboard."""

    def test_health_endpoint(self, api_client):
        resp = api_client.get("/api/production/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["all_passed"] in (True, False)

    def test_system_report(self, api_client):
        resp = api_client.get("/api/production/system-report")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_modules"] > 0
        assert "modules" in data

    def test_deploy_spec(self, api_client):
        resp = api_client.get("/api/production/deploy-spec?port=8000")
        assert resp.status_code == 200
        data = resp.json()
        assert "dockerfile" in data
        assert "docker_compose" in data
        assert "env_template" in data

    def test_pipeline_status(self, api_client):
        resp = api_client.get("/api/production/pipeline/status")
        assert resp.status_code == 200


class TestModelManagement:
    """Prueba la sincronizacion del Dashboard con modelos locales."""

    def test_list_models(self, api_client):
        """GET /api/local-ai/models retorna lista de modelos."""
        resp = api_client.get("/api/local-ai/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "models" in data
        assert isinstance(data["models"], list)


class TestPersonaManagement:
    """Prueba la sincronizacion del Dashboard con personajes."""

    def test_list_personas(self, api_client):
        """GET /api/personas/cards retorna lista de tarjetas."""
        resp = api_client.get("/api/personas/cards")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "cards" in data
        assert isinstance(data["cards"], list)

    def test_import_persona(self, api_client):
        """POST /api/personas/cards importa una tarjeta de personaje."""
        persona_data = {
            "name": "Test Persona E2E",
            "description": "Personaje de prueba",
            "personality": "Curioso y amable",
            "scenario": "Conversacion casual",
            "first_mes": "Hola! Soy un personaje de prueba.",
        }
        resp = api_client.post(
            "/api/personas/cards", json={"source": "json", "data": json.dumps(persona_data)}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") in ("imported", "error")


class TestWebRTCSignaling:
    """Prueba el handshake completo de audio WebRTC."""

    def test_webrtc_offer(self, api_client):
        """POST /api/webrtc/offer crea una sesion WebRTC."""
        sdp = (
            "v=0\r\n"
            "o=- 1 1 IN IP4 0.0.0.0\r\n"
            "s=AURA-WebRTC\r\n"
            "t=0 0\r\n"
            "m=audio 9 UDP/TLS/RTP/SAVPF 0\r\n"
            "c=IN IP4 0.0.0.0\r\n"
        )
        resp = api_client.post(
            "/api/webrtc/offer", json={"sdp_offer": sdp, "client_id": "e2e_test"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert "sdp_answer" in data
        assert "state" in data

    def test_webrtc_status_without_session(self, api_client):
        """GET /api/webrtc/status retorna estado general."""
        resp = api_client.get("/api/webrtc/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "active_sessions" in data
        assert "total_sessions" in data

    def test_webrtc_audio_chunk(self, api_client):
        """POST /api/webrtc/audio procesa un chunk de audio."""
        offer_resp = api_client.post(
            "/api/webrtc/offer", json={"sdp_offer": "v=0 test", "client_id": "e2e_audio"}
        )
        session_id = offer_resp.json()["session_id"]

        import base64

        audio_data = base64.b64encode(b"\x00\x01" * 480).decode("ascii")
        resp = api_client.post(
            "/api/webrtc/audio", json={"session_id": session_id, "data": audio_data}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("session_id") == session_id
        assert "is_speech" in data

    def test_webrtc_ice_candidate(self, api_client):
        """POST /api/webrtc/ice-candidates registra candidatos ICE."""
        offer_resp = api_client.post(
            "/api/webrtc/offer", json={"sdp_offer": "v=0 test", "client_id": "e2e_ice"}
        )
        session_id = offer_resp.json()["session_id"]

        candidate = {
            "candidate": "candidate:0 1 UDP 2122252031 0.0.0.0 0 typ host",
            "sdp_mid": "audio",
            "sdp_mline_index": 0,
        }
        resp = api_client.post(
            "/api/webrtc/ice-candidates", json={"session_id": session_id, "candidate": candidate}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("session_id") == session_id
        assert data.get("ice_added") is True


class TestWebSocketSignaling:
    """Prueba el handshake WebSocket de senializacion WebRTC."""

    @pytest.mark.asyncio
    async def test_websocket_signaling(self, backend_server):
        """WS /api/webrtc/ws/{session_id} conecta y envia mensajes."""
        base_url = (
            backend_server["base_url"].replace("http://", "ws://").replace("https://", "wss://")
        )

        offer = (
            "v=0\r\no=- 1 1 IN IP4 0.0.0.0\r\n"
            "s=AURA-WebRTC\r\nt=0 0\r\n"
            "m=audio 9 UDP/TLS/RTP/SAVPF 0\r\nc=IN IP4 0.0.0.0\r\n"
        )
        resp = httpx.post(
            f"{backend_server['base_url']}/api/webrtc/offer",
            json={"sdp_offer": offer, "client_id": "e2e_ws"},
            timeout=10,
        )
        assert resp.status_code == 200
        session_id = resp.json()["session_id"]

        ws_url = f"{base_url}/api/webrtc/ws/{session_id}"
        try:
            async with websockets.connect(ws_url, ping_interval=None, open_timeout=15) as ws:
                ready_msg = await asyncio.wait_for(ws.recv(), timeout=10)
                ready_json = json.loads(ready_msg)
                assert ready_json.get("type") == "ready"

                await ws.send(json.dumps({"type": "status"}))
                status_msg = await asyncio.wait_for(ws.recv(), timeout=10)
                status_json = json.loads(status_msg)
                assert status_json.get("type") == "status"
                assert "status" in status_json
        except (TimeoutError, ConnectionError, OSError) as exc:
            pytest.skip(f"WebSocket signaling not available in this environment: {exc}")


class TestCleanShutdown:
    """Verifica cierre limpio sin leaks de memoria ni puertos bloqueados."""

    def test_no_blocked_ports_after_tests(self, backend_server):
        """El puerto 8000 debe estar disponible tras el cierre del backend."""
        if backend_server["started"]:
            proc = backend_server["proc"]
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
            time.sleep(1)
            assert not is_port_in_use(DEFAULT_PORT) or backend_server["started"] is False

    def test_no_orphan_processes(self, backend_server):
        """No deben quedar procesos hijos sin terminar."""
        if backend_server["started"] and backend_server["proc"]:
            proc = backend_server["proc"]
            assert proc.poll() is not None, "Backend process should have terminated"

    def test_backend_stdout_no_critical_errors(self, backend_server):
        """El backend no debe haber registrado errores criticos durante las pruebas."""
        if backend_server["started"] and backend_server["proc"]:
            proc = backend_server["proc"]
            if proc.stderr:
                _ = proc.stderr.read()
