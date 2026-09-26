#!/usr/bin/env python3
"""
godot_bridge.py — AURA Core ↔ Godot 4.x WebSocket Bridge
==========================================================
Servidor WebSocket en puerto 9090 que bidireccionaliza
comunicación entre AURA Core y el juego Godot.

Protocolo JSON:
  AURA → Godot: {"event": "TELEMETRY_UPDATE", "payload": {...}}
  Godot → AURA: {"event": "BUFF_GRANTED", "payload": {...}}

Endpoints:
  ws://localhost:9090           — WebSocket principal
  http://localhost:9090/status  — Status HTTP del bridge
"""

import os
import sys
import json
import time
import asyncio
import logging
import threading
from datetime import datetime
from typing import Dict, Set, Any

# ── websockets para servidor async en Python 3.10+ ──
try:
    import websockets
    import websockets.server
    WS_AVAILABLE = True
except ImportError:
    WS_AVAILABLE = False
    print("[GODOT-BRIDGE] ⚠️  websockets no instalado: pip install websockets")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [GODOT-BRIDGE] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# ── Constantes ──
BRIDGE_PORT = 9090
STATUS_PORT = 9091


class GodotBridge:
    """
    Servidor WebSocket que conecta AURA Core con Godot 4.x.
    Escucha eventos de Godot, los reenvía al EventBus de AURA,
    y envía telemetría/ordenes a Godot cuando hay datos nuevos.
    """

    def __init__(self, aura_event_bus=None):
        self.event_bus = aura_event_bus
        self.clients: Dict[str, Any] = {}
        self.connected = False
        self.start_time = datetime.now()
        self.message_count = 0
        self.event_log: list = []
        self.running = False
        self.loop = None
        self.server = None

    async def _handler(self, websocket, path):
        """Handler principal de cada conexión WebSocket."""
        client_id = f"godot-{str(id(websocket))[-8:]}"
        logger.info(f"🎮 Godot conectado: {client_id}")

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    event = data.get("event", "")
                    payload = data.get("payload", {})

                    self.message_count += 1
                    self._log_event(event, payload, "GODOT→AURA")

                    # Reenviar al EventBus de AURA Core
                    if self.event_bus:
                        self._dispatch_to_aura(event, payload)

                except json.JSONDecodeError:
                    logger.warning(f"JSON inválido de {client_id}")

        except Exception as e:
            logger.error(f"Error en cliente {client_id}: {e}")
        finally:
            logger.info(f"🎮 Godot desconectado: {client_id}")

    async def _dispatch_to_aura(self, event: str, payload: dict):
        """Reenvía un evento de Godot al EventBus de AURA."""
        if self.event_bus and hasattr(self.event_bus, 'emit'):
            self.event_bus.emit(event, payload)
        logger.info(f"  → AURA: {event}")

    async def send_to_godot(self, event: str, payload: dict):
        """Envía un mensaje a todos los clientes Godot conectados."""
        msg = json.dumps({"event": event, "payload": payload})
        for cid, ws in list(self.clients.items()):
            try:
                await ws.send(msg)
            except Exception:
                pass

    async def start(self):
        """Inicia el servidor WebSocket."""
        if not WS_AVAILABLE:
            logger.error("websockets no disponible. Instalar con: pip install websockets")
            return

        self.running = True
        self.server = await websockets.serve(
            self._handler, "0.0.0.0", BRIDGE_PORT
        )
        logger.info(f"🎮 Godot Bridge WebSocket en puerto {BRIDGE_PORT}")
        await self.server.wait_closed()

    def stop(self):
        self.running = False

    def _log_event(self, event, payload, direction):
        entry = {
            "time": datetime.now().isoformat(),
            "event": event,
            "direction": direction,
            "size": len(json.dumps(payload)) if payload else 0
        }
        self.event_log.append(entry)
        if len(self.event_log) > 1000:
            self.event_log = self.event_log[-500:]

    def get_status(self) -> dict:
        return {
            "bridge": "online",
            "clients_connected": len(self.clients),
            "messages_total": self.message_count,
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
            "port": BRIDGE_PORT
        }


def start_bridge():
    """Punto de entrada para iniciar el bridge."""
    print("=" * 50)
    print("  AURA ↔ Godot Bridge")
    print("=" * 50)
    bridge = GodotBridge()
    print(f"  Puerto WebSocket: {BRIDGE_PORT}")
    print()

    asyncio.run(bridge.start())


if __name__ == "__main__":
    start_bridge()