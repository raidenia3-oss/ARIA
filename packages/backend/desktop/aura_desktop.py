# -*- coding: utf-8 -*-
"""AURA Desktop — Entry point nativo.

Inicia en paralelo:
  - Backend FastAPI en puerto aleatorio (no 8000)
  - Servidor WebSocket P2P local
  - Frontend PyQt5 nativo
  - Deteccion automatica de LAN

100% local — sin dependencias cloud.
"""
from __future__ import annotations

import os
import sys
import socket
import asyncio
import threading
import logging
import random
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger("AURA.Desktop")

# Colores cyberpunk
BG_DARK = "#0f172a"
PRIMARY = "#38bdf8"
ACCENT = "#ff6b35"
SUCCESS = "#10b981"
FONT = "Courier New"


def find_free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _start_backend(port: int) -> None:
    """Corre uvicorn en background thread."""
    os.environ["AURA_DESKTOP_MODE"] = "1"
    os.environ["AURA_PORT"] = str(port)
    config = uvicorn.Config("backend.main:app", host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    logger.info("Backend FastAPI iniciado en puerto %d", port)
    server.run()


_desktop_app = None


def get_desktop_app() -> FastAPI:
    global _desktop_app
    if _desktop_app is None:
        _desktop_app = FastAPI(title="AURA Desktop API", version="1.0")
        _desktop_app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

        @_desktop_app.websocket("/ws/desktop")
        async def desktop_ws(ws: WebSocket):
            await ws.accept()
            try:
                while True:
                    data = await ws.receive_text()
                    await ws.send_json({"type": "echo", "data": data})
            except WebSocketDisconnect:
                pass

        @_desktop_app.get("/health")
        async def health():
            return {"status": "ok", "mode": "desktop", "port": _backend_port}

    return _desktop_app


_backend_port: int = 0
_backend_thread: threading.Thread | None = None
_p2p_server: asyncio.Server | None = None


def start_p2p_server(port: int = 9000) -> None:
    """Servidor WebSocket P2P en LAN."""
    global _p2p_server

    async def p2p_handler(websocket: WebSocket, path: str):
        await websocket.accept()
        client_id = f"client_{int(time.time() * 1000)}"
        logger.info("P2P client conectado: %s", client_id)
        try:
            while True:
                msg = await websocket.receive_text()
                await websocket.send_json({"type": "p2p_ack", "from": "aura_desktop", "msg_id": client_id})
        except WebSocketDisconnect:
            logger.info("P2P client desconectado: %s", client_id)

    async def run_p2p():
        from starlette.websockets import WebSocket as StarletteWS
        config = uvicorn.Config(get_p2p_app(), host="0.0.0.0", port=port, log_level="warning")
        server = uvicorn.Server(config)
        await server.serve()

    def _run():
        import asyncio as _asyncio
        _asyncio.run(run_p2p())

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    logger.info("P2P servidor iniciado en puerto %d", port)


def get_p2p_app() -> FastAPI:
    app = FastAPI()

    @app.websocket("/ws/p2p")
    async def p2p_ws(ws: WebSocket):
        await ws.accept()
        try:
            while True:
                data = await ws.receive_text()
                await ws.send_json({"type": "p2p_relay", "data": data})
        except WebSocketDisconnect:
            pass

    return app


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def generate_pairing_code() -> str:
    import hmac, hashlib
    secret = os.environ.get("AURA_PAIRING_SECRET", "aura-desktop-2026").encode()
    token = hmac.new(secret, f"{get_local_ip()}:{_backend_port}:{time.time()}".encode(), hashlib.sha256).hexdigest()[:8]
    return token.upper()


def start_desktop() -> None:
    """Punto de entrada principal."""
    global _backend_port, _backend_thread

    _backend_port = find_free_port()
    logger.info("AURA Desktop iniciando...")
    logger.info("IP Local: %s", get_local_ip())
    logger.info("Backend puerto: %d", _backend_port)

    # 1. Backend FastAPI en background
    _backend_thread = threading.Thread(target=_start_backend, args=(_backend_port,), daemon=True)
    _backend_thread.start()
    time.sleep(2)

    # 2. P2P servidor
    start_p2p_server(port=9000)

    # 3. Lanza PyQt5 UI
    launch_ui()


def launch_ui() -> None:
    from frontend.desktop.aura_app import AURADesktopApp
    app = AURADesktopApp(
        backend_port=_backend_port,
        backend_host="127.0.0.1",
        local_ip=get_local_ip(),
        pairing_code=generate_pairing_code(),
    )
    app.run()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(message)s")
    start_desktop()
