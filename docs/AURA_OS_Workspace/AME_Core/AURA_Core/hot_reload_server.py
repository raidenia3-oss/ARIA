#!/usr/bin/env python3
"""
hot_reload_server.py - Servidor WebSocket para Hot-Reload de AME.
Este servidor difunde eventos 'RELOAD' cada vez que watchdog detecta cambios en los archivos
del frontend de AME, permitiendo que la app se recargue automáticamente en el dispositivo móvil.

Características:
- Usa WebSockets para comunicación en tiempo real.
- Difunde eventos a todos los clientes conectados.
- Integrable con el sistema de watchdog existente.
- Logging detallado para monitoreo.
"""

import asyncio
import json
import logging
from typing import Dict, List, Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import argparse
import os
import sys
from datetime import datetime

class HotReloadEventHandler(FileSystemEventHandler):
    """Maneja eventos de cambios en el sistema de archivos para Hot-Reload."""

    def __init__(self, config: Dict, websocket_server):
        self.config = config
        self.websocket_server = websocket_server
        self.logger = logging.getLogger("HotReloadEventHandler")
        self.ignored_dirs = config.get("ignored_dirs", [
            ".git", "node_modules", "__pycache__", ".venv", ".env",
            ".vscode", "dist", "build", "logs", "spec"
        ])
        self.ame_frontend_dir = config.get("ame_frontend_dir", "AME_Core")
        self.recent_files = set()  # Para evitar múltiples eventos por el mismo archivo
        self.debounce_time = config.get("debounce_time", 1.0)  # segundos para evitar spam

    def should_ignore(self, file_path: str) -> bool:
        """Determina si un archivo o directorio debe ser ignorado."""
        try:
            # Ignorar directorios
            for ignored_dir in self.ignored_dirs:
                if ignored_dir in file_path:
                    return True

            # Ignorar archivos fuera del directorio de AME
            if not file_path.startswith(self.ame_frontend_dir):
                return True

            # Ignorar archivos ocultos
            if file_path.startswith('.'):
                return True

            # Ignorar extensiones no relevantes
            excluded_extensions = [".log", ".pyc", ".pyo", ".dll", ".so", ".min.js", ".min.css"]
            if os.path.splitext(file_path)[1] in excluded_extensions:
                return True

            return False
        except Exception as e:
            self.logger.error(f"Error al verificar exclusión para {file_path}: {str(e)}")
            return True

    def is_relevant_file(self, file_path: str) -> bool:
        """Verifica si el archivo es relevante para el Hot-Reload."""
        try:
            # Verificar que sea un archivo (no directorio)
            if not os.path.isfile(file_path):
                return False

            # Verificar extensiones relevantes para el frontend
            relevant_extensions = [".html", ".js", ".css", ".json", ".ts", ".tsx"]
            return os.path.splitext(file_path)[1].lower() in relevant_extensions
        except Exception as e:
            self.logger.error(f"Error al verificar archivo {file_path}: {str(e)}")
            return False

    def on_modified(self, event):
        """Evento llamado cuando un archivo es modificado."""
        if not event.is_directory:
            file_path = event.src_path
            if not self.should_ignore(file_path) and self.is_relevant_file(file_path):
                self.logger.debug(f"Cambio detectado en archivo relevante: {file_path}")
                self.trigger_reload(file_path)

    def on_created(self, event):
        """Evento llamado cuando un archivo es creado."""
        if not event.is_directory:
            file_path = event.src_path
            if not self.should_ignore(file_path) and self.is_relevant_file(file_path):
                self.logger.debug(f"Archivo relevante creado: {file_path}")
                self.trigger_reload(file_path)

    def on_deleted(self, event):
        """Evento llamado cuando un archivo es eliminado."""
        if not event.is_directory:
            file_path = event.src_path
            if not self.should_ignore(file_path):
                self.logger.debug(f"Archivo eliminado: {file_path}")
                self.trigger_reload(file_path, is_deleted=True)

    def trigger_reload(self, file_path: str, is_deleted: bool = False):
        """Dispara un evento de recarga para todos los clientes WebSocket."""
        try:
            # Evitar múltiples eventos por el mismo archivo en poco tiempo
            if file_path in self.recent_files:
                return

            self.recent_files.add(file_path)

            # Crear mensaje de evento
            event_data = {
                "type": "hot_reload",
                "action": "reload" if not is_deleted else "hard_reload",
                "file": file_path,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "message": f"Archivo {file_path} ha sido modificado" if not is_deleted else f"Archivo {file_path} ha sido eliminado"
            }

            # Difundir el evento a todos los clientes conectados
            self.logger.info(f"Difundiendo evento de recarga: {event_data['message']}")
            asyncio.create_task(self.websocket_server.broadcast(json.dumps(event_data)))

            # Limpiar el conjunto de archivos recientes después de un tiempo
            asyncio.create_task(asyncio.sleep(self.debounce_time))
            self.recent_files.discard(file_path)

        except Exception as e:
            self.logger.error(f"Error al difundir evento de recarga: {str(e)}")

