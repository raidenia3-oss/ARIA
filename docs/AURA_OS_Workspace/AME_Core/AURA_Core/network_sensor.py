#!/usr/bin/env python3
"""
network_sensor.py - Sensor de red para Termux que mapea dispositivos en la red local.
Este script utiliza nmap y arp-scan para detectar dispositivos, filtrar cambios y enviar
alertas al servidor AURA cuando se detectan nuevos hosts o cambios en la topología.

Características:
- Detección automática de dispositivos en la red local.
- Comparación con el estado anterior para detectar cambios.
- Envío de payload JSON al servidor AURA vía SSH.
- Registro de dispositivos desconocidos en la base de datos aura_intel.db.
- Alertas para dispositivos nuevos o sospechosos.
"""

import os
import sys
import json
import subprocess
import time
import logging
import socket
import hashlib
from datetime import datetime, timedelta
import argparse
import requests
import sqlite3
from typing import Dict, List, Optional, Tuple

class NetworkSensor:
    """Sensor de red para detectar dispositivos en la red local."""

    def __init__(self, config: Dict):
        self.config = config
        self.logger = self._setup_logging()
        self.known_devices_file = config.get("known_devices_file", "/data/data/com.termux/files/home/known_devices.json")
        self.db_path = config.get("db_path", "/data/data/com.termux/files/home/aura_intel.db")
        self.ssh_host = config.get("ssh_host", "localhost")
        self.ssh_port = config.get("ssh_port", 8022)
        self.ssh_user = config.get("ssh_user", "user")
        self.scan_interval = config.get("scan_interval", 60)  # segundos
        self.max_retries = config.get("max_retries", 3)
        self.retry_delay = config.get("retry_delay", 5)
        self.interface = config.get("interface", "wlan0")
        self.network_prefix = config.get("network_prefix", "192.168.1.")
        self.known_devices = self._load_known_devices()
        self.last_scan_time = None
        self.running = False
        self.shutdown_event = threading.Event()

    def _setup_logging(self):
        """Configura el logging para el sensor de red."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('/data/data/com.termux/files/home/network_sensor.log'),
                logging.StreamHandler()
            ]
        )
        logger = logging.getLogger("NetworkSensor")
        logger.setLevel(logging.INFO)
        return logger

    def _load_known_devices(self) -> Dict:
        """Carga los dispositivos conocidos desde el archivo JSON."""
        try:
            if os.path.exists(self.known_devices_file):
                with open(self.known_devices_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            self.logger.error(f"Error al cargar dispositivos conocidos: {str(e)}")
            return {}

    def _save_known_devices(self, devices: Dict):
        """Guarda los dispositivos conocidos en el archivo JSON."""
        try:
            with open(self.known_devices_file, 'w') as f:
                json.dump(devices, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error al guardar dispositivos conocidos: {str(e)}")

    def _execute_command(self, command: List[str]) -> Tuple[bool, str, str]:
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

    def _get_mac_vendor(self, mac: str) -> str:
        """Obtiene el fabricante de una dirección MAC usando nmap."""
        try:
            # Usar nmap para obtener el fabricante (si está disponible)
            success, stdout, stderr = self._execute_command([
                "nmap", "-e", self.interface, "-sn", mac
            ])

            if success and stdout:
                # Buscar la línea con el fabricante
                for line in stdout.split('\n'):
                    if 'MAC Address:' in line and ('(unknown)' not in line):
                        parts = line.split()
                        if len(parts) > 2:
                            return parts[-1].strip('()')
            return "Unknown"
        except Exception as e:
            self.logger.error(f"Error al obtener fabricante para MAC {mac}: {str(e)}")
            return "Unknown"

    def _scan_network(self) -> List[Dict]:
        """Escanea la red local y devuelve una lista de dispositivos."""
        devices = []

        try:
            # Usar arp-scan para obtener la lista de dispositivos
            success, stdout, stderr = self._execute_command([
                "arp-scan", "--interface=" + self.interface, "--localnet"
            ])

            if not success:
                self.logger.warning(f"arp-scan falló: {stderr}")
                # Intentar con nmap como alternativa
                success, stdout, stderr = self._execute_command([
                    "nmap", "-sn", self.network_prefix + "0/24"
                ])
                if not success:
                    self.logger.error(f"Ambos escaneos fallaron: {stderr}")
                    return devices

            # Procesar la salida de arp-scan
            if success and stdout:
                lines = stdout.split('\n')
                for line in lines[2:]:  # Saltar las primeras 2 líneas (encabezados)
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 3:
                            ip = parts[0]
                            mac = parts[2].lower()
                            vendor = self._get_mac_vendor(mac)

                            devices.append({
                                "ip": ip,
                                "mac": mac,
                                "vendor": vendor,
                                "first_seen": datetime.utcnow().isoformat() + "Z",
                                "last_seen": datetime.utcnow().isoformat() + "Z",
                                "status": "active"
                            })

            # Si no se encontraron dispositivos con arp-scan, intentar con nmap
            if not devices:
                success, stdout, stderr = self._execute_command([
                    "nmap", "-sn", self.network_prefix + "0/24"
                ])
                if success and stdout:
                    for line in stdout.split('\n'):
                        if 'Nmap scan report' in line:
                            ip = line.split()[3]
                            next_line = stdout.split('\n')[stdout.split('\n').index(line) + 1]
                            if 'MAC Address:' in next_line:
                                mac_part = next_line.split('MAC Address:')[1].split('(')[0].strip()
                                mac = mac_part.replace(' ', '').replace('(', '').replace(')', '')
                                vendor = self._get_mac_vendor(mac)

                                devices.append({
                                    "ip": ip,
                                    "mac": mac,
                                    "vendor": vendor,
                                    "first_seen": datetime.utcnow().isoformat() + "Z",
                                    "last_seen": datetime.utcnow().isoformat() + "Z",
                                    "status": "active"
                                })

        except Exception as e:
            self.logger.error(f"Error al escanear la red: {str(e)}")

        return devices

    def _compare_network_states(self, current_devices: List[Dict], previous_devices: Dict) -> Dict:
        """Compara el estado actual de la red con el anterior y detecta cambios."""
        changes = {
            "new_devices": [],
            "disappeared_devices": [],
            "changed_devices": [],
            "unchanged_devices": []
        }

        # Convertir dispositivos actuales a un diccionario por MAC para comparación fácil
        current_devices_dict = {device["mac"]: device for device in current_devices}
        previous_devices_dict = previous_devices

        # Detectar dispositivos nuevos
        for mac, device in current_devices_dict.items():
            if mac not in previous_devices_dict:
                changes["new_devices"].append(device)
                self.logger.info(f"🆕 Nuevo dispositivo detectado: {device['ip']} ({device['mac']}) - {device['vendor']}")

        # Detectar dispositivos desaparecidos
        for mac, device in previous_devices_dict.items():
            if mac not in current_devices_dict:
                device["last_seen"] = datetime.utcnow().isoformat() + "Z"
                device["status"] = "disappeared"
                changes["disappeared_devices"].append(device)
                self.logger.info(f"⚠️  Dispositivo desaparecido: {device['ip']} ({device['mac']})")

        # Detectar dispositivos existentes (actualizados o sin cambios)
        for mac, current_device in current_devices_dict.items():
            if mac in previous_devices_dict:
                previous_device = previous_devices_dict[mac]
                current_device["last_seen"] = datetime.utcnow().isoformat() + "Z"

                # Verificar si hay cambios significativos
                if (current_device["vendor"] != previous_device.get("vendor", "")):
                    changes["changed_devices"].append(current_device)
                    self.logger.info(f"🔄 Cambio detectado en dispositivo: {current_device['ip']} ({current_device['mac']}) - Fabricante cambiado a {current_device['vendor']}")

                # Si no hay cambios significativos, añadir a dispositivos sin cambios
                else:
                    changes["unchanged_devices"].append(current_device)

        return changes

    def _send_to_aura_server(self, payload: Dict) -> bool:
        """Envía el payload al servidor AURA vía SSH."""
        try:
            # Crear un script temporal para enviar los datos
            script_content = f"""#!/bin/bash
