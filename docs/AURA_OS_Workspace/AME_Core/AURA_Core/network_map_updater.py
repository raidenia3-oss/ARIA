#!/usr/bin/env python3
"""
network_map_updater.py - Script para procesar y actualizar el Network Map en el servidor AURA.
Este script recibe payloads de dispositivos de red desde los sensores móviles y actualiza
la base de datos central, el dashboard y genera alertas según corresponda.

Características:
- Procesa payloads JSON de dispositivos de red.
- Actualiza la base de datos central con información de dispositivos.
- Genera alertas para dispositivos desconocidos o sospechosos.
- Actualiza el Network Map para visualización en el dashboard.
- Integra con el sistema de tareas y alertas de AURA.
"""

import os
import sys
import json
import logging
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
import argparse
import hashlib
import time
from mobile_database_manager import MobileDatabaseManager

class NetworkMapUpdater:
    """Actualizador del Network Map en el servidor AURA."""

    def __init__(self, config: Dict):
        self.config = config
        self.logger = self._setup_logging()
        self.db_path = config.get("db_path", "/data/data/com.termux/files/home/aura_intel.db")
        self.mobile_db_manager = MobileDatabaseManager(config.get("mobile_db_config", {}))
        self.alert_threshold = config.get("alert_threshold", "high")
        self.known_devices_file = config.get("known_devices_file", "/data/data/com.termux/files/home/known_devices.json")
        self.network_map_file = config.get("network_map_file", "/data/data/com.termux/files/home/network_map.json")
        self.alert_destination = config.get("alert_destination", "dashboard")
        self.device_whitelist = config.get("device_whitelist", [])
        self.device_blacklist = config.get("device_blacklist", [])
        self.alert_severity_mapping = config.get("alert_severity_mapping", {
            "unknown_device": "high",
            "new_device": "medium",
            "disappeared_device": "low",
            "changed_device": "medium"
        })

    def _setup_logging(self):
        """Configura el logging para el actualizador del Network Map."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('/data/data/com.termux/files/home/network_map_updater.log'),
                logging.StreamHandler()
            ]
        )
        logger = logging.getLogger("NetworkMapUpdater")
        logger.setLevel(logging.INFO)
        return logger

    def _load_payload(self, payload_file: str) -> Dict:
        """Carga el payload JSON desde un archivo."""
        try:
            with open(payload_file, 'r') as f:
                payload = json.load(f)
            return payload
        except Exception as e:
            self.logger.error(f"Error al cargar payload: {str(e)}")
            return {}

    def _save_network_map(self, network_map: Dict):
        """Guarda el Network Map en un archivo JSON."""
        try:
            with open(self.network_map_file, 'w') as f:
                json.dump(network_map, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error al guardar Network Map: {str(e)}")

    def _initialize_database(self):
        """Inicializa la base de datos si no existe."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Crear tabla devices si no existe
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mac TEXT UNIQUE NOT NULL,
                    ip TEXT,
                    vendor TEXT,
                    first_seen DATETIME,
                    last_seen DATETIME,
                    status TEXT,
                    node_id TEXT,
                    details TEXT,
                    is_known BOOLEAN DEFAULT 0,
                    is_whitelisted BOOLEAN DEFAULT 0,
                    is_blacklisted BOOLEAN DEFAULT 0,
                    alert_severity TEXT,
                    alert_message TEXT,
                    alert_timestamp DATETIME,
                    resolved BOOLEAN DEFAULT 0
                )
            """)

            # Crear tabla network_changes si no existe
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS network_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    node_id TEXT,
                    interface TEXT,
                    network_prefix TEXT,
                    change_type TEXT NOT NULL,
                    device_mac TEXT NOT NULL,
                    device_ip TEXT,
                    device_vendor TEXT,
                    old_status TEXT,
                    new_status TEXT,
                    details TEXT,
                    severity TEXT,
                    resolved BOOLEAN DEFAULT 0
                )
            """)

            # Crear índices para búsquedas rápidas
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_devices_mac ON devices(mac)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_devices_ip ON devices(ip)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_devices_node_id ON devices(node_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_network_changes_timestamp ON network_changes(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_network_changes_device_mac ON network_changes(device_mac)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_network_changes_node_id ON network_changes(node_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_network_changes_severity ON network_changes(severity)")

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

    def _update_device_in_db(self, device: Dict, change_type: str, details: Optional[Dict] = None) -> bool:
        """Actualiza un dispositivo en la base de datos."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Verificar si el dispositivo ya existe
            cursor.execute("""
                SELECT id, is_known, is_whitelisted, is_blacklisted, status
                FROM devices
                WHERE mac = ?
            """, (device["mac"],))

            result = cursor.fetchone()

            # Determinar si el dispositivo es conocido, whitelisted o blacklisted
            is_known = device["mac"] in self.device_whitelist or result is not None
            is_whitelisted = device["mac"] in self.device_whitelist
            is_blacklisted = device["mac"] in self.device_blacklist

            # Determinar la severidad de la alerta
            severity = self.alert_severity_mapping.get(change_type, "medium")

            # Crear o actualizar el dispositivo
            if result:
                # Dispositivo existente - actualizar
                cursor.execute("""
                    UPDATE devices
                    SET ip = ?, vendor = ?, last_seen = ?, status = ?,
                        node_id = ?, details = ?, is_known = ?, is_whitelisted = ?,
                        is_blacklisted = ?, alert_severity = ?, alert_message = ?,
                        alert_timestamp = ?, resolved = 0
                    WHERE mac = ?
                """, (
                    device["ip"], device["vendor"], device["last_seen"],
                    device["status"], self.config.get("node_id", "unknown"),
                    json.dumps(device), is_known, is_whitelisted,
                    is_blacklisted, severity,
                    f"{change_type}: {device['ip']} ({device['mac']}) - {device.get('vendor', 'Unknown')}",
                    datetime.utcnow().isoformat() + "Z", device["mac"]
                ))
            else:
                # Nuevo dispositivo - insertar
                cursor.execute("""
                    INSERT INTO devices (
                        mac, ip, vendor, first_seen, last_seen, status, node_id,
                        details, is_known, is_whitelisted, is_blacklisted,
                        alert_severity, alert_message, alert_timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    device["mac"], device["ip"], device["vendor"], device["first_seen"],
                    device["last_seen"], device["status"], self.config.get("node_id", "unknown"),
                    json.dumps(device), is_known, is_whitelisted,
                    is_blacklisted, severity,
                    f"{change_type}: {device['ip']} ({device['mac']}) - {device.get('vendor', 'Unknown')}",
                    datetime.utcnow().isoformat() + "Z"
                ))

            # Registrar el cambio en la tabla network_changes
            cursor.execute("""
                INSERT INTO network_changes (
                    node_id, interface, network_prefix, change_type, device_mac,
                    device_ip, device_vendor, old_status, new_status, details,
                    severity
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self.config.get("node_id", "unknown"),
                self.config.get("interface", "wlan0"),
                self.config.get("network_prefix", "192.168.1."),
                change_type,
                device["mac"], device["ip"], device["vendor"],
                details.get("old_status", "unknown") if details else "unknown",
                device["status"],
                json.dumps(details) if details else json.dumps({}),
                severity
            ))

            conn.commit()
            conn.close()
            return True

        except sqlite3.Error as e:
            self.logger.error(f"Error al actualizar dispositivo en la base de datos: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Error al actualizar dispositivo: {str(e)}")
            return False

    def _register_alert(self, alert_type: str, device: Dict, change_type: str) -> bool:
        """Registra una alerta en la base de datos."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Insertar alerta en la tabla alerts
            cursor.execute("""
                INSERT INTO alerts (
                    alert_type, severity, message, timestamp, node_id, target,
                    resolved, details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert_type,
                self.alert_severity_mapping.get(change_type, "medium"),
                f"{change_type}: {device['ip']} ({device['mac']}) - {device.get('vendor', 'Unknown')}",
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
                    "status": device["status"],
                    "change_type": change_type
                })
            ))

            conn.commit()
            conn.close()
            return True

        except sqlite3.Error as e:
            self.logger.error(f"Error al registrar alerta: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Error al registrar alerta: {str(e)}")
            return False

    def _process_new_device(self, device: Dict) -> bool:
        """Procesa un nuevo dispositivo detectado."""
        self.logger.info(f"🆕 Nuevo dispositivo detectado: {device['ip']} ({device['mac']}) - {device['vendor']}")

        # Verificar si el dispositivo está en la whitelist o blacklist
        if device["mac"] in self.device_whitelist:
            self.logger.info(f"✅ Dispositivo whitelisted: {device['mac']}")
            return self._update_device_in_db(device, "new_device")

        if device["mac"] in self.device_blacklist:
            self.logger.warning(f"⚠️  Dispositivo blacklisted: {device['mac']}")
            device["status"] = "blacklisted"
            return self._update_device_in_db(device, "blacklisted_device")

        # Si el dispositivo es desconocido (fabricante "Unknown"), registrar alerta
        if device["vendor"] == "Unknown":
            self.logger.warning(f"🚨  Dispositivo desconocido detectado: {device['mac']}")
            self._register_alert("unknown_device", device, "new_device")
            device["status"] = "unknown"
            return self._update_device_in_db(device, "new_device")

        # Si el dispositivo es conocido pero nuevo en esta sesión, solo actualizar
        return self._update_device_in_db(device, "new_device")

    def _process_disappeared_device(self, device: Dict) -> bool:
        """Procesa un dispositivo que desapareció de la red."""
        self.logger.info(f"⚠️  Dispositivo desaparecido: {device['ip']} ({device['mac']})")

        # Actualizar el dispositivo como desaparecido
        device["status"] = "disappeared"
        return self._update_device_in_db(device, "disappeared_device")

    def _process_changed_device(self, device: Dict, old_device: Dict) -> bool:
        """Procesa un dispositivo que cambió (ej: fabricante cambiado)."""
        self.logger.info(f"🔄 Cambio detectado en dispositivo: {device['ip']} ({device['mac']})")

        # Determinar qué cambió
        changes = []
        if old_device.get("vendor", "") != device.get("vendor", ""):
            changes.append(f"fabricante: {old_device.get('vendor', 'N/A')} -> {device.get('vendor', 'N/A')}")

        if old_device.get("status", "") != device.get("status", ""):
            changes.append(f"estado: {old_device.get('status', 'N/A')} -> {device.get('status', 'N/A')}")

        change_details = {
            "old_vendor": old_device.get("vendor", ""),
            "new_vendor": device.get("vendor", ""),
            "old_status": old_device.get("status", ""),
            "new_status": device.get("status", ""),
            "changes": changes
        }

        # Si el dispositivo es desconocido ahora, registrar alerta
        if device["vendor"] == "Unknown":
            self.logger.warning(f"🚨  Dispositivo ahora desconocido: {device['mac']}")
            self._register_alert("unknown_device", device, "changed_device")

        return self._update_device_in_db(device, "changed_device", change_details)

    def _process_unchanged_device(self, device: Dict) -> bool:
        """Procesa un dispositivo que no cambió."""
        # Solo actualizar la última vez visto
        return self._update_device_in_db(device, "unchanged_device")

    def _build_network_map(self, payload: Dict) -> Dict:
        """Construye el Network Map a partir del payload recibido."""
        network_map = {
            "timestamp": payload.get("timestamp", datetime.utcnow().isoformat() + "Z"),
            "node_id": payload.get("node_id", "unknown"),
            "interface": payload.get("interface", "wlan0"),
            "network_prefix": payload.get("network_prefix", "192.168.1."),
            "devices": {},
            "summary": {
                "total_devices": 0,
                "new_devices": 0,
                "disappeared_devices": 0,
                "changed_devices": 0,
                "unknown_devices": 0,
                "whitelisted_devices": 0,
                "blacklisted_devices": 0
            },
            "changes": payload.get("changes", {})
        }

        # Procesar dispositivos nuevos
        for device in payload["changes"].get("new_devices", []):
            mac = device["mac"]
            network_map["devices"][mac] = device
            network_map["summary"]["total_devices"] += 1
            network_map["summary"]["new_devices"] += 1
            if device["vendor"] == "Unknown":
                network_map["summary"]["unknown_devices"] += 1

        # Procesar dispositivos desaparecidos
        for device in payload["changes"].get("disappeared_devices", []):
            mac = device["mac"]
            network_map["devices"][mac] = device
            network_map["summary"]["total_devices"] += 1
            network_map["summary"]["disappeared_devices"] += 1

        # Procesar dispositivos cambiados
        for device in payload["changes"].get("changed_devices", []):
            mac = device["mac"]
            network_map["devices"][mac] = device
            network_map["summary"]["total_devices"] += 1
            network_map["summary"]["changed_devices"] += 1
            if device["vendor"] == "Unknown":
                network_map["summary"]["unknown_devices"] += 1

        # Procesar dispositivos sin cambios (actualizar solo last_seen)
        for device in payload["changes"].get("unchanged_devices", []):
            mac = device["mac"]
            if mac in network_map["devices"]:
                # Actualizar solo last_seen si el dispositivo ya existe
                existing_device = network_map["devices"][mac]
                existing_device["last_seen"] = device["last_seen"]
            else:
                # Si no existe, añadirlo (debería estar en disappeared_devices)
                network_map["devices"][mac] = device
                network_map["summary"]["total_devices"] += 1

        # Actualizar resumen
        network_map["summary"]["total_devices"] = len(network_map["devices"])
        network_map["summary"]["whitelisted_devices"] = len([d for d in network_map["devices"].values()
                                                              if d["mac"] in self.device_whitelist])
        network_map["summary"]["blacklisted_devices"] = len([d for d in network_map["devices"].values()
                                                               if d["mac"] in self.device_blacklist])

        return network_map

    def _update_mobile_database(self, payload: Dict):
        """Actualiza la base de datos móvil con la información de red."""
        try:
            # Obtener los dispositivos de los cambios
            devices = []
            for change_type in ["new_devices", "disappeared_devices", "changed_devices", "unchanged_devices"]:
                devices.extend(payload["changes"].get(change_type, []))

            if not devices:
                return

            # Preparar consultas para insertar/actualizar dispositivos
            queries = []

            for device in devices:
                # Verificar si el dispositivo ya existe en la base de datos móvil
                existing_devices = self.mobile_db_manager.execute_query("""
                    SELECT * FROM devices WHERE mac = ?
                """, [device["mac"]])

                if existing_devices:
                    # Actualizar dispositivo existente
                    queries.append({
                        "query": """
                            UPDATE devices
                            SET ip = ?, vendor = ?, last_seen = ?, status = ?,
                                details = ?
                            WHERE mac = ?
                        """,
                        "params": (
                            device["ip"], device["vendor"], device["last_seen"],
                            device["status"], json.dumps(device), device["mac"]
                        )
                    })
                else:
                    # Insertar nuevo dispositivo
                    queries.append({
                        "query": """
                            INSERT INTO devices (
                                mac, ip, vendor, first_seen, last_seen, status, details
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        "params": (
                            device["mac"], device["ip"], device["vendor"],
                            device["first_seen"], device["last_seen"],
                            device["status"], json.dumps(device)
                        )
                    })

            # Ejecutar las consultas en la base de datos móvil
            if queries:
                success = self.mobile_db_manager.execute_transaction(queries)
                if success:
                    self.logger.info("📡 Base de datos móvil actualizada con información de red")
                else:
                    self.logger.error("❌ Error al actualizar base de datos móvil")

        except Exception as e:
            self.logger.error(f"Error al actualizar base de datos móvil: {str(e)}")

    def process_payload(self, payload_file: str) -> bool:
        """Procesa un payload de red recibido y actualiza el Network Map."""
        try:
            # Cargar el payload
            payload = self._load_payload(payload_file)
            if not payload:
                self.logger.error("Payload vacío o inválido")
                return False

            self.logger.info(f"📥 Procesando payload de red desde {payload.get('node_id', 'desconocido')}")

            # Inicializar base de datos si es necesario
            if not self._initialize_database():
                self.logger.error("Error al inicializar la base de datos")
                return False

            # Construir el Network Map
            network_map = self._build_network_map(payload)

            # Procesar cada tipo de cambio
            for device in payload["changes"].get("new_devices", []):
                self._process_new_device(device)

            for device in payload["changes"].get("disappeared_devices", []):
                self._process_disappeared_device(device)

            for device in payload["changes"].get("changed_devices", []):
                # Para dispositivos cambiados, necesitamos el estado anterior
                # En este ejemplo, asumimos que el payload contiene suficiente información
                self._process_changed_device(device, {})

            for device in payload["changes"].get("unchanged_devices", []):
                self._process_unchanged_device(device)

            # Actualizar la base de datos móvil
            self._update_mobile_database(payload)

            # Guardar el Network Map
            self._save_network_map(network_map)

            # Enviar alertas si es necesario
            if payload["changes"].get("new_devices"):
                for device in payload["changes"]["new_devices"]:
                    if device["vendor"] == "Unknown":
                        self._register_alert("unknown_device", device, "new_device")

            self.logger.info("✅ Network Map actualizado correctamente")
            return True

        except Exception as e:
            self.logger.error(f"Error al procesar payload: {str(e)}")
            return False

def load_config(config_file: str = "/data/data/com.termux/files/home/network_map_updater_config.json") -> Dict:
    """Carga la configuración desde un archivo JSON."""
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        raise ValueError(f"Error al cargar configuración: {str(e)}")

def save_config(config: Dict, config_file: str = "/data/data/com.termux/files/home/network_map_updater_config.json"):
    """Guarda la configuración en un archivo JSON."""
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        raise ValueError(f"Error al guardar configuración: {str(e)}")

def setup_default_config() -> Dict:
    """Configura valores por defecto para el actualizador del Network Map."""
    return {
        "version": "1.0.0",
        "description": "Configuración para el actualizador del Network Map AURA",
        "node_id": "server_node_001",
        "interface": "eth0",
        "network_prefix": "192.168.1.",
        "db_path": "/data/data/com.termux/files/home/aura_intel.db",
        "known_devices_file": "/data/data/com.termux/files/home/known_devices.json",
        "network_map_file": "/data/data/com.termux/files/home/network_map.json",
        "alert_threshold": "high",
        "alert_destination": "dashboard",
        "device_whitelist": [
            "00:11:22:33:44:55",
            "AA:BB:CC:DD:EE:FF"
        ],
        "device_blacklist": [
            "FF:FF:FF:FF:FF:FF",
            "00:00:00:00:00:00"
        ],
        "alert_severity_mapping": {
            "unknown_device": "high",
            "new_device": "medium",
            "disappeared_device": "low",
            "changed_device": "medium"
        },
        "mobile_db_config": {
            "version": "1.0.0",
            "db_path": "/data/data/com.termux/files/home/aura_intel.db",
            "ssh_host": "localhost",
            "ssh_port": 8022,
            "ssh_user": "user",
            "ssh_timeout": 30
        },
        "log_file": "/data/data/com.termux/files/home/network_map_updater.log",
        "enable_alerts": true,
        "enable_network_map": true,
        "enable_mobile_db_sync": true,
        "last_updated": "2026-06-02T00:00:00Z"
    }

def main():
    """Punto de entrada principal del actualizador del Network Map."""
    parser = argparse.ArgumentParser(description="Actualizador del Network Map en el servidor AURA.")
    parser.add_argument("--config", help="Archivo de configuración JSON", default="/data/data/com.termux/files/home/network_map_updater_config.json")
    parser.add_argument("--setup", action="store_true", help="Configurar valores por defecto")
    parser.add_argument("--payload", help="Archivo con el payload de red a procesar")
    args = parser.parse_args()

    try:
        if args.setup:
            config = setup_default_config()
            save_config(config)
            print("✅ Configuración por defecto guardada en network_map_updater_config.json")
            print("Por favor edita este archivo según tu configuración antes de iniciar el servicio.")
            return

        config = load_config(args.config)
        updater = NetworkMapUpdater(config)

        if args.payload:
            success = updater.process_payload(args.payload)
            if success:
                print("✅ Payload procesado con éxito")
            else:
                print("❌ Error al procesar el payload")
            return

        print("🚀 Actualizador del Network Map listo para uso.")
        print("Ejemplos de uso:")
        print("  python network_map_updater.py --setup (Configurar valores por defecto)")
        print("  python network_map_updater.py --payload /tmp/aura_network_payload.json (Procesar payload)")

    except Exception as e:
        print(f"❌ Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()