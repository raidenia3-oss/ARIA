#!/usr/bin/env python3
"""
telemetry_aggregator.py - Módulo para agregar y gestionar telemetría de nodos móviles en AURA.
Este script recibe datos JSON de los nodos móviles, los procesa, los almacena en un archivo histórico
y los transmite en tiempo real al frontend de AME mediante WebSocket.
"""

import os
import json
import asyncio
import websockets
from datetime import datetime
from typing import Dict, List, Optional
import logging
from pathlib import Path

class TelemetryAggregator:
    def __init__(self, config: Dict):
        self.config = config
        self.telemetry_history_file = config.get("telemetry_history_file", "telemetry_history.json")
        self.websocket_port = config.get("websocket_port", 8765)
        self.max_history_size = config.get("max_history_size", 1000)
        self.telemetry_data = {}
        self.setup_logging()
        self.load_history()

    def setup_logging(self):
        """Configura el logging para el agregador de telemetría."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('telemetry_aggregator.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger("TelemetryAggregator")

    def load_history(self):
        """Carga el historial de telemetría desde el archivo JSON."""
        try:
            if os.path.exists(self.telemetry_history_file):
                with open(self.telemetry_history_file, 'r') as f:
                    self.telemetry_data = json.load(f)
                    self.logger.info(f"Cargados {len(self.telemetry_data)} registros de telemetría.")
            else:
                self.telemetry_data = {}
        except Exception as e:
            self.logger.error(f"Error al cargar el historial de telemetría: {str(e)}")
            self.telemetry_data = {}

    def save_history(self):
        """Guarda el historial de telemetría en el archivo JSON."""
        try:
            with open(self.telemetry_history_file, 'w') as f:
                json.dump(self.telemetry_data, f, indent=2)
            self.logger.info("Historial de telemetría guardado.")
        except Exception as e:
            self.logger.error(f"Error al guardar el historial de telemetría: {str(e)}")

    def add_telemetry(self, device_id: str, telemetry: Dict):
        """
        Agrega un nuevo registro de telemetría para un dispositivo específico.
        """
        timestamp = datetime.utcnow().isoformat() + "Z"
        entry = {
            "timestamp": timestamp,
            "device_id": device_id,
            "data": telemetry
        }

        # Agregar al historial
        if device_id not in self.telemetry_data:
            self.telemetry_data[device_id] = []
        self.telemetry_data[device_id].append(entry)

        # Limitar el tamaño del historial
        if len(self.telemetry_data[device_id]) > self.max_history_size:
            self.telemetry_data[device_id] = self.telemetry_data[device_id][-self.max_history_size:]

        # Guardar en disco
        self.save_history()

        # Retornar el registro para transmisión en tiempo real
        return entry

    async def broadcast_telemetry(self, websocket_server, data: Dict):
        """
        Transmite los datos de telemetría a todos los clientes WebSocket conectados.
        """
        if websocket_server:
            try:
                await websocket_server.broadcast(json.dumps(data))
            except Exception as e:
                self.logger.error(f"Error al transmitir telemetría: {str(e)}")

    async def handle_websocket_client(self, websocket, path):
        """
        Maneja la conexión WebSocket de un cliente frontend.
        """
        self.logger.info("Cliente WebSocket conectado.")
        try:
            async for message in websocket:
                # Este endpoint solo recibe datos de telemetría de los nodos móviles
                # Los clientes frontend solo escuchan
                pass
        except websockets.exceptions.ConnectionClosed:
            self.logger.info("Cliente WebSocket desconectado.")
        except Exception as e:
            self.logger.error(f"Error en la conexión WebSocket: {str(e)}")

    async def start_websocket_server(self):
        """
        Inicia el servidor WebSocket para transmitir telemetría en tiempo real.
        """
        async with websockets.serve(
            self.handle_websocket_client,
            "0.0.0.0",
            self.websocket_port
        ):
            self.logger.info(f"Servidor WebSocket iniciado en ws://0.0.0.0:{self.websocket_port}")
            await asyncio.Future()  # Mantiene el servidor en ejecución

    async def process_telemetry_data(self, data: Dict):
        """
        Procesa los datos de telemetría recibidos de un nodo móvil.
        """
        try:
            device_id = data.get("device_id")
            if not device_id:
                self.logger.error("ID de dispositivo no proporcionado en los datos de telemetría.")
                return

            # Agregar al historial
            telemetry_entry = self.add_telemetry(device_id, data.get("data", {}))

            # Transmitir en tiempo real
            await self.broadcast_telemetry(self, telemetry_entry)

        except Exception as e:
            self.logger.error(f"Error al procesar datos de telemetría: {str(e)}")

    async def run(self):
        """
        Inicia el agregador de telemetría y el servidor WebSocket.
        """
        # Iniciar servidor WebSocket en un hilo separado
        websocket_task = asyncio.create_task(self.start_websocket_server())

        # Esperar a que el servidor WebSocket esté listo
        await asyncio.sleep(1)

        # Simular recepción de datos de telemetría (para pruebas)
        # En un entorno real, estos datos serían recibidos desde los nodos móviles
        self.logger.info("Agregador de telemetría en ejecución. Esperando datos de los nodos móviles...")

        # Ejemplo de datos simulados (comentar en producción)
        # await self.process_telemetry_data({
        #     "device_id": "ANDROID_EDGE_NODE_001",
        #     "data": {
        #         "connection_status": "active",
        #         "cpu_usage": 15.3,
        #         "temperature": 35.5,
        #         "battery_level": 85,
        #         "last_heartbeat": "2026-06-02T15:00:00Z"
        #     }
        # })

        # Esperar indefinidamente (en un entorno real, esto sería reemplazado por la recepción de datos)
        await asyncio.Future()

def main():
    """Punto de entrada principal del agregador de telemetría."""
    config = {
        "telemetry_history_file": "telemetry_history.json",
        "websocket_port": 8765,
        "max_history_size": 1000
    }

    aggregator = TelemetryAggregator(config)

    try:
        asyncio.run(aggregator.run())
    except KeyboardInterrupt:
        aggregator.logger.info("Deteniendo el agregador de telemetría...")
    except Exception as e:
        aggregator.logger.error(f"Error en el agregador de telemetría: {str(e)}")

if __name__ == "__main__":
    main()