# Script para enviar datos de red al servidor AURA
# Payload: {json.dumps(payload)}

# Guardar el payload en un archivo temporal
echo '{json.dumps(payload)}' > /tmp/aura_network_payload.json

# Enviar el archivo al servidor AURA vía SSH
scp -P {self.ssh_port} /tmp/aura_network_payload.json {self.ssh_user}@{self.ssh_host}:/tmp/aura_network_payload.json

# Limpiar el archivo temporal
rm -f /tmp/aura_network_payload.json

# Ejecutar el script de procesamiento en el servidor
ssh -p {self.ssh_port} {self.ssh_user}@{self.ssh_host} "python3 /data/data/com.termux/files/home/aura_core/network_map_updater.py /tmp/aura_network_payload.json"

echo "Payload enviado con éxito al servidor AURA"
"""

            # Guardar el script en un archivo temporal
            script_path = "/tmp/send_to_aura.sh"
            with open(script_path, 'w') as f:
                f.write(script_content)

            # Hacer el script ejecutable y ejecutarlo
            os.chmod(script_path, 0o755)
            success, stdout, stderr = self._execute_command([script_path])

            # Limpiar el script temporal
            os.remove(script_path)

            if success:
                self.logger.info("Payload enviado con éxito al servidor AURA")
                return True
            else:
                self.logger.error(f"Error al enviar payload al servidor AURA: {stderr}")
                return False

        except Exception as e:
            self.logger.error(f"Error al enviar payload al servidor AURA: {str(e)}")
            return False

    def _register_unknown_device(self, device: Dict) -> bool:
        """Registra un dispositivo desconocido en la base de datos aura_intel.db."""
        try:
            # Intentar conectar a la base de datos local
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Verificar si el dispositivo ya existe
            cursor.execute("""
                SELECT id FROM alerts
                WHERE node_id = ? AND target = ?
            """, (self.config.get("node_id", "unknown"), device["mac"]))

            if cursor.fetchone():
                self.logger.info(f"Dispositivo {device['mac']} ya registrado como alerta")
                conn.close()
                return True

            # Insertar alerta por dispositivo desconocido
            cursor.execute("""
                INSERT INTO alerts (
                    alert_type, severity, message, timestamp, node_id, target,
                    resolved, details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "unknown_device",
                "high",
                f"Nuevo dispositivo desconocido detectado: {device['ip']} ({device['mac']}) - {device['vendor']}",
                datetime.utcnow().isoformat() + "Z",
                self.config.get("node_id", "unknown"),
                device["mac"],
                0,
                json.dumps({
                    "ip": device["ip"],
                    "mac": device["mac"],
                    "vendor": device["vendor"],
                    "first_seen": device["first_seen"],
                    "last_seen": device["last_seen"],
                    "status": "new_unknown_device"
                })
            ))

            conn.commit()
            conn.close()
            self.logger.info(f"🚨 Alerta registrada en la base de datos: {device['mac']}")
            return True

        except sqlite3.Error as e:
            self.logger.error(f"Error al registrar dispositivo desconocido en la base de datos: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Error al registrar dispositivo desconocido: {str(e)}")
            return False

    def _process_changes(self, changes: Dict):
        """Procesa los cambios detectados en la red."""
        # Crear payload para enviar al servidor AURA
        payload = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "node_id": self.config.get("node_id", "unknown"),
            "interface": self.interface,
            "network_prefix": self.network_prefix,
            "changes": changes,
            "summary": {
                "new_devices": len(changes["new_devices"]),
                "disappeared_devices": len(changes["disappeared_devices"]),
                "changed_devices": len(changes["changed_devices"]),
                "total_devices": len(changes["new_devices"]) + len(changes["disappeared_devices"]) +
                                len(changes["changed_devices"]) + len(changes["unchanged_devices"])
            }
        }

        # Enviar payload al servidor AURA
        if self._send_to_aura_server(payload):
            # Registrar dispositivos desconocidos en la base de datos
            for device in changes["new_devices"]:
                if device["vendor"] == "Unknown":
                    self._register_unknown_device(device)

    def _update_known_devices(self, current_devices: List[Dict]):
        """Actualiza la lista de dispositivos conocidos."""
        known_devices = {}
        for device in current_devices:
            mac = device["mac"]
            known_devices[mac] = {
                "ip": device["ip"],
                "mac": mac,
                "vendor": device["vendor"],
                "first_seen": device["first_seen"],
                "last_seen": device["last_seen"],
                "status": device["status"]
            }

        self.known_devices = known_devices
        self._save_known_devices(known_devices)

    def _check_dependencies(self) -> bool:
        """Verifica que las dependencias necesarias estén instaladas."""
        required_tools = ["nmap", "arp-scan"]

        for tool in required_tools:
            success, _, _ = self._execute_command(["which", tool])
            if not success:
                self.logger.error(f"Herramienta requerida no encontrada: {tool}")
                return False

        return True

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
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_target ON alerts(target)")
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

    def _monitor_network(self):
        """Monitorea la red local en segundo plano."""
        while not self.shutdown_event.is_set():
            try:
                self.logger.info("🔍 Iniciando escaneo de red local...")
                current_devices = self._scan_network()

                if not current_devices:
                    self.logger.warning("No se detectaron dispositivos en la red")
                else:
                    self.logger.info(f"📡 {len(current_devices)} dispositivos detectados en la red")

                    # Comparar con el estado anterior
                    changes = self._compare_network_states(current_devices, self.known_devices)

                    # Procesar cambios detectados
                    if (changes["new_devices"] or changes["disappeared_devices"] or
                        changes["changed_devices"]):
                        self._process_changes(changes)
                        self.logger.info("📊 Cambios procesados y enviados al servidor AURA")

                    # Actualizar dispositivos conocidos
                    self._update_known_devices(current_devices)

                # Actualizar tiempo del último escaneo
                self.last_scan_time = datetime.utcnow()

                # Esperar hasta el próximo escaneo
                time.sleep(self.scan_interval)

            except Exception as e:
                self.logger.error(f"Error en el monitoreo de red: {str(e)}")
                time.sleep(self.retry_delay)

    def start(self):
        """Inicia el sensor de red."""
        self.running = True
        self.shutdown_event.clear()
        self.logger.info("🚀 Sensor de red iniciado")

        # Verificar dependencias
        if not self._check_dependencies():
            self.logger.error("❌ Dependencias no encontradas. Deteniendo el sensor.")
            self.running = False
            return

        # Inicializar base de datos
        if not self._initialize_database():
            self.logger.error("❌ Error al inicializar la base de datos. Deteniendo el sensor.")
            self.running = False
            return

        # Iniciar monitoreo en segundo plano
        import threading
        monitor_thread = threading.Thread(
            target=self._monitor_network,
            daemon=True,
            name="NetworkMonitorThread"
        )
        monitor_thread.start()

        # Esperar a que se presione Ctrl+C
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("🛑 Sensor de red detenido por el usuario")
        finally:
            self.stop()

    def stop(self):
        """Detiene el sensor de red."""
        if self.running:
            self.running = False
            self.shutdown_event.set()
            self.logger.info("🛑 Sensor de red detenido")

