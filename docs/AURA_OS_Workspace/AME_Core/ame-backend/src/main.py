"""AURA Backend main entrypoint - con integración de Agent Orchestrator."""

from __future__ import annotations

import logging
from typing import Any, Dict, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

# Integrar Agent Orchestrator
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from AURA_Core.agent_orchestrator import get_system_actions, start_orchestrator

# Iniciar el orquestador al arrancar el servidor
start_orchestrator()

logger = logging.getLogger(__name__)

app = FastAPI(title="AURA Backend")

active_ws: Set[WebSocket] = set()


@app.get("/")
def root() -> Dict[str, Any]:
    return {"status": "ok", "service": "aura-backend"}


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok"}


@app.get("/api/status")
def api_status() -> Dict[str, Any]:
    return {
        "bots": [
            {"id": "bot-1", "name": "Roller Miner", "status": "Idle"},
            {"id": "bot-2", "name": "Survey Harvester", "status": "Stopped"},
            {"id": "bot-3", "name": "OSINT Recon", "status": "Stopped"},
        ]
    }


@app.get("/api/balance")
def api_balance() -> Dict[str, Any]:
    return {"total_balance": 0.0, "currency": "USD"}


@app.get("/api/test-sync")
async def api_test_sync() -> Dict[str, Any]:
    """Envía un mensaje de prueba a todos los clientes WebSocket conectados."""
    msg = {
        "type": "UPDATE_STATUS",
        "payload": {"news": "test-news", "stats": "test-stats"},
    }
    for ws in active_ws:
        try:
            await ws.send_json(msg)
        except Exception as exc:
            logger.error("WS send error: %s", exc)
    return {"status": "sent", "clients": len(active_ws)}


@app.get("/api/system/actions")
def api_system_actions() -> JSONResponse:
    """Endpoint para obtener el historial de acciones del orquestador."""
    return JSONResponse(content=get_system_actions())


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    active_ws.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        active_ws.remove(ws)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
