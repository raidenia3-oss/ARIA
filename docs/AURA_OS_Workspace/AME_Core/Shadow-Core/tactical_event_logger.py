"""
Módulo de registro de eventos tácticos para Shadow-Core.
Registra eventos del sistema de manera segura y los envía al EventBus de AURA.
No captura teclas ni portapapeles, solo eventos de sistema autorizados.
"""

import json
import logging
import threading
import time
import asyncio
import websockets
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import subprocess
import platform

class TacticalEventLogger:
    """
    Logger de eventos tácticos para Shadow-Core.
    Registra eventos del sistema y los envía al EventBus de AURA.
    """

    def __init__(self, event_bus_url: str = "ws://localhost:8765"):
        self.event_bus_url = event_bus_url
        self.logger = logging.getLogger("TacticalEventLogger")
        self.logger.setLevel(logging.INFO)
        self.event_queue = []
        self.running = False
        self.ws_connection = None
        self.lock = threading.Lock()
        self.config_path = Path("Shadow-Core/config/tactical_events.json")
        self._load_config()

    def _load_config(self) -> None:
        """Cargar configuración de eventos a monitorear."""
        if not self.config_path.exists():
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(json.dumps({
                "enabled_events": [
                    "system_startup",
                    "service_restart",
                    "network_change",
                    "disk_usage",
                    "process_termination"
                ],
                "event_interval": 60,
                "max_queue_size": 1000
            }, indent=2))

        try:
            with open(self.config_path, "r") as f:
                self.config = json.load(f)
        except Exception as e:
            self.logger.error(f"Error cargando configuración: {e}")
            self.config = {
                "enabled_events": [],
                "event_interval": 60,
                "max_queue_size": 1000
            }

    def _get_system_info(self) -> Dict:
        """Recopilar información básica del sistema."""
        return {
            "timestamp": datetime.now().isoformat(),
            "hostname": platform.node(),
            "os": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_cores": threading.active_count(),
            "memory_usage": self._get_memory_usage()
        }

    def _get_memory_usage(self) -> Dict:
        """Obtener uso de memoria del sistema."""
        try:
            with open("/proc/meminfo", "r") as f:
                meminfo = f.read()
            mem = {}
            for line in meminfo.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    mem[key.strip()] = value.strip()
            return {
                "total": mem.get("MemTotal", "0"),
                "free": mem.get("MemFree", "0"),
                "available": mem.get("MemAvailable", "0")
            }
        except Exception:
            return {"total": "N/A", "free": "N/A", "available": "N/A"}

    def _get_network_interfaces(self) -> List[Dict]:
        """Obtener información de interfaces de red."""
        try:
            result = subprocess.run(
                ["ip", "addr", "show"],
                capture_output=True,
                text=True,
                timeout=5
            )
            interfaces = []
            for line in result.stdout.split("\n"):
                if "state UP" in line:
                    interface = {}
                    for part in line.split():
                        if part.startswith("inet"):
                            interface["ip"] = part.split("/")[0]
                        elif part.startswith("link/ether"):
                            interface["mac"] = part.split()[1]
                    if interface:
                        interfaces.append(interface)
            return interfaces
        except Exception as e:
            self.logger.error(f"Error obteniendo interfaces de red: {e}")
            return []

    def _log_system_event(self, event_type: str, details: Dict = None) -> None:
        """Registrar un evento del sistema."""
        event = {
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            "system_info": self._get_system_info(),
            "details": details or {},
            "source": "Shadow-Core"
        }

        with self.lock:
            self.event_queue.append(event)
            if len(self.event_queue) > self.config["max_queue_size"]:
                self.event_queue.pop(0)

    async def _connect_to_event_bus(self) -> None:
        """Conectar al EventBus de AURA."""
        try:
            self.ws_connection = await websockets.connect(
                self.event_bus_url,
                ping_interval=20,
                ping_timeout=10
            )
            self.logger.info(f"Conectado al EventBus en {self.event_bus_url}")
        except Exception as e:
            self.logger.error(f"Error conectando al EventBus: {e}")

    async def _send_event_to_bus(self, event: Dict) -> None:
        """Enviar evento al EventBus de AURA."""
        if self.ws_connection and self.ws_connection.open:
            try:
                await self.ws_connection.send(json.dumps({
                    "node": "Shadow-Core",
                    "event": "TACTICAL_CAPTURE",
                    "payload": event,
                    "ts": datetime.now().isoformat()
                }))
                self.logger.debug(f"Evento enviado al EventBus: {event['type']}")
            except Exception as e:
                self.logger.error(f"Error enviando evento al EventBus: {e}")
                # Intentar reconectar
                await self._connect_to_event_bus()

    def _process_queue(self) -> None:
        """Procesar la cola de eventos y enviarlos al EventBus."""
        while self.running:
            with self.lock:
                if self.event_queue:
                    batch = self.event_queue.copy()
                    self.event_queue.clear()

            for event in batch:
                try:
                    asyncio.run(self._send_event_to_bus(event))
                except Exception as e:
                    self.logger.error(f"Error procesando evento: {e}")

            time.sleep(1)

    def _send_to_event_bus(self, event: Dict) -> None:
        """Enviar evento al EventBus de AURA (versión sincrónica)."""
        # Para pruebas, guardamos en un archivo temporal
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = Path(f"Shadow-Core/logs/tactical_events_{timestamp}.json")
        log_file.parent.mkdir(parents=True, exist_ok=True)

        with open(log_file, "a") as f:
            f.write(json.dumps(event) + "\n")

    def start(self) -> None:
        """Iniciar el logger de eventos tácticos."""
        if self.running:
            return

        self.running = True
        self.logger.info("Iniciando Tactical Event Logger")

        # Iniciar conexión al EventBus
        asyncio.run(self._connect_to_event_bus())

        # Iniciar hilo para procesar la cola
        threading.Thread(target=self._process_queue, daemon=True).start()

        # Registrar eventos iniciales
        self._log_system_event("system_startup")
        self._log_system_event("network_change", {"interfaces": self._get_network_interfaces()})

    def stop(self) -> None:
        """Detener el logger de eventos tácticos."""
        self.running = False
        if self.ws_connection:
            try:
                self.ws_connection.close()
            except Exception as e:
                self.logger.error(f"Error cerrando conexión al EventBus: {e}")
        self.logger.info("Deteniendo Tactical Event Logger")

    def log_service_restart(self, service_name: str) -> None:
        """Registrar reinicio de servicio."""
        self._log_system_event("service_restart", {
            "service": service_name,
            "timestamp": datetime.now().isoformat()
        })

    def log_process_termination(self, process_name: str, exit_code: int) -> None:
        """Registrar terminación de proceso."""
        self._log_system_event("process_termination", {
            "process": process_name,
            "exit_code": exit_code,
            "timestamp": datetime.now().isoformat()
        })

    def log_disk_usage(self, path: str = "/") -> None:
        """Registrar uso de disco."""
        try:
            result = subprocess.run(
                ["df", "-h", path],
                capture_output=True,
                text=True,
                timeout=5
            )
            usage = {}
            for line in result.stdout.split("\n")[1:]:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 6:
                        usage[parts[0]] = {
                            "used": parts[2],
                            "total": parts[1],
                            "percent": parts[4]
                        }
            self._log_system_event("disk_usage", {"path": path, "usage": usage})
        except Exception as e:
            self.logger.error(f"Error obteniendo uso de disco: {e}")

    def log_network_change(self) -> None:
        """Registrar cambio de red."""
        self._log_system_event("network_change", {
            "interfaces": self._get_network_interfaces(),
            "timestamp": datetime.now().isoformat()
        })

# Instancia global del logger
tactical_event_logger = TacticalEventLogger()

if __name__ == "__main__":
    # Ejemplo de uso
    tactical_event_logger.start()

    # Simular algunos eventos
    tactical_event_logger.log_service_restart("Shadow-Core")
    tactical_event_logger.log_disk_usage()
    tactical_event_logger.log_network_change()

    # Esperar 10 segundos para mostrar el procesamiento
    time.sleep(10)

    tactical_event_logger.stop()