def load_config(config_file: str = "/data/data/com.termux/files/home/network_sensor_config.json") -> Dict:
    """Carga la configuración desde un archivo JSON."""
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        raise ValueError(f"Error al cargar configuración: {str(e)}")

def save_config(config: Dict, config_file: str = "/data/data/com.termux/files/home/network_sensor_config.json"):
    """Guarda la configuración en un archivo JSON."""
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        raise ValueError(f"Error al guardar configuración: {str(e)}")

def setup_default_config() -> Dict:
    """Configura valores por defecto para el sensor de red."""
    return {
        "version": "1.0.0",
        "description": "Configuración para el sensor de red AURA en Termux",
        "node_id": "mobile_node_001",
        "interface": "wlan0",
        "network_prefix": "192.168.1.",
        "known_devices_file": "/data/data/com.termux/files/home/known_devices.json",
        "db_path": "/data/data/com.termux/files/home/aura_intel.db",
        "ssh_host": "localhost",
        "ssh_port": 8022,
        "ssh_user": "user",
        "scan_interval": 60,  # segundos
        "max_retries": 3,
        "retry_delay": 5,
        "command_timeout": 30,
        "log_file": "/data/data/com.termux/files/home/network_sensor.log",
        "alert_threshold": "high",
        "vendor_lookup_enabled": True
    }

