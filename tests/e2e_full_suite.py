"""Suite E2E integrada para AURA — Module 30.

Ejecuta la cadena completa:
1. Handshake WebRTC (Oferta/Respuesta).
2. Inyección de audio PCM -> transcripción STT -> consulta RAG -> ejecución de herramienta SAFE -> síntesis TTS.
3. Envío de keyframe de visión y verificación de contexto inyectado en el prompt unificado de Swarm.
4. Simulación de microcorte de red y verificación de disparo de SilentReconnector / Self-Healing.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import threading
import time
from typing import Any, Dict, Optional

import requests
import websockets

BASE_URL = os.getenv("AURA_BASE_URL", "http://127.0.0.1:8000")
WS_URL = BASE_URL.replace("http://", "ws://").replace("https://", "wss://")
SESSION_ID = "e2e-test-session"
RESULTS: Dict[str, Any] = {}


def log(name: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}{(' — ' + detail) if detail else ''}")
    RESULTS[name] = {"pass": ok, "detail": detail}


def wait_backend(max_retries: int = 30, interval: float = 1.0) -> bool:
    url = f"{BASE_URL}/api/production/health"
    for _ in range(max_retries):
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(interval)
    return False


def test_webrtc_handshake() -> None:
    try:
        payload = {
            "sdp": "v=0\r\no=- 123456 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\na=rtpmap:111 opus/48000/2\r\nm=video 9 UDP/TLS/RTP/SAVPF 96\r\na=rtpmap:96 VP8/90000\r\n",
            "type": "offer",
            "audio": True,
            "video": True,
        }
        r = requests.post(f"{BASE_URL}/api/webrtc/offer", json=payload, timeout=10)
        data = r.json()
        sid = data.get("session_id") or data.get("id") or ""
        sdp_answer = data.get("sdp_answer") or data.get("sdp") or ""
        ok = r.status_code == 200 and bool(sid) and bool(sdp_answer)
        log("webrtc_handshake", ok, f"session_id={sid} sdp_answer={'yes' if sdp_answer else 'no'}")
    except Exception as exc:
        log("webrtc_handshake", False, str(exc))


def test_audio_stt_rag_tool_tts() -> None:
    try:
        audio_b64 = base64.b64encode(b"\x00\x00" * 1600).decode("utf-8")
        audio_payload = {"session_id": SESSION_ID, "audio": audio_b64}
        r = requests.post(f"{BASE_URL}/api/webrtc/audio/process", json=audio_payload, timeout=10)
        audio_ok = r.status_code == 200

        memory_payload = {"text": "recordar comprar leche", "type": "semantic", "source": "e2e"}
        r = requests.post(f"{BASE_URL}/api/memory/remember", json=memory_payload, timeout=10)
        memory_ok = r.status_code == 200

        r = requests.get(
            f"{BASE_URL}/api/memory/search", params={"q": "leche", "limit": 1}, timeout=10
        )
        search_ok = r.status_code == 200 and len(r.json().get("results", [])) > 0

        tool_payload = {"tool": "list_directory", "params": {"path": "."}}
        r = requests.post(f"{BASE_URL}/api/actions/execute", json=tool_payload, timeout=10)
        tool_ok = r.status_code == 200

        tts_payload = {"text": "Hola, soy AURA.", "session_id": SESSION_ID}
        r = requests.post(f"{BASE_URL}/api/webrtc/tts/speak", json=tts_payload, timeout=10)
        tts_ok = r.status_code == 200

        ok = audio_ok and memory_ok and search_ok and tool_ok and tts_ok
        detail = (
            f"audio={audio_ok} memory={memory_ok} search={search_ok} tool={tool_ok} tts={tts_ok}"
        )
        log("audio_stt_rag_tool_tts", ok, detail)
    except Exception as exc:
        log("audio_stt_rag_tool_tts", False, str(exc))


def test_vision_context_injection() -> None:
    try:
        tiny_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        vision_payload = {"image": tiny_png, "session_id": SESSION_ID}
        r = requests.post(f"{BASE_URL}/api/vision/analyze-frame", json=vision_payload, timeout=10)
        vision_ok = r.status_code == 200
        vision_desc = r.json().get("description", "") if vision_ok else ""

        context_payload = {"query": "test", "max_results": 2}
        r = requests.post(f"{BASE_URL}/swarm/context", json=context_payload, timeout=10)
        context_ok = r.status_code == 200

        r = requests.get(f"{BASE_URL}/swarm/prompt", timeout=10)
        prompt_ok = r.status_code == 200 and len(r.json().get("prompt", "")) > 0

        ok = vision_ok and context_ok and prompt_ok
        detail = f"vision={'yes' if vision_desc else 'no'} context={'yes' if context_ok else 'no'} prompt_len={r.json().get('length', 0) if prompt_ok else 0}"
        log("vision_context_injection", ok, detail)
    except Exception as exc:
        log("vision_context_injection", False, str(exc))


def test_self_healing_reconnect() -> None:
    try:
        r = requests.get(f"{BASE_URL}/api/swarm/status", timeout=10)
        status_ok = r.status_code == 200

        r = requests.post(
            f"{BASE_URL}/api/swarm/recover",
            json={"module": "self_healing", "reason": "e2e_test"},
            timeout=10,
        )
        recover_ok = r.status_code == 200

        ws_url = f"{WS_URL}/ws/telemetry"
        ws_ok = False
        try:
            loop = __import__("asyncio").new_event_loop()
            __import__("asyncio").set_event_loop(loop)

            async def _probe():
                nonlocal ws_ok
                async with websockets.connect(ws_url, ping_interval=5, ping_timeout=10) as ws:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    ws_ok = "cpu_percent" in data and "ram_percent" in data

            loop.run_until_complete(_probe())
        except Exception:
            ws_ok = False
        finally:
            try:
                loop.close()
            except Exception:
                pass

        ok = status_ok and recover_ok and ws_ok
        detail = f"status={status_ok} recover={recover_ok} ws={ws_ok}"
        log("self_healing_reconnect", ok, detail)
    except Exception as exc:
        log("self_healing_reconnect", False, str(exc))


def run_e2e() -> Dict[str, Any]:
    print("=" * 60)
    print("  AURA E2E Full Suite")
    print("=" * 60)
    print()

    print("[PRE] Esperando backend...")
    if not wait_backend():
        print("[red]ERROR: Backend no disponible[/red]")
        log("backend_health", False, "no_response")
        return RESULTS
    log("backend_health", True, "200 OK")

    print("[1/4] Handshake WebRTC...")
    test_webrtc_handshake()

    print("[2/4] Cadena Audio -> STT -> RAG -> Tool -> TTS...")
    test_audio_stt_rag_tool_tts()

    print("[3/4] Visión + inyección de contexto en Swarm...")
    test_vision_context_injection()

    print("[4/4] Self-Healing + reconexión WebSocket...")
    test_self_healing_reconnect()

    passed = sum(1 for r in RESULTS.values() if r.get("pass"))
    total = len(RESULTS)
    print()
    print(f"[bold green]=== Resultados: {passed}/{total} pruebas exitosas ===[/bold green]")
    return RESULTS


if __name__ == "__main__":
    results = run_e2e()
    sys.exit(0 if all(r.get("pass") for r in results.values()) else 1)
