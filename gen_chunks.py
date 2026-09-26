#!/usr/bin/env python3
"""Generador de los chunks de AURA OS."""
import pathlib

# *****************************************************************************
# CHUNK 2: ws_routes.py (200 líneas)
# *****************************************************************************
ws_routes = r'''# -*- coding: utf-8 -*-
"""AURA OS — Chunk 2: WebSocket Routes.

Streaming de eventos en tiempo real vía WebSocket.
Endpoint: /ws/core/events

Emite eventos del EventBus a clientes conectados.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.core.event_bus import CoreEvent, EventBus, EventType, get_event_bus

logger = logging.getLogger("AURA.WSRoutes")

router = APIRouter(tags=["websocket"])

# Conexiones activas
_active_connections: List[WebSocket] = []


def _build_event_payload(event: CoreEvent) -> Dict[str, Any]:
    """Convierte un CoreEvent a payload JSON para WebSocket."""
    return {
        "type": event.type.value if hasattr(event.type, "value") else str(event.type),
        "data": event.data,
        "agent": event.agent,
        "status": event.status,
        "timestamp": event.timestamp,
        "event_id": event.event_id,
    }


def _subscribe_to_bus() -> None:
    """Suscribe al EventBus para reenvío a WS clients."""
    bus = get_event_bus()

    def _forward(event: CoreEvent) -> None:
        """Reenvía evento a todos los clientes WS conectados."""
        payload = _build_event_payload(event)
        disconnected = []
        for ws in _active_connections:
            try:
                # Enviar de forma async en tarea separada
                asyncio.create_task(ws.send_json(payload))
            except Exception as exc:
                logger.warning(f"WS forward failed: {exc}")
                disconnected.append(ws)
        # Limpiar conexiones rotas
        for ws in disconnected:
            if ws in _active_connections:
                _active_connections.remove(ws)

    # Suscribirse a todos los tipos de eventos relevantes
    for event_type in [
        EventType.INPUT,
        EventType.THOUGHT,
        EventType.DECISION,
        EventType.ACTION,
        EventType.AGENT_START,
        EventType.AGENT_END,
        EventType.RESULT,
        EventType.PROGRESS,
        EventType.ERROR,
        EventType.COMPLETE,
    ]:
        bus.subscribe(event_type.value, _forward)

    logger.info("WSRoutes: Subscrito al EventBus para reenvío a clientes")


# Inicializar suscripción al cargar el módulo
_subscribe_done = False


def _ensure_subscribed() -> None:
    """Asegura que el reenvío esté suscrito (solo una vez)."""
    global _subscribe_done
    if not _subscribe_done:
        _subscribe_to_bus()
        _subscribe_done = True


@router.websocket("/ws/core/events")
async def websocket_events(websocket: WebSocket) -> None:
    """Endpoint WebSocket para streaming de eventos en tiempo real.
    
    El cliente puede enviar mensajes para:
    - "subscribe:<event_type>" — suscribirse a un tipo específico
    - "unsubscribe:<event_type>" — dejar de recibir un tipo
    - "ping" — response: "pong"
    
    Se reciben eventos del EventBus automáticamente.
    """
    await websocket.accept()
    _ensure_subscribed()
    _active_connections.append(websocket)
    client_id = f"ws_{len(_active_connections)}"
    logger.info(f"WS: Cliente conectado ({client_id})")

    # Confirmación de conexión
    try:
        await websocket.send_json({
            "type": "connected",
            "data": {
                "client_id": client_id,
                "active_clients": len(_active_connections),
                "event_types": [
                    e.value for e in [
                        EventType.INPUT, EventType.THOUGHT, EventType.DECISION,
                        EventType.ACTION, EventType.AGENT_START, EventType.AGENT_END,
                        EventType.RESULT, EventType.PROGRESS, EventType.ERROR,
                        EventType.COMPLETE,
                    ]
                ],
                "timestamp": __import__("time").time(),
            },
            "event_id": "connect_" + str(int(__import__("time").time() * 1000)),
        })
    except Exception as exc:
        logger.error(f"WS: Error enviando connect: {exc}")

    # Manejar mensajes del cliente
    try:
        while True:
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                break
            except Exception as exc:
                logger.warning(f"WS: Error receiving: {exc}")
                break

            # Procesar comando del cliente
            message = raw.strip()
            if message.startswith("subscribe:"):
                event_type = message.split(":", 1)[1].strip()
                await _handle_subscribe(websocket, event_type)
            elif message.startswith("unsubscribe:"):
                event_type = message.split(":", 1)[1].strip()
                await _handle_unsubscribe(websocket, event_type)
            elif message == "ping":
                try:
                    await websocket.send_json({
                        "type": "pong",
                        "data": {"timestamp": __import__("time").time()},
                        "event_id": "pong_" + str(int(__import__("time").time() * 1000)),
                    })
                except Exception:
                    break
            else:
                # Echo para depuración
                try:
                    await websocket.send_json({
                        "type": "echo",
                        "data": {"received": message},
                        "event_id": "echo_" + str(int(__import__("time").time() * 1000)),
                    })
                except Exception:
                    break

    except asyncio.CancelledError:
        logger.info(f"WS: Cliente {client_id} cancelado")
    finally:
        if websocket in _active_connections:
            _active_connections.remove(websocket)
        logger.info(f"WS: Cliente desconnected ({client_id}), activos: {len(_active_connections)}")


async def _handle_subscribe(websocket: WebSocket, event_type: str) -> None:
    """Maneja solicitud de suscripción del cliente."""
    valid_types = [e.value for e in EventType]
    if event_type not in valid_types:
        try:
            await websocket.send_json({
                "type": "error",
                "data": {"message": f"Tipo inválido: {event_type}", "valid_types": valid_types},
                "event_id": "err_" + str(int(__import__("time").time() * 1000)),
            })
        except Exception:
            pass
        return

    try:
        await websocket.send_json({
            "type": "subscribed",
            "data": {"event_type": event_type},
            "event_id": "sub_" + str(int(__import__("time").time() * 1000)),
        })
    except Exception:
        pass

    logger.debug(f"WS: Cliente suscrito a {event_type}")


async def _handle_unsubscribe(websocket: WebSocket, event_type: str) -> None:
    """Maneja solicitud de cancelación de suscripción."""
    try:
        await websocket.send_json({
            "type": "unsubscribed",
            "data": {"event_type": event_type},
            "event_id": "unsub_" + str(int(__import__("time").time() * 1000)),
        })
    except Exception:
        pass

    logger.debug(f"WS: Cliente unsubscrito de {event_type}")


@router.get("/ws/info")
async def ws_info() -> Dict[str, Any]:
    """Devuelve información sobre las conexiones WebSocket activas."""
    return {
        "active_connections": len(_active_connections),
        "event_types_available": [
            e.value for e in EventType
        ],
        "endpoint": "/ws/core/events",
        "commands": [
            "subscribe:<event_type>",
            "unsubscribe:<event_type>",
            "ping",
        ],
    }


def get_ws_router() -> APIRouter:
    """Retorna el router de WebSocket para inclusión en la app."""
    return router


if __name_
