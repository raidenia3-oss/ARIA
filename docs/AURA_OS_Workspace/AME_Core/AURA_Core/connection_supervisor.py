#!/usr/bin/env python3
"""
connection_supervisor.py - Supervisor de conexión SSH para el túnel AURA-Termux.
Este script monitorea constantemente la conexión SSH al nodo móvil y re-establece el túnel
automáticamente si falla. También envía alertas al dashboard web si el nodo está OFFLINE.

Características:
- Monitorea la conexión SSH con pings periódicos.
- Re-intenta establecer el túnel si falla.
- Envía alertas al dashboard web si el nodo está OFFLINE por más de X minutos.
- Logging detallado para monitoreo y depuración.
"""

import os
import sys
import subprocess
import json
import logging
import time
import threading
import requests
from datetime import datetime, timedelta
import argparse
import signal
import socket
from typing import Dict, Optional

class ConnectionSupervisor:
    """Supervisor de conexión SSH para el túnel AURA-Termux."""

    def __init__(self, config: Dict):
        self.config = config
        self.logger = self._setup_logging()
        self.running = False
        self.connection_status = "unknown"
        self.last_ping_success = None
        self.last_reconnect_attempt = None
        self.alert_sent = False
        self.connection_thread = None
        self.alert_thread = None
        self.shutdown_event = threading.Event()

        # Inicializar estado
        self.connection_status = "offline"
        self._update_last_states()

    def _setup_logging(self):
        """Configura el logging para el supervisor de conexión."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('connection_supervisor.log'),
                logging.StreamHandler()
            ]
        )
        logger = logging.getLogger("ConnectionSupervisor")
        logger.setLevel(logging.INFO)
        return logger

    def _update_last_states(self):
        """Actualiza los últimos estados de conexión y reconexión."""
        self.last_ping_success = datetime.utcnow()
        self.last_reconnect_attempt = datetime.utcnow()

    def _test_ssh_connection(self) -> bool:
        """Prueba la conexión SSH al nodo móvil."""
        try:
            command = [
                "ssh", "-p", str(self.config["ssh_port"]),
                f"{self.config['ssh_user']}@{self.config['ssh_host']}",
                "echo 'SSH connection test successful'"
            ]
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.config.get("ping_timeout", 10)
            )
            if result.returncode == 0:
                self.connection_status = "online"
                self.last_ping_success = datetime.utcnow()
                self.logger.info("Conexión SSH verificada con éxito.")
                return True
            else:
                self.connection_status = "offline"
                self.logger.warning(f"Conexión SSH fallida: {result.stderr.strip()}")
                return False
        except subprocess.TimeoutExpired:
            self.connection_status = "offline"
            self.logger.warning("Conexión SSH timeout.")
            return False
        except Exception as e:
            self.connection_status = "offline"
            self.logger.error(f"Error al probar conexión SSH: {str(e)}")
            return False

    def _restart_ssh_tunnel(self) -> bool:
        """Intenta re-establecer el túnel SSH."""
        try:
            self.logger.info("Intentando re-establecer el túnel SSH...")

            # Ejecutar el comando para re-establecer el túnel
            # Asumimos que el túnel se re-establece con el mismo comando que se usó originalmente
            # Esto debería ser reemplazado con el comando real que se usa en tu sistema
            restart_command = self.config.get("restart_command", [
                "bash", "-c", "source ~/.profile; ssh -R 8022:localhost:22 -N user@mobile-device"
            ])

            # Ejecutar el comando en segundo plano
            process = subprocess.Popen(
                restart_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Esperar un poco y luego verificar si el túnel está activo
            time.sleep(self.config.get("reconnect_delay", 5))

            # Verificar si el túnel está activo
            if self._test_ssh_connection():
                self.last_reconnect_attempt = datetime.utcnow()
                self.logger.info("Túnel SSH re-establecido con éxito.")
                return True
            else:
                self.logger.error("Fallo al re-establecer el túnel SSH.")
                return False

        except Exception as e:
            self.logger.error(f"Error al re-establecer el túnel SSH: {str(e)}")
            return False

    def _send_alert_to_dashboard(self, message: str, status: str = "critical"):
        """Envía una alerta al dashboard web."""
        try:
            if not self.config.get("dashboard_url") or not self.config.get("dashboard_api_key"):
                self.logger.warning("No configurada la URL del dashboard o la API key. No se enviará alerta.")
                return False

            dashboard_url = self.config["dashboard_url"]
            api_key = self.config["dashboard_api_key"]

            # Crear payload de la alerta
            payload = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "status": status,
                "message": message,
                "component": "SSH Tunnel Supervisor",
                "details": {
                    "connection_status": self.connection_status,
                    "last_ping": self.last_ping_success.isoformat() if self.last_ping_success else None,
                    "last_reconnect": self.last_reconnect_attempt.isoformat() if self.last_reconnect_attempt else None
                }
            }

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }

            response = requests.post(
                f"{dashboard_url}/api/alerts",
                json=payload,
                headers=headers,
                timeout=self.config.get("alert_timeout", 10)
            )

            if response.status_code == 200:
                self.logger.info(f"Alerta enviada al dashboard: {message}")
                self.alert_sent = True
                return True
            else:
                self.logger.error(f"Error al enviar alerta al dashboard: {response.text}")
                return False

        except Exception as e:
            self.logger.error(f"Error al enviar alerta al dashboard: {str(e)}")
            return False

    def _monitor_connection(self):
        """Monitorea constantemente la conexión SSH."""
        while not self.shutdown_event.is_set():
            try:
                # Verificar conexión
                if not self._test_ssh_connection():
                    # Si la conexión falla, intentar re-establecer el túnel
                    if self._restart_ssh_tunnel():
                        # Si el túnel se re-estableció, enviar alerta de recuperación
                        if self.connection_status == "offline":
                            self._send_alert_to_dashboard(
                                "El túnel SSH ha sido re-establecido con éxito.",
                                "recovery"
                            )
                    else:
                        # Si no se pudo re-establecer, verificar si ya enviamos una alerta
                        if not self.alert_sent:
                            self._send_alert_to_dashboard(
                                "El túnel SSH está OFFLINE y no se pudo re-establecer.",
                                "critical"
                            )
                            self.alert_sent = True

                # Reiniciar el flag de alerta si la conexión está activa
                if self.connection_status == "online":
                    self.alert_sent = False

                # Esperar antes del próximo ping
                time.sleep(self.config.get("ping_interval", 30))

            except Exception as e:
                self.logger.error(f"Error en el monitoreo de conexión: {str(e)}")
                time.sleep(self.config.get("error_retry_delay", 60))

    def _check_offline_status(self):
        """Verifica si el nodo ha estado OFFLINE por demasiado tiempo."""
        while not self.shutdown_event.is_set():
            try:
                if self.connection_status == "offline":
                    offline_duration = datetime.utcnow() - self.last_ping_success
                    if offline_duration > timedelta(minutes=self.config.get("offline_threshold_minutes", 5)):
                        if not self.alert_sent:
                            self._send_alert_to_dashboard(
                                f"El nodo móvil ha estado OFFLINE por más de {self.config['offline_threshold_minutes']} minutos.",
                                "warning"
                            )
                            self.alert_sent = True
                else:
                    self.alert_sent = False

                time.sleep(self.config.get("offline_check_interval", 60))

            except Exception as e:
                self.logger.error(f"Error al verificar estado OFFLINE: {str(e)}")
                time.sleep(self.config.get("error_retry_delay", 60))

    def start(self):
        """Inicia el supervisor de conexión."""
        self.running = True
        self.shutdown_event.clear()
        self.logger.info("Supervisor de conexión SSH iniciado.")

        # Iniciar hilo de monitoreo
        self.connection_thread = threading.Thread(
            target=self._monitor_connection,
            daemon=True,
            name="ConnectionMonitorThread"
        )
        self.connection_thread.start()

        # Iniciar hilo para verificar estado OFFLINE prolongado
        self.alert_thread = threading.Thread(
            target=self._check_offline_status,
            daemon=True,
            name="OfflineStatusCheckerThread"
        )
        self.alert_thread.start()

        # Esperar a que se presione Ctrl+C
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Deteniendo supervisor de conexión...")
        finally:
            self.stop()

    def stop(self):
        """Detiene el supervisor de conexión."""
        if self.running:
            self.running = False
            self.shutdown_event.set()

            # Esperar a que los hilos terminen
            if self.connection_thread:
                self.connection_thread.join(timeout=5)
            if self.alert_thread:
                self.alert_thread.join(timeout=5)

            self.logger.info("Supervisor de conexión detenido.")

def load_config(config_file: str = "connection_supervisor_config.json") -> Dict:
    """Carga la configuración desde un archivo JSON."""
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        raise ValueError(f"Error al cargar configuración: {str(e)}")

def save_config(config: Dict, config_file: str = "connection_supervisor_config.json"):
    """Guarda la configuración en un archivo JSON."""
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        raise ValueError(f"Error al guardar configuración: {str(e)}")

def setup_default_config() -> Dict:
    """Configura valores por defecto para el supervisor de conexión."""
    return {
        "version": "1.0.0",
        "description": "Configuración para el supervisor de conexión SSH AURA-Termux",
        "ssh_host": "localhost",
        "ssh_port": 8022,
        "ssh_user": "user",
        "ping_interval": 30,  # segundos entre pings
        "ping_timeout": 10,   # segundos de timeout para el ping
        "reconnect_delay": 5, # segundos antes de intentar reconectar
        "offline_threshold_minutes": 5,  # minutos OFFLINE antes de enviar alerta
        "offline_check_interval": 60,    # segundos entre verificaciones de estado OFFLINE
        "error_retry_delay": 60,         # segundos entre reintentos después de un error
        "dashboard_url": "http://localhost:3000",  # URL del dashboard web
        "dashboard_api_key": "",          # API key para el dashboard
        "restart_command": [
            "bash", "-c", "source ~/.profile; ssh -R 8022:localhost:22 -N user@mobile-device"
        ],
        "log_file": "connection_supervisor.log"
    }

def main():
    """Punto de entrada principal del supervisor de conexión."""
    parser = argparse.ArgumentParser(description="Supervisor de conexión SSH para el túnel AURA-Termux.")
    parser.add_argument("--config", help="Archivo de configuración JSON", default="connection_supervisor_config.json")
    parser.add_argument("--setup", action="store_true", help="Configurar valores por defecto")
    args = parser.parse_args()

    try:
        if args.setup:
            config = setup_default_config()
            save_config(config)
            print("Configuración por defecto guardada en connection_supervisor_config.json")
            print("Por favor edita este archivo según tu configuración antes de iniciar el servicio.")
            return

        config = load_config(args.config)
        supervisor = ConnectionSupervisor(config)
        supervisor.start()

    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()