class HotReloadWebSocketServer:
    """Servidor WebSocket para manejar conexiones de Hot-Reload."""

    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger("HotReloadWebSocketServer")
        self.clients: Set[asyncio.Queue] = set()
        self.port = config.get("websocket_port", 8080)
        self.host = config.get("websocket_host", "0.0.0.0")
        self.server = None

    async def broadcast(self, message: str):
        """Difunde un mensaje a todos los clientes conectados."""
        if not self.clients:
            return

        # Crear una copia del conjunto de clientes para evitar problemas de concurrencia
        clients_copy = self.clients.copy()

        for client_queue in clients_copy:
            try:
                await client_queue.put(message)
            except Exception as e:
                self.logger.error(f"Error al enviar mensaje a cliente: {str(e)}")
                # Eliminar cliente si falla la comunicación
                self.clients.discard(client_queue)

    async def handle_client(self, reader, writer):
        """Maneja una conexión de cliente WebSocket."""
        client_queue = asyncio.Queue()
        self.clients.add(client_queue)

        self.logger.info(f"Nuevo cliente conectado: {writer.getextrainfo('peername')}")

        try:
            # Leer el handshake HTTP (simplificado para WebSocket)
            # En un entorno de producción, usarías una librería como websockets
            # Aquí usamos un enfoque básico para demostración
            while True:
                data = await reader.read(1024)
                if not data:
                    break

                # Procesar mensajes (en un entorno real, usarías un parser de WebSocket)
                # Para este ejemplo, asumimos que el cliente envía pings y nosotros respondemos
                if b"ping" in data.lower():
                    writer.write(b"pong\n")
                    await writer.drain()
                else:
                    # Enviar mensajes de bienvenida o mantener la conexión
                    if client_queue.empty():
                        welcome_msg = json.dumps({
                            "type": "welcome",
                            "message": "Conectado al servidor de Hot-Reload de AME",
                            "timestamp": datetime.utcnow().isoformat() + "Z"
                        })
                        await client_queue.put(welcome_msg)

        except Exception as e:
            self.logger.error(f"Error en conexión con cliente: {str(e)}")
        finally:
            self.clients.discard(client_queue)
            writer.close()
            await writer.wait_closed()
            self.logger.info(f"Cliente desconectado: {writer.getextrainfo('peername')}")

    async def start(self):
        """Inicia el servidor WebSocket."""
        self.server = await asyncio.start_server(
            self.handle_client,
            self.host,
            self.port
        )

        addr = self.server.sockets[0].getsockname()
        self.logger.info(f"Servidor WebSocket iniciado en ws://{addr[0]}:{addr[1]}")

        async with self.server:
            await self.server.serve_forever()

