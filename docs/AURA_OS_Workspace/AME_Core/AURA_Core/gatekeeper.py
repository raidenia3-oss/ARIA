#!/usr/bin/env python3
"""
gatekeeper.py - Gatekeeper de seguridad para módulos Venice en dispositivos móviles.
Este script se ejecuta ANTES de cualquier módulo Venice y valida las condiciones de seguridad
del dispositivo antes de permitir la ejecución.

Características:
- Verifica nivel de batería (>30%).
- Valida que el túnel SSH esté estable.
- Comprueba que haya suficiente espacio en disco.
- Envía alertas a AURA si las validaciones fallan.
- Pone el sistema en modo "Standby" si no se cumplen los requisitos.
"""

import os
import sys
import json
import logging
import subprocess
import time
import socket
import threading
import argparse
import signal
from datetime import datetime
from typing import Dict, Optional, Tuple
import sqlite3
import hashlib
import requests
import psutil

class Gatekeeper:
    """Gatekeeper de seguridad para módulos Venice."""

    def __init__(self, config: Dict):
        self.config = config
        self.logger = self._setup_logging()
        self.db_path = config.get("db_path", "/data/data/com.termux/files/home/aura_intel.db")
        self.ssh_host = config.get("ssh_host", "localhost")
        self.ssh_port = config.get("ssh_port", 8022)
        self.ssh_user = config.get("ssh_user", "user")
        self.node_id = config.get("node_id", "mobile_node_001")
        self.min_battery_percent = config.get("min_battery_percent", 30)
        self.min_disk_space_mb = config.get("min_disk_space_mb", 100)
        self.ssh_test_command = config.get("ssh_test_command", "echo 'SSH_TEST_SUCCESS'")
        self.standby_mode_script = config.get("standby_mode_script", "/data/data/com.termux/files/home/enter_standby.sh")
        self.aura_server_url = config.get("aura_server_url", "http://localhost:3000/api/alerts")
        self.aura_auth_token = config.get("aura_auth_token", "aura_gatekeeper_token_123")
        self.running = False
        self.shutdown_event = threading.Event()
        self.module_to_execute = None
        self.module_args = None
        self.validation_results = {}
        self.lock = threading.Lock()

    def _setup_logging(self):
        """Configura el logging para el gatekeeper."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('/data/data/com.termux/files/home/gatekeeper.log'),
                logging.StreamHandler()
            ]
        )
        logger = logging.getLogger("Gatekeeper")
        logger.setLevel(logging.INFO)
        return logger

    def _execute_command(self, command: list) -> Tuple[bool, str, str]:
        """Ejecuta un comando en el sistema y devuelve el resultado."""
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.config.get("command_timeout", 30)
            )
            if result.returncode == 0:
                return True, result.stdout, result.stderr
            else:
                return False, "", result.stderr
        except subprocess.TimeoutExpired:
            return False, "", f"Timeout al ejecutar comando: {' '.join(command)}"
        except Exception as e:
            return False, "", f"Error al ejecutar comando: {str(e)}"

    def _get_battery_level(self) -> Optional[float]:
        """Obtiene el nivel actual de batería del dispositivo."""
        try:
            success, stdout, stderr = self._execute_command(["termux-battery-status"])
            if success:
                try:
                    battery_info = json.loads(stdout)
                    return battery_info.get("percentage", 0)
                except json.JSONDecodeError:
                    self.logger.error(f"Error al parsear salida de termux-battery-status: {stderr}")
                    return None
            else:
                self.logger.error(f"Error al obtener nivel de batería: {stderr}")
                return None
        except Exception as e:
            self.logger.error(f"Error al obtener nivel de batería: {str(e)}")
            return None

    def _check_ssh_connection(self) -> bool:
        """Verifica que el túnel SSH esté estable."""
        try:
            # Intentar ejecutar un comando simple vía SSH
            success, stdout, stderr = self._execute_command([
                "ssh",
                f"-p", str(self.ssh_port),
                f"{self.ssh_user}@{self.ssh_host}",
                self.ssh_test_command
            ])

            if success and stdout.strip() == "SSH_TEST_SUCCESS":
                return True
            else:
                self.logger.error(f"Conexión SSH no estable: {stderr}")
                return False
        except Exception as e:
            self.logger.error(f"Error al verificar conexión SSH: {str(e)}")
            return False

    def _get_disk_space(self) -> Optional[float]:
        """Obtiene el espacio disponible en disco."""
        try:
            # Obtener espacio disponible en el directorio home de Termux
            stat = psutil.disk_usage('/data/data/com.termux/files/home')
            return stat.free / (1024 * 1024)  # Convertir a MB
        except Exception as e:
            self.logger.error(f"Error al obtener espacio en disco: {str(e)}")
            return None

    def _check_system_health(self) -> Dict:
        """Realiza todas las verificaciones de salud del sistema."""
        results = {
            "battery": None,
            "ssh_connection": None,
            "disk_space": None,
            "all_valid": True,
            "errors": []
        }

        # Verificar nivel de batería
        battery_level = self._get_battery_level()
        results["battery"] = battery_level
        if battery_level is not None and battery_level < self.min_battery_percent:
            results["all_valid"] = False
            results["errors"].append(f"Batería baja: {battery_level}% (requerido >{self.min_battery_percent}%)")

        # Verificar conexión SSH
        ssh_ok = self._check_ssh_connection()
        results["ssh_connection"] = ssh_ok
        if not ssh_ok:
            results["all_valid"] = False
            results["errors"].append("Conexión SSH no estable")

        # Verificar espacio en disco
        disk_space = self._get_disk_space()
        results["disk_space"] = disk_space
        if disk_space is not None and disk_space < self.min_disk_space_mb:
            results["all_valid"] = False
            results["errors"].append(f"Espacio en disco insuficiente: {disk_space:.2f}MB (requerido >{self.min_disk_space_mb}MB)")

        return results

    def _send_alert_to_aura(self, alert_type: str, message: str, details: Optional[Dict] = None) -> bool:
        """Envía una alerta al servidor AURA."""
        try:
            payload = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "node_id": self.node_id,
                "alert_type": alert_type,
                "severity": "critical",
                "message": message,
                "details": details or {},
                "source": "gatekeeper"
            }

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.aura_auth_token}"
            }

            response = requests.post(
                self.aura_server_url,
                json=payload,
                headers=headers,
                timeout=self.config.get("alert_timeout", 10)
            )

            if response.status_code == 200:
                self.logger.info(f"Alerta enviada a AURA: {alert_type}")
                return True
            else:
                self.logger.error(f"Error al enviar alerta a AURA: {response.text}")
                return False
        except Exception as e:
            self.logger.error(f"Error al enviar alerta a AURA: {str(e)}")
            return False

    def _enter_standby_mode(self):
        """Pone el sistema en modo Standby para proteger la integridad del nodo."""
        try:
            self.logger.warning("🛑 Modo Standby activado. Protegiendo la integridad del nodo.")

            # Ejecutar script de standby si existe
            if os.path.exists(self.standby_mode_script):
                success, stdout, stderr = self._execute_command([self.standby_mode_script])
                if not success:
                    self.logger.error(f"Error al ejecutar script de standby: {stderr}")

            # Registrar alerta en la base de datos local
            self._register_standby_alert()

            # Notificar a AURA
            self._send_alert_to_aura(
                "system_standby",
                "El nodo ha entrado en modo Standby debido a condiciones de seguridad no cumplidas",
                {
                    "validation_results": self.validation_results,
                    "node_id": self.node_id,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
            )

            # Esperar un tiempo antes de salir (para permitir que el sistema se estabilice)
            time.sleep(self.config.get("standby_delay", 30))

        except Exception as e:
            self.logger.error(f"Error al entrar en modo Standby: {str(e)}")

    def _register_standby_alert(self):
        """Registra una alerta de modo Standby en la base de datos local."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Verificar si ya existe una alerta de standby sin resolver
            cursor.execute("""
                SELECT id FROM alerts
                WHERE alert_type = ? AND resolved = 0
                ORDER BY timestamp DESC LIMIT 1
            """, ("system_standby",))

            existing_alert = cursor.fetchone()

            if existing_alert:
                # Actualizar la alerta existente
                cursor.execute("""
                    UPDATE alerts
                    SET message = ?, timestamp = ?, resolved = 0, details = ?
                    WHERE id = ?
                """, (
                    f"Modo Standby activado en {self.node_id} (actualización)",
                    datetime.utcnow().isoformat() + "Z",
                    json.dumps({
                        "validation_results": self.validation_results,
                        "node_id": self.node_id,
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    }),
                    existing_alert[0]
                ))
            else:
                # Insertar nueva alerta
                cursor.execute("""
                    INSERT INTO alerts (
                        alert_type, severity, message, timestamp, node_id, target,
                        resolved, details
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    "system_standby",
                    "critical",
                    f"Modo Standby activado en {self.node_id} debido a condiciones de seguridad no cumplidas",
                    datetime.utcnow().isoformat() + "Z",
                    self.node_id,
                    self.node_id,
                    0,
                    json.dumps({
                        "validation_results": self.validation_results,
                        "node_id": self.node_id,
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    })
                ))

            conn.commit()
            conn.close()
            self.logger.info("Alerta de modo Standby registrada en la base de datos local")

        except sqlite3.Error as e:
            self.logger.error(f"Error al registrar alerta de standby en la base de datos: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error al registrar alerta de standby: {str(e)}")

    def _initialize_database(self):
        """Inicializa la base de datos si no existe."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Crear tabla alerts si no existe
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    node_id TEXT,
                    target TEXT,
                    resolved BOOLEAN DEFAULT 0,
                    resolved_at DATETIME,
                    details TEXT
                )
            """)

            # Crear índice para búsquedas rápidas
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_node_id ON alerts(node_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_alert_type ON alerts(alert_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity)")

            conn.commit()
            conn.close()
            self.logger.info("Base de datos inicializada correctamente")

        except sqlite3.Error as e:
            self.logger.error(f"Error al inicializar la base de datos: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Error al inicializar la base de datos: {str(e)}")
            return False

        return True

    def _validate_and_execute(self, module_path: str, module_args: list):
        """Valida las condiciones de seguridad y ejecuta el módulo si todo está bien."""
        try:
            self.logger.info("🔒 Iniciando validación de seguridad para ejecutar módulo")

            # Guardar información del módulo a ejecutar
            self.module_to_execute = module_path
            self.module_args = module_args

            # Realizar verificaciones de salud
            self.validation_results = self._check_system_health()

            if not self.validation_results["all_valid"]:
                self.logger.error("❌ Validaciones de seguridad fallidas. Bloqueando ejecución del módulo.")
                self.logger.error(f"Errores detectados: {', '.join(self.validation_results['errors'])}")

                # Entrar en modo Standby
                self._enter_standby_mode()

                # Notificar al usuario
                print("❌ ERROR: Condiciones de seguridad no cumplidas. El módulo no se ejecutará.")
                print(f"   Detalles: {', '.join(self.validation_results['errors'])}")
                print("   El nodo ha entrado en modo Standby para proteger su integridad.")
                return False

            # Si todas las validaciones pasan, ejecutar el módulo
            self.logger.info("✅ Todas las validaciones de seguridad pasadas. Ejecutando módulo.")

            # Ejecutar el módulo
            command = [sys.executable, module_path] + module_args
            success, stdout, stderr = self._execute_command(command)

            if success:
                self.logger.info(f"✅ Módulo ejecutado con éxito: {module_path}")
                print(f"✅ Módulo ejecutado con éxito: {module_path}")
                return True
            else:
                self.logger.error(f"❌ Error al ejecutar módulo: {stderr}")
                print(f"❌ Error al ejecutar módulo: {stderr}")
                return False

        except Exception as e:
            self.logger.error(f"Error al validar y ejecutar módulo: {str(e)}")
            print(f"❌ Error al validar y ejecutar módulo: {str(e)}")
            return False

    def _monitor_system_health(self):
        """Monitorea constantemente la salud del sistema en segundo plano."""
        while not self.shutdown_event.is_set():
            try:
                # Realizar verificaciones periódicas
                health_check = self._check_system_health()

                if not health_check["all_valid"]:
                    self.logger.warning("⚠️  Condiciones de seguridad no cumplidas durante monitoreo")
                    self.logger.warning(f"Errores detectados: {', '.join(health_check['errors'])}")

                    # Si hay un módulo en ejecución, intentar detenerlo
                    if self.module_to_execute:
                        self.logger.warning("🛑 Intentando detener módulo en ejecución debido a condiciones de seguridad no cumplidas")
                        # En un entorno real, implementar un mecanismo para detener el módulo
                        # Esto es solo un ejemplo simplificado
                        print("⚠️  Advertencia: Condiciones de seguridad no cumplidas. El módulo actual podría estar en riesgo.")

                time.sleep(self.config.get("health_check_interval", 60))

            except Exception as e:
                self.logger.error(f"Error en el monitoreo de salud del sistema: {str(e)}")
                time.sleep(self.config.get("error_retry_delay", 60))

    def start(self, module_path: str, module_args: list):
        """Inicia el gatekeeper y valida la ejecución del módulo."""
        self.running = True
        self.shutdown_event.clear()
        self.logger.info("🚀 Gatekeeper de seguridad iniciado")

        # Inicializar base de datos
        if not self._initialize_database():
            self.logger.error("❌ Error al inicializar la base de datos. Deteniendo el gatekeeper.")
            self.running = False
            return False

        # Iniciar monitoreo de salud en segundo plano
        monitor_thread = threading.Thread(
            target=self._monitor_system_health,
            daemon=True,
            name="SystemHealthMonitorThread"
        )
        monitor_thread.start()

        # Validar y ejecutar el módulo
        success = self._validate_and_execute(module_path, module_args)

        # Detener el gatekeeper después de la validación
        self.running = False
        self.shutdown_event.set()

        return success

    def stop(self):
        """Detiene el gatekeeper."""
        if self.running:
            self.running = False
            self.shutdown_event.set()
            self.logger.info("🛑 Gatekeeper detenido")

def load_config(config_file: str = "/data/data/com.termux/files/home/gatekeeper_config.json") -> Dict:
    """Carga la configuración desde un archivo JSON."""
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        raise ValueError(f"Error al cargar configuración: {str(e)}")

def save_config(config: Dict, config_file: str = "/data/data/com.termux/files/home/gatekeeper_config.json"):
    """Guarda la configuración en un archivo JSON."""
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        raise ValueError(f"Error al guardar configuración: {str(e)}")

def setup_default_config() -> Dict:
    """Configura valores por defecto para el gatekeeper."""
    return {
        "version": "1.0.0",
        "description": "Configuración para el gatekeeper de seguridad AURA",
        "node_id": "mobile_node_001",
        "db_path": "/data/data/com.termux/files/home/aura_intel.db",
        "ssh_host": "localhost",
        "ssh_port": 8022,
        "ssh_user": "user",
        "ssh_test_command": "echo 'SSH_TEST_SUCCESS'",
        "min_battery_percent": 30,
        "min_disk_space_mb": 100,
        "standby_mode_script": "/data/data/com.termux/files/home/enter_standby.sh",
        "aura_server_url": "http://localhost:3000/api/alerts",
        "aura_auth_token": "aura_gatekeeper_token_123",
        "command_timeout": 30,
        "alert_timeout": 10,
        "health_check_interval": 60,
        "error_retry_delay": 60,
        "standby_delay": 30,
        "log_file": "/data/data/com.termux/files/home/gatekeeper.log",
        "enable_ssh_validation": true,
        "enable_battery_check": true,
        "enable_disk_check": true,
        "require_all_validations": true,
        "block_on_failure": true,
        "send_alerts_to_aura": true,
        "register_standby_alerts": true
    }

def main():
    """Punto de entrada principal del gatekeeper."""
    parser = argparse.ArgumentParser(description="Gatekeeper de seguridad para módulos Venice en dispositivos móviles.")
    parser.add_argument("--config", help="Archivo de configuración JSON", default="/data/data/com.termux/files/home/gatekeeper_config.json")
    parser.add_argument("--setup", action="store_true", help="Configurar valores por defecto")
    parser.add_argument("--test", action="store_true", help="Realizar pruebas de validación")
    parser.add_argument("--module", help="Ruta al módulo Venice a ejecutar")
    parser.add_argument("--args", nargs=argparse.REMAINDER, help="Argumentos para el módulo")
    args = parser.parse_args()

    try:
        if args.setup:
            config = setup_default_config()
            save_config(config)
            print("✅ Configuración por defecto guardada en gatekeeper_config.json")
            print("Por favor edita este archivo según tu configuración antes de iniciar el servicio.")
            return

        config = load_config(args.config)
        gatekeeper = Gatekeeper(config)

        if args.test:
            print("🔍 Realizando pruebas de validación...")
            results = gatekeeper._check_system_health()
            print(f"📡 Resultados de validación:")
            for check, value in results.items():
                if check != "all_valid" and check != "errors":
                    print(f"   - {check.replace('_', ' ').title()}: {value}")
            if not results["all_valid"]:
                print(f"   ❌ Errores detectados: {', '.join(results['errors'])}")
            else:
                print("   ✅ Todas las validaciones pasadas")
            return

        if args.module and args.args:
            print(f"🔒 Validando y ejecutando módulo: {args.module}")
            success = gatekeeper.start(args.module, args.args)
            if success:
                print("✅ Módulo ejecutado con éxito")
            else:
                print("❌ Error al ejecutar módulo")
            return

        print("🚀 Gatekeeper de seguridad listo para uso.")
        print("Ejemplos de uso:")
        print("  python gatekeeper.py --setup (Configurar valores por defecto)")
        print("  python gatekeeper.py --test (Realizar pruebas de validación)")
        print("  python gatekeeper.py --module /data/data/com.termux/files/home/.aura/module.py --args arg1 arg2 (Ejecutar módulo con validación)")

    except Exception as e:
        print(f"❌ Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()