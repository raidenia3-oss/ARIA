#!/usr/bin/env python3
"""
ws_server.py - Servidor WebSocket para el Dashboard Táctico de AME
Este módulo maneja las conexiones WebSocket para el dashboard táctico,
proporcionando actualizaciones en tiempo real de nodos y tareas.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
import uuid
import websockets
from websockets.exceptions import ConnectionClosed
import threading
import time
from AURA_Core.swarm_manager import SwarmManager
from AURA_Core.action_handler import ActionHandler
from AURA_Core.data_lakehouse import DataLakehouse

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("ws_server.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class WebSocketServer:
    def __init__(self, host="0.0.0.0", port=3000):
        self.host = host
        self.port = port
        self.websockets: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.subscriptions: Dict[str, List[str]] = {}  # {channel: [ws_ids]}
        self.nodes: List[Dict] = []
        self.tasks: Dict[str, Dict] = {}
        self.swarm_manager = SwarmManager()
        self.action_handler = ActionHandler()
        self.data_lakehouse = DataLakehouse()
        self.running = False
        self.server_thread = None

        # Simular datos iniciales de nodos
        self._initialize_sample_nodes()

        # Iniciar el servidor en un hilo separado
        self.server_thread = threading.Thread(target=self._run_server)
        self.server_thread.daemon = True

    def _initialize_sample_nodes(self):
        """Inicializar nodos de ejemplo para pruebas"""
        self.nodes = [
            {
                "id": f"node-{i}",
                "name": f"Nodo {i+1}",
                "type": "mobile",
                "status": "available" if i % 3 != 0 else "offline",
                "location": f"Sector {chr(65 + i % 5)}",
                "last_seen": datetime.now().isoformat(),
                "battery": 85 + (i % 20),
                "signal": 70 + (i % 30),
            }
            for i in range(10)
        ]

        # Estado de sesión por conexión: {connection_id: {subscriptions:[], last_seen, session_token}}
        self.sessions: Dict[str, Dict] = {}

    async def _handle_connection(self, websocket: websockets.WebSocketServerProtocol, path):
        """Manejar una conexión WebSocket individual"""
        connection_id = str(uuid.uuid4())
        session_token = self._recover_or_create_token(path)
        self.websockets[connection_id] = websocket
        self.sessions[connection_id] = {
            "subscriptions": [],
            "last_seen": datetime.now().isoformat(),
            "session_token": session_token,
        }
        logger.info(f"Nueva conexión WebSocket: {connection_id}")

        heartbeat_task = None

        async def _heartbeat_loop():
            nonlocal heartbeat_task
            try:
                while True:
                    await asyncio.sleep(15)
                    if connection_id in self.websockets:
                        await self._send_heartbeat(connection_id)
            except Exception as e:
                logger.debug(f"Heartbeat loop ended {connection_id}: {e}")

        try:
            heartbeat_task = asyncio.create_task(_heartbeat_loop())
            async for message in websocket:
                try:
                    data = json.loads(message)
                    if data.get("action") == "subscribe":
                        channel = data.get("channel")
                        if channel:
                            if channel not in self.subscriptions:
                                self.subscriptions[channel] = []
                            if connection_id not in self.subscriptions[channel]:
                                self.subscriptions[channel].append(connection_id)
                                self.sessions[connection_id]["subscriptions"].append(channel)
                                logger.info(f"Cliente {connection_id} suscrito a {channel}")
                        await self._send_to_connection(
                            connection_id, "session", {"token": session_token}
                        )
                    elif data.get("action") == "assign_task":
                        await self._handle_task_assignment(data, connection_id)
                    elif data.get("event") == "heartbeat":
                        await self._send_to_connection(
                            connection_id, "heartbeat_ack", {"t": datetime.now().isoformat()}
                        )
                    else:
                        logger.warning(f"Mensaje desconocido de {connection_id}: {message}")
                except json.JSONDecodeError:
                    logger.warning(f"Mensaje no válido de {connection_id}: {message}")
                except Exception as e:
                    logger.error(f"Error procesando mensaje de {connection_id}: {e}")

        except ConnectionClosed:
            logger.info(f"Conexión cerrada: {connection_id}")
        finally:
            if heartbeat_task:
                heartbeat_task.cancel()
            # Limpiar suscripciones
            for channel, connections in list(self.subscriptions.items()):
                if connection_id in connections:
                    connections.remove(connection_id)
                    if not connections:
                        del self.subscriptions[channel]

            # Eliminar conexión
            if connection_id in self.websockets:
                del self.websockets[connection_id]
            if connection_id in self.sessions:
                del self.sessions[connection_id]

    def _recover_or_create_token(self, path: str) -> str:
        """Recuperar token desde la URL de reconexión o crear uno nuevo"""
        from urllib.parse import urlparse, parse_qs

        parsed = urlparse(str(path))
        query = parse_qs(parsed.query)
        token = query.get("token", [None])[0]
        if token:
            return token
        return str(uuid.uuid4())

    async def _send_heartbeat(self, connection_id: str):
        """Enviar heartbeat a un cliente y esperar pong"""
        try:
            ping_msg = json.dumps({"event": "heartbeat", "data": {}})
            await self.websockets[connection_id].send(ping_msg)
        except Exception as e:
            logger.debug(f"Heartbeat drop {connection_id}: {e}")

    async def _handle_task_assignment(self, data: Dict, connection_id: str):
        """Manejar la asignación de una tarea a un nodo"""
        try:
            node_id = data.get("nodeId")
            module_type = data.get("module")
            task_id = str(uuid.uuid4())

            if not node_id or not module_type:
                raise ValueError("Faltan datos para asignar tarea")

            # Buscar el nodo
            node = next((n for n in self.nodes if n["id"] == node_id), None)
            if not node:
                raise ValueError(f"Nodo no encontrado: {node_id}")

            # Actualizar estado del nodo
            node["status"] = "busy"
            await self._broadcast("node_update", self.nodes)

            # Crear tarea
            task = {
                "id": task_id,
                "nodeId": node_id,
                "module": module_type,
                "timestamp": datetime.now().isoformat(),
                "status": "assigned",
                "progress": 0,
                "output": [],
            }

            self.tasks[task_id] = task
            await self._broadcast("task_assigned", task)

            # Simular ejecución de la tarea (en un entorno real, esto sería manejado por SwarmManager)
            await self._simulate_task_execution(task_id, node_id, module_type)

        except Exception as e:
            logger.error(f"Error asignando tarea: {e}")
            error_msg = {"error": str(e), "taskId": task_id}
            await self._send_to_connection(connection_id, "error", error_msg)

    async def _simulate_task_execution(self, task_id: str, node_id: str, module_type: str):
        """Simular la ejecución de una tarea (para pruebas)"""
        task = self.tasks.get(task_id)
        if not task:
            return

        # Simular progreso de la tarea
        for i in range(1, 11):
            if task_id not in self.tasks:
                break

            progress = i * 10
            task["progress"] = progress
            task["status"] = "running"

            # Generar salida simulada
            output_line = f"[{datetime.now().strftime('%H:%M:%S')}] {module_type.upper()} Module - Progress: {progress}% - Node: {node_id}"
            if i % 3 == 0:
                output_line += f" | Sample data: {i * 10} items processed"

            task["output"].append(output_line)

            # Enviar actualización
            await self._broadcast("task_update", task)

            # Esperar un momento
            await asyncio.sleep(1)

        # Completar tarea
        if task_id in self.tasks:
            task["status"] = "completed"
            task["progress"] = 100
            task["output"].append(
                f"[{datetime.now().strftime('%H:%M:%S')}] Task completed successfully on node {node_id}"
            )
            await self._broadcast("task_update", task)

            # Actualizar estado del nodo
            node = next((n for n in self.nodes if n["id"] == node_id), None)
            if node:
                node["status"] = "available"
                await self._broadcast("node_update", self.nodes)

    async def _broadcast(self, event: str, data: Dict):
        """Enviar un mensaje a TODOS los clientes conectados (multi-cliente)"""
        message = {"event": event, "data": data}
        for connection_id, ws in list(self.websockets.items()):
            try:
                await ws.send(json.dumps(message))
            except Exception as e:
                logger.error(f"Error enviando mensaje a {connection_id}: {e}")

    async def _send_to_connection(self, connection_id: str, event: str, data: Dict):
        """Enviar un mensaje a una conexión específica"""
        if connection_id in self.websockets:
            try:
                message = json.dumps({"event": event, "data": data})
                await self.websockets[connection_id].send(message)
            except Exception as e:
                logger.error(f"Error enviando mensaje a {connection_id}: {e}")

    def _run_server(self):
        """Iniciar el servidor WebSocket"""
        start_server = websockets.serve(self._handle_connection, self.host, self.port)

        asyncio.set_event_loop(asyncio.new_event_loop())
        asyncio.get_event_loop().run_until_complete(start_server)
        asyncio.get_event_loop().run_forever()

    def start(self):
        """Iniciar el servidor en un hilo separado"""
        if not self.running:
            self.running = True
            self.server_thread.start()
            logger.info(f"Servidor WebSocket iniciado en {self.host}:{self.port}")

    def stop(self):
        """Detener el servidor"""
        if self.running:
            self.running = False
            if self.server_thread:
                self.server_thread.join(timeout=5)
            logger.info("Servidor WebSocket detenido")

    def get_nodes(self) -> List[Dict]:
        """Obtener la lista actual de nodos"""
        return self.nodes

    def get_tasks(self) -> Dict[str, Dict]:
        """Obtener la lista actual de tareas"""
        return self.tasks


if __name__ == "__main__":
    server = WebSocketServer()
    server.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
