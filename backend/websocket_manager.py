"""AURA WebSocket Gateway — canal de eventos literarios en tiempo real.

Endpoint: /api/ws/stream

Gestiona conexiones persistentes entre el host de AURA (PC) y clientes AME
(móvil), propagando instantáneamente:
- Cambios de canon (nuevos eventos canónicos).
- Actualizaciones de Character Bible (personajes creados/editados).
- Cambios de estado de sesión literaria.
- Pings de latencia para keep-alive.

Protocolo de eventos (JSON):
  Cliente → Servidor:
    {"type": "auth", "token": "...", "deviceId": "..."}
    {"type": "subscribe", "work_id": "..."}  # filtrar por obra
    {"type": "ping"}

  Servidor → Cliente:
    {"eventId": "...", "type": "canon_event", "payload": {...}, "createdAt": "ISO", "schemaVersion": 1}
    {"eventId": "...", "type": "character_update", "payload": {...}, "createdAt": "ISO", "schemaVersion": 1}
    {"eventId": "...", "type": "session_change", "payload": {...}, "createdAt": "ISO", "schemaVersion": 1}
    {"type": "pong"}  # respuesta a ping

Mantiene compatibilidad con el protocolo de /api/mobile/sync/{client_id}.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("AURA.WebSocket.Gateway")


class WSGateway:
    """Gestor de conexiones WebSocket para eventos literarios en tiempo real."""

    def __init__(self) -> None:
        self._connections: Dict[str, Set[Any]] = {}  # work_id → {sockets}
        self._all_connections: Set[Any] = set()
        self._lock = threading.Lock()
        self._connection_meta: Dict[int, Dict[str, Any]] = {}

    def add_connection(self, websocket: Any, work_id: Optional[str] = None) -> None:
        """Registra una nueva conexión WebSocket."""
        with self._lock:
            self._all_connections.add(websocket)
            if work_id:
                self._connections.setdefault(work_id, set()).add(websocket)
            self._connection_meta[id(websocket)] = {
                "connected_at": time.time(),
                "work_id": work_id,
            }
        logger.info("WS gateway connection added (total: %d)", len(self._all_connections))

    def remove_connection(self, websocket: Any) -> None:
        """Elimina una conexión WebSocket."""
        with self._lock:
            self._all_connections.discard(websocket)
            for work_id in list(self._connections.keys()):
                self._connections[work_id].discard(websocket)
                if not self._connections[work_id]:
                    self._connections.pop(work_id, None)
            self._connection_meta.pop(id(websocket), None)
        logger.info("WS gateway connection removed (total: %d)", len(self._all_connections))

    def subscribe(self, websocket: Any, work_id: str) -> None:
        """Suscribe una conexión a eventos de una obra específica."""
        with self._lock:
            self._connections.setdefault(work_id, set()).add(websocket)
            self._connection_meta[id(websocket)] = {
                "connected_at": self._connection_meta.get(id(websocket), {}).get("connected_at", time.time()),
                "work_id": work_id,
            }

    def unsubscribe(self, websocket: Any, work_id: Optional[str] = None) -> None:
        """Desuscribe una conexión (de una obra o de todas)."""
        with self._lock:
            if work_id:
                self._connections.get(work_id, set()).discard(websocket)
            else:
                for conns in self._connections.values():
                    conns.discard(websocket)

    async def broadcast(
        self,
        event_type: str,
        payload: Dict[str, Any],
        work_id: Optional[str] = None,
    ) -> int:
        """Transmite un evento a todos los clientes (o solo a suscriptores de una obra).

        Retorna el número de clientes a los que se envió el evento.
        """
        message = json.dumps({
            "eventId": str(uuid.uuid4()),
            "deviceId": "aura-os",
            "type": event_type,
            "payload": payload,
            "createdAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "schemaVersion": 1,
        }, default=str)

        targets: Set[Any] = set()
        with self._lock:
            if work_id:
                targets = set(self._connections.get(work_id, set()))
            else:
                targets = set(self._all_connections)

        if not targets:
            return 0

        sent = 0
        dead: Set[Any] = set()
        for ws in targets:
            try:
                await ws.send(message)
                sent += 1
            except Exception as exc:
                logger.warning("WS broadcast to client failed: %s", exc)
                dead.add(ws)

        for ws in dead:
            self.remove_connection(ws)

        return sent

    async def send_to(self, websocket: Any, data: Dict[str, Any]) -> None:
        """Envía un mensaje a un cliente específico."""
        try:
            await websocket.send(json.dumps(data, default=str))
        except Exception as exc:
            logger.warning("WS send_to failed: %s", exc)
            self.remove_connection(websocket)

    def get_connection_count(self) -> int:
        with self._lock:
            return len(self._all_connections)

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_connections": len(self._all_connections),
                "subscribed_works": {wid: len(conns) for wid, conns in self._connections.items()},
            }


ws_gateway = WSGateway()