class HotReloadService:
    """Servicio principal de Hot-Reload."""

    def __init__(self, config: Dict):
        self.config = config
        self.logger = self._setup_logging()
        self.websocket_server = HotReloadWebSocketServer(config)
        self.event_handler = HotReloadEventHandler(config, self.websocket_server)
        self.observer = None
        self.running = False
        self.task = None

    def _setup_logging(self):
        """Configura el logging para el servicio de Hot-Reload."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('hot_reload_server.log'),
                logging.StreamHandler()
            ]
        )
        logger = logging.getLogger("HotReloadService")
        logger.setLevel(logging.INFO)
        return logger

    def _setup_observer(self):
        """Configura el observador de watchdog."""
        try:
            self.observer = Observer()
            self.observer.schedule(
                self.event_handler,
                self.config["ame_frontend_dir"],
                recursive=True
            )
            self.logger.info(f"Observando directorio de AME: {self.config['ame_frontend_dir']}")
        except Exception as e:
            self.logger.error(f"Error al configurar observador: {str(e)}")
            raise

    async def _start_websocket_server(self):
        """Inicia el servidor WebSocket en un hilo separado."""
        try:
            await self.websocket_server.start()
        except Exception as e:
            self.logger.error(f"Error al iniciar servidor WebSocket: {str(e)}")
            raise

    def start(self):
        """Inicia el servicio de Hot-Reload."""
        try:
            self._setup_observer()
            self.running = True
            self.logger.info("Servicio de Hot-Reload iniciado.")

            # Iniciar el servidor WebSocket en un hilo separado
            self.task = asyncio.create_task(self._start_websocket_server())

            # Iniciar el observador
            self.observer.start()

            # Esperar a que el servidor WebSocket esté listo
            asyncio.get_event_loop().run_until_complete(asyncio.sleep(1))

            self.logger.info("Servicio listo. Esperando cambios en los archivos de AME...")

            # Bucle principal (para manejar señales de interrupción)
            try:
                while self.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                self.logger.info("Deteniendo servicio de Hot-Reload...")
            finally:
                self.stop()

        except Exception as e:
            self.logger.error(f"Error en el servicio de Hot-Reload: {str(e)}")
            self.stop()
            raise

    def stop(self):
        """Detiene el servicio de Hot-Reload."""
        if self.running:
            self.running = False

            # Detener el observador
            if self.observer and self.observer.is_alive():
                self.observer.stop()
                self.observer.join()
                self.logger.info("Observador de watchdog detenido.")

            # Detener el servidor WebSocket
            if self.task:
                try:
                    self.task.cancel()
                    asyncio.get_event_loop().run_until_complete(self.task)
                except Exception as e:
                    self.logger.error(f"Error al detener servidor WebSocket: {str(e)}")

            self.logger.info("Servicio de Hot-Reload detenido.")

def load_config(config_file: str = "hot_reload_config.json") -> Dict:
    """Carga la configuración desde un archivo JSON."""
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        raise ValueError(f"Error al cargar configuración: {str(e)}")

def save_config(config: Dict, config_file: str = "hot_reload_config.json"):
    """Guarda la configuración en un archivo JSON."""
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        raise ValueError(f"Error al guardar configuración: {str(e)}")

def setup_default_config() -> Dict:
    """Configura valores por defecto para el Hot-Reload."""
    return {
        "version": "1.0.0",
        "ame_frontend_dir": "AME_Core",
        "websocket_host": "0.0.0.0",
        "websocket_port": 8080,
        "ignored_dirs": [
            ".git", "node_modules", "__pycache__", ".venv", ".env",
            ".vscode", "dist", "build", "logs", "spec"
        ],
        "debounce_time": 1.0,
        "log_file": "hot_reload_server.log"
    }

def main():
    """Punto de entrada principal del servicio de Hot-Reload."""
    parser = argparse.ArgumentParser(description="Servicio de Hot-Reload para AME.")
    parser.add_argument("--config", help="Archivo de configuración JSON", default="hot_reload_config.json")
    parser.add_argument("--setup", action="store_true", help="Configurar valores por defecto")
    args = parser.parse_args()

    try:
        if args.setup:
            config = setup_default_config()
            save_config(config)
            print("Configuración por defecto guardada en hot_reload_config.json")
            print("Por favor edita este archivo según tu configuración antes de iniciar el servicio.")
            return

        config = load_config(args.config)
        service = HotReloadService(config)

        # Iniciar el servicio en un hilo separado para permitir el manejo de señales
        import threading
        sync_thread = threading.Thread(target=service.start, daemon=True)
        sync_thread.start()

        # Esperar a que el hilo termine (para manejo de señales)
        sync_thread.join()

    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()