def main():
    """Punto de entrada principal del sensor de red."""
    parser = argparse.ArgumentParser(description="Sensor de red para detectar dispositivos en la red local.")
    parser.add_argument("--config", help="Archivo de configuración JSON", default="/data/data/com.termux/files/home/network_sensor_config.json")
    parser.add_argument("--setup", action="store_true", help="Configurar valores por defecto")
    parser.add_argument("--scan", action="store_true", help="Realizar un escaneo manual de la red")
    parser.add_argument("--test", action="store_true", help="Probar la conexión con el servidor AURA")
    args = parser.parse_args()

    try:
        if args.setup:
            config = setup_default_config()
            save_config(config)
            print("✅ Configuración por defecto guardada en network_sensor_config.json")
            print("Por favor edita este archivo según tu configuración antes de iniciar el servicio.")
            return

        config = load_config(args.config)
        sensor = NetworkSensor(config)

        if args.scan:
            print("🔍 Realizando escaneo manual de la red...")
            devices = sensor._scan_network()
            print(f"📡 {len(devices)} dispositivos detectados:")
            for device in devices:
                print(f"   - {device['ip']} ({device['mac']}) - {device['vendor']}")
            return

        if args.test:
            test_payload = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "node_id": config.get("node_id", "test_node"),
                "interface": config.get("interface", "wlan0"),
                "test_message": "Prueba de conexión con el servidor AURA",
                "devices": [
                    {"ip": "192.168.1.1", "mac": "00:11:22:33:44:55", "vendor": "Cisco"},
                    {"ip": "192.168.1.100", "mac": "AA:BB:CC:DD:EE:FF", "vendor": "Apple"}
                ]
            }
            success = sensor._send_to_aura_server(test_payload)
            if success:
                print("✅ Prueba de conexión exitosa con el servidor AURA")
            else:
                print("❌ Error al probar la conexión con el servidor AURA")
            return

        print("🚀 Sensor de red listo para uso.")
        print("Ejemplos de uso:")
        print("  python network_sensor.py --setup (Configurar valores por defecto)")
        print("  python network_sensor.py --scan (Realizar escaneo manual)")
        print("  python network_sensor.py --test (Probar conexión con el servidor)")
        print("  python network_sensor.py (Iniciar sensor en segundo plano)")

        # Iniciar el sensor
        sensor.start()

    except Exception as e:
        print(f"❌ Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    import threading
    main()