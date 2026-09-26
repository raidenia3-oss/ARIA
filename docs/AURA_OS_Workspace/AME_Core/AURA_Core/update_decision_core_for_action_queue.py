"""
update_decision_core_for_action_queue.py - Actualización del Decision Core para soportar Action Queue
Este script actualiza el Decision Core para manejar acciones que requieren aprobación.
"""

import os
import sys
import time
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import socketio
import requests
from dotenv import load_dotenv

# Configuración del logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

# Configuración del sistema
class DecisionCoreConfig:
    def __init__(self):
        self.server_url = "http://localhost:5002"
        self.socket_url = "http://localhost:5002"
        self.log_file = "agent_decisions.log"
        self.rules_file = "decision_rules.json"
        self.action_queue_url = "http://localhost:5004"  # Puerto para Action Queue Manager
        self.default_rules = {
            "threat_rules": [
                {
                    "condition": {
                        "type": "Amenaza",
                        "severity": ["Alta", "Crítica"]
                    },
                    "actions": [
                        {"type": "Bloquear_IP", "target": "metadata.ip"},
                        {"type": "Notificar", "channel": "security_team", "message": "Amenaza detectada: {{title}} (Severidad: {{severity}})"},
                        {"type": "Actualizar_Estado", "node": "security", "status": "threat_detected"}
                    ]
                },
                {
                    "condition": {
                        "type": "Scan",
                        "severity": ["Media", "Alta"]
                    },
                    "actions": [
                        {"type": "Notificar", "channel": "security_team", "message": "Escaneo detectado: {{title}} (Origen: {{metadata.ip}})"},
                        {"type": "Registrar_Evento", "event": "network_scan_detected", "details": "{{details}}"}
                    ]
                },
                {
                    "condition": {
                        "type": "Phishing"
                    },
                    "actions": [
                        {"type": "Notificar", "channel": "security_team", "message": "Posible campaña de phishing detectada: {{title}}"},
                        {"type": "Notificar", "channel": "users", "message": "Advertencia: Posible intento de phishing detectado"},
                        {"type": "Guardar_en_Obsidian", "node": "phishing_campaigns", "title": "{{title}}", "details": "{{description}}"}
                    ]
                },
                {
                    "condition": {
                        "type": "OSINT_Found"
                    },
                    "actions": [
                        {"type": "Guardar_en_Obsidian", "node": "osint_findings", "title": "{{title}}", "details": "{{description}}"},
                        {"type": "Crear_Nuevo_Nodo", "type": "osint", "data": "{{details}}"},
                        {"type": "Notificar", "channel": "research_team", "message": "Nuevo hallazgo OSINT: {{title}}"}
                    ]
                },
                {
                    "condition": {
                        "severity": "Crítica"
                    },
                    "actions": [
                        {"type": "Notificar", "channel": "all", "message": "ALERTA CRÍTICA: {{title}} (Severidad: {{severity}})", "priority": "high"},
                        {"type": "Actualizar_Estado", "node": "security", "status": "critical_threat"}
                    ]
                }
            ],
            "default_actions": [
                {"type": "Registrar_Evento", "event": "alert_processed", "details": "Alerta {{id}} procesada a las {{timestamp}}"}
            ]
        }

        # Cargar reglas desde archivo si existe
        self.rules = self.load_rules()

    def load_rules(self) -> Dict:
        """Cargar reglas desde archivo JSON"""
        try:
            if Path(self.rules_file).exists():
                with open(self.rules_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return self.default_rules
        except Exception as e:
            logger.error(f"Error al cargar reglas: {e}")
            return self.default_rules

    def save_rules(self, rules: Dict) -> bool:
        """Guardar reglas en archivo JSON"""
        try:
            with open(self.rules_file, 'w', encoding='utf-8') as f:
                json.dump(rules, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Error al guardar reglas: {e}")
            return False

class DecisionCore:
    def __init__(self):
        self.config = DecisionCoreConfig()
        self.sio = socketio.Client(logger=True, engineio_logger=True)
        self.action_queue_sio = socketio.Client(logger=True, engineio_logger=True)
        self.connected = False
        self.action_queue_connected = False
        self.setup_logging()
        self.setup_socket_events()

    def setup_logging(self):
        """Configurar sistema de logging"""
        self.log_file_path = Path(self.config.log_file)
        if not self.log_file_path.exists():
            with open(self.log_file_path, 'w', encoding='utf-8') as f:
                f.write("# Log de decisiones del agente AURA\n")
                f.write(f"# Iniciado: {datetime.utcnow().isoformat()}\n")
                f.write("# ============================================\n\n")

    def log_decision(self, decision_data: Dict):
        """Registrar una decisión en el log"""
        try:
            timestamp = datetime.utcnow().isoformat()
            log_entry = {
                "timestamp": timestamp,
                "decision": decision_data,
                "status": "processed"
            }

            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] DECISIÓN:\n")
                f.write(f"  ID: {decision_data.get('alert_id', 'desconocido')}\n")
                f.write(f"  Tipo: {decision_data.get('alert_type', 'desconocido')}\n")
                f.write(f"  Acciones: {len(decision_data.get('actions', []))}\n")
                f.write(f"  Detalles: {decision_data.get('details', 'N/A')}\n")
                f.write(f"  Resultado: {'Éxito' if decision_data.get('status', 'error') == 'success' else 'Error'}\n")
                f.write("  ============================================\n\n")

            logger.info(f"Decisión registrada: {decision_data.get('alert_id', 'desconocido')}")
            return True
        except Exception as e:
            logger.error(f"Error al registrar decisión: {e}")
            return False

    def setup_socket_events(self):
        """Configurar eventos para Socket.IO"""
        connected = False
        action_queue_connected = False

        @self.sio.on('connect')
        def on_connect():
            nonlocal connected
            connected = True
            logger.info("🔗 Conexión WebSocket establecida con el Decision Core")
            self.sio.emit('subscribe', {'room': 'decision_engine'})
            self.report_status("connected")

        @self.sio.on('disconnect')
        def on_disconnect():
            nonlocal connected
            connected = False
            logger.warning("⚠️ Desconectado del servidor WebSocket")
            self.report_status("disconnected")

        @self.sio.on('new_alert')
        def on_new_alert(alert_data):
            """Procesar alertas entrantes"""
            logger.info(f"🚨 Nueva alerta recibida para procesamiento: {alert_data.get('id', 'desconocido')}")
            self.process_alert(alert_data)

        @self.sio.on('config_update')
        def on_config_update(config_data):
            """Actualizar configuración del sistema"""
            logger.info("🔄 Configuración actualizada recibida")
            self.report_status("config_updated")

        @self.action_queue_sio.on('connect')
        def on_action_queue_connect():
            nonlocal action_queue_connected
            action_queue_connected = True
            logger.info("🔗 Conexión WebSocket establecida con Action Queue Manager")
            self.action_queue_sio.emit('subscribe', {'room': 'action_queue'})

        @self.action_queue_sio.on('disconnect')
        def on_action_queue_disconnect():
            nonlocal action_queue_connected
            action_queue_connected = False
            logger.warning("⚠️ Desconectado del Action Queue Manager")

        @self.action_queue_sio.on('execute_approved_action')
        def on_execute_approved_action(action_data):
            """Recibir solicitud de ejecución de acción aprobada"""
            logger.info(f"🤖 Ejecutando acción aprobada: {action_data.get('action_id', 'desconocido')}")
            self.execute_approved_action(action_data)

    def connect(self):
        """Conectarse al servidor principal"""
        try:
            logger.info("🔌 Conectando Decision Core al servidor principal...")
            self.sio.connect(self.config.socket_url, transports=['websocket'])

            # Conectar también al Action Queue Manager
            self.action_queue_sio.connect(self.config.action_queue_url, transports=['websocket'])

            return True
        except Exception as e:
            logger.error(f"Error al conectar Decision Core: {e}")
            return False

    def disconnect(self):
        """Desconectarse del servidor"""
        try:
            if self.connected:
                self.sio.disconnect()
                logger.info("🔌 Decision Core desconectado del servidor principal")

            if self.action_queue_connected:
                self.action_queue_sio.disconnect()
                logger.info("🔌 Decision Core desconectado del Action Queue Manager")

            return True
        except Exception as e:
            logger.error(f"Error al desconectar Decision Core: {e}")
            return False

    def report_status(self, status: str, message: str = ""):
        """Reportar estado al dashboard"""
        try:
            status_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "status": status,
                "message": message,
                "component": "decision_core",
                "version": "1.0.0",
                "action_queue_connected": self.action_queue_connected
            }

            if self.connected:
                self.sio.emit('agent_status', status_data)
            else:
                logger.warning("No se pudo reportar estado: No conectado a WebSocket")

            # También guardar en log local
            self.log_decision({
                "alert_id": "status_report",
                "alert_type": "system_status",
                "actions": [f"Reportar estado: {status}"],
                "details": message,
                "status": "success"
            })

            return True
        except Exception as e:
            logger.error(f"Error al reportar estado: {e}")
            return False

    def process_alert(self, alert_data: Dict):
        """Procesar una alerta entrante y tomar decisiones"""
        try:
            logger.info(f"🤖 Procesando alerta: {alert_data.get('id', 'desconocido')} ({alert_data.get('type', 'desconocido')})")

            # Preparar datos para procesamiento
            alert_id = alert_data.get('id', 'unknown')
            alert_type = alert_data.get('type', 'unknown')
            alert_severity = alert_data.get('severity', 'unknown')
            alert_title = alert_data.get('title', 'Sin título')
            alert_description = alert_data.get('description', '')
            alert_metadata = alert_data.get('metadata', {})
            alert_details = alert_data.get('details', [])

            # Inicializar lista de acciones
            actions_taken = []
            decision_result = {
                "alert_id": alert_id,
                "alert_type": alert_type,
                "severity": alert_severity,
                "timestamp": datetime.utcnow().isoformat(),
                "actions": [],
                "status": "processing",
                "details": f"Alerta procesada: {alert_title}"
            }

            # 1. Evaluar reglas específicas
            matched_rules = self.evaluate_rules(alert_data)
            logger.info(f"🎯 {len(matched_rules)} reglas aplicables encontradas para esta alerta")

            # 2. Ejecutar acciones de las reglas coincidentes
            for rule in matched_rules:
                for action in rule['actions']:
                    action_result = self.execute_action(action, alert_data)
                    if action_result:
                        actions_taken.append({
                            "rule": rule.get('name', 'desconocida'),
                            "action": action['type'],
                            "target": action.get('target', 'N/A'),
                            "status": action_result.get('status', 'success'),
                            "message": action_result.get('message', '')
                        })
                        decision_result['actions'].append({
                            "type": action['type'],
                            "target": action.get('target', 'N/A'),
                            "status": action_result.get('status', 'success')
                        })

            # 3. Ejecutar acciones por defecto
            for action in self.config.rules['default_actions']:
                action_result = self.execute_action(action, alert_data)
                if action_result:
                    actions_taken.append({
                        "rule": "default",
                        "action": action['type'],
                        "target": action.get('target', 'N/A'),
                        "status": action_result.get('status', 'success'),
                        "message": action_result.get('message', '')
                    })
                    decision_result['actions'].append({
                        "type": action['type'],
                        "target": action.get('target', 'N/A'),
                        "status": action_result.get('status', 'success')
                    })

            # 4. Registrar la decisión
            decision_result['status'] = 'success'
            decision_result['actions_taken'] = len(actions_taken)
            self.log_decision(decision_result)

            # 5. Reportar estado al dashboard
            self.report_status(
                "alert_processed",
                f"Procesada alerta {alert_id}: {alert_type} (Severidad: {alert_severity})"
            )

            logger.info(f"✅ Alerta procesada con éxito: {alert_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Error al procesar alerta {alert_data.get('id', 'desconocido')}: {e}")

            # Registrar error
            error_decision = {
                "alert_id": alert_data.get('id', 'unknown'),
                "alert_type": alert_data.get('type', 'unknown'),
                "severity": alert_data.get('severity', 'unknown'),
                "timestamp": datetime.utcnow().isoformat(),
                "actions": [],
                "status": "error",
                "details": f"Error al procesar alerta: {str(e)}",
                "error": str(e)
            }
            self.log_decision(error_decision)

            # Reportar error
            self.report_status(
                "alert_processing_error",
                f"Error al procesar alerta {alert_data.get('id', 'desconocido')}: {str(e)}"
            )

            return False

    def execute_approved_action(self, action_data: Dict):
        """Ejecutar una acción que fue aprobada por el Action Queue"""
        try:
            logger.info(f"🤖 Ejecutando acción aprobada: {action_data.get('action_id', 'desconocido')}")

            # Crear resultado de la acción
            action_result = {
                "action_id": action_data.get('action_id', 'unknown'),
                "action_type": action_data.get('action_type', 'unknown'),
                "timestamp": datetime.utcnow().isoformat(),
                "status": "executed",
                "details": f"Acción ejecutada: {action_data.get('action_type', 'Desconocido')}",
                "metadata": action_data.get('metadata', {})
            }

            # Ejecutar la acción específica
            if action_data.get('action_type') == "Bloquear_IP":
                ip_address = action_data.get('metadata', {}).get('ip', 'N/A')
                if ip_address:
                    logger.info(f"🔒 Bloqueando IP: {ip_address}")
                    # Aquí iría la lógica real para bloquear la IP
                    action_result['details'] = f"IP {ip_address} bloqueada con éxito"
                else:
                    action_result['status'] = 'warning'
                    action_result['details'] = "No se encontró dirección IP para bloquear"

            elif action_data.get('action_type') == "Guardar_en_Obsidian":
                node_type = action_data.get('node', 'general')
                title = action_data.get('title', 'Sin título')
                details = action_data.get('details', '')

                logger.info(f"📝 Guardando en Obsidian: {title} (Nodo: {node_type})")
                # Aquí iría la lógica real para guardar en Obsidian
                action_result['details'] = f"Contenido guardado en Obsidian (nodo: {node_type})"

            elif action_data.get('action_type') == "Crear_Nuevo_Nodo":
                node_type = action_data.get('type', 'osint')
                data = action_data.get('data', {})

                logger.info(f"🌐 Creando nuevo nodo: {node_type}")
                # Aquí iría la lógica real para crear nodos
                action_result['details'] = f"Nuevo nodo creado ({node_type})"

            elif action_data.get('action_type') == "Notificar":
                channel = action_data.get('channel', 'default')
                message = action_data.get('message', '')

                logger.info(f"📢 Notificando a {channel}: {message[:50]}...")
                # Aquí iría la lógica real para enviar notificaciones
                action_result['details'] = f"Notificación enviada a {channel}"

            # Registrar la ejecución de la acción
            self.log_action_execution(action_result)

            # Reportar estado al dashboard
            self.report_status(
                "action_executed",
                f"Acción ejecutada: {action_data.get('action_id', 'desconocido')}"
            )

            logger.info(f"✅ Acción ejecutada con éxito: {action_data.get('action_id', 'desconocido')}")
            return True

        except Exception as e:
            logger.error(f"❌ Error al ejecutar acción aprobada {action_data.get('action_id', 'desconocido')}: {e}")

            # Registrar error
            error_result = {
                "action_id": action_data.get('action_id', 'unknown'),
                "action_type": action_data.get('action_type', 'unknown'),
                "timestamp": datetime.utcnow().isoformat(),
                "status": "error",
                "details": f"Error al ejecutar acción: {str(e)}",
                "error": str(e)
            }
            self.log_action_execution(error_result)

            # Reportar error
            self.report_status(
                "action_execution_error",
                f"Error al ejecutar acción {action_data.get('action_id', 'desconocido')}: {str(e)}"
            )

            return False

    def evaluate_rules(self, alert_data: Dict) -> List[Dict]:
        """Evaluar qué reglas aplican a esta alerta"""
        matched_rules = []
        alert_type = alert_data.get('type', '')
        alert_severity = alert_data.get('severity', '')

        # Corregir la estructura de rules para que sea compatible
        rules_to_check = []
        for rule_name, rule_config in self.config.rules['threat_rules']:
            rules_to_check.append({
                "name": rule_name,
                "condition": rule_config['condition'],
                "actions": rule_config['actions']
            })

        for rule in rules_to_check:
            # Evaluar condición del tipo
            type_match = True
            if 'type' in rule['condition']:
                if rule['condition']['type'] != alert_type and rule['condition']['type'] != 'all':
                    type_match = False

            # Evaluar condición de severidad
            severity_match = True
            if 'severity' in rule['condition']:
                if isinstance(rule['condition']['severity'], list):
                    if alert_severity not in rule['condition']['severity']:
                        severity_match = False
                else:
                    if rule['condition']['severity'] != alert_severity:
                        severity_match = False

            if type_match and severity_match:
                matched_rules.append(rule)

        return matched_rules

    def execute_action(self, action: Dict, alert_data: Dict) -> Optional[Dict]:
        """Ejecutar una acción específica"""
        action_type = action['type']
        result = {
            "status": "success",
            "message": f"Accion {action_type} ejecutada"
        }

        try:
            if action_type == "Bloquear_IP":
                ip_address = self.get_value_from_alert(action.get('target', 'metadata.ip'), alert_data)
                if ip_address:
                    logger.info(f"🔒 Bloqueando IP: {ip_address}")

                    # Verificar si esta acción requiere aprobación
                    if self.requires_approval_for_action(action_type, alert_data):
                        # Si requiere aprobación, no ejecutar aquí, solo registrar
                        return {
                            "status": "pending_approval",
                            "message": f"Acción {action_type} requiere aprobación",
                            "details": {"action": action_type, "target": ip_address}
                        }
                    else:
                        # Ejecutar directamente
                        return {
                            "status": "success",
                            "message": f"IP {ip_address} marcada para bloqueo",
                            "details": {"action": "block_ip", "target": ip_address}
                        }
                else:
                    return {
                        "status": "warning",
                        "message": f"No se encontró dirección IP para bloquear en la alerta",
                        "details": {"action": "block_ip", "target": action.get('target', 'metadata.ip')}
                    }

            elif action_type == "Notificar":
                channel = action.get('channel', 'default')
                message_template = action.get('message', 'Alerta procesada: {{title}}')
                priority = action.get('priority', 'normal')

                # Construir mensaje
                message = message_template.format(
                    title=alert_data.get('title', 'Sin título'),
                    severity=alert_data.get('severity', 'Desconocida'),
                    type=alert_data.get('type', 'Desconocido'),
                    source=alert_data.get('source', 'Desconocido'),
                    ip=alert_data.get('metadata', {}).get('ip', 'N/A'),
                    details=json.dumps(alert_data.get('details', []))
                )

                logger.info(f"📢 Notificación a {channel}: {message[:50]}...")
                return {
                    "status": "success",
                    "message": f"Notificación enviada a {channel}",
                    "details": {"action": "notify", "channel": channel, "message": message}
                }

            elif action_type == "Guardar_en_Obsidian":
                node_type = action.get('node', 'general')
                title = action.get('title', alert_data.get('title', 'Sin título'))
                details = action.get('details', alert_data.get('description', ''))

                logger.info(f"📝 Guardando en Obsidian: {title} (Nodo: {node_type})")

                # Verificar si esta acción requiere aprobación
                if self.requires_approval_for_action(action_type, alert_data):
                    return {
                        "status": "pending_approval",
                        "message": f"Acción {action_type} requiere aprobación",
                        "details": {"action": action_type, "node": node_type, "title": title}
                    }
                else:
                    return {
                        "status": "success",
                        "message": f"Contenido guardado en Obsidian (nodo: {node_type})",
                        "details": {"action": "save_to_obsidian", "node": node_type, "title": title}
                    }

            elif action_type == "Crear_Nuevo_Nodo":
                node_type = action.get('type', 'osint')
                data = action.get('data', alert_data.get('details', []))

                logger.info(f"🌐 Creando nuevo nodo: {node_type}")

                # Verificar si esta acción requiere aprobación
                if self.requires_approval_for_action(action_type, alert_data):
                    return {
                        "status": "pending_approval",
                        "message": f"Acción {action_type} requiere aprobación",
                        "details": {"action": action_type, "type": node_type, "data": data}
                    }
                else:
                    return {
                        "status": "success",
                        "message": f"Nuevo nodo creado ({node_type})",
                        "details": {"action": "create_node", "type": node_type, "data": data}
                    }

            elif action_type == "Actualizar_Estado":
                node = action.get('node', 'security')
                status = action.get('status', 'updated')

                logger.info(f"🔄 Actualizando estado del nodo: {node} -> {status}")
                return {
                    "status": "success",
                    "message": f"Estado actualizado para nodo {node}",
                    "details": {"action": "update_status", "node": node, "status": status}
                }

            elif action_type == "Registrar_Evento":
                event_type = action.get('event', 'alert_processed')
                details = action.get('details', alert_data.get('description', ''))

                logger.info(f"📋 Registrando evento: {event_type}")
                return {
                    "status": "success",
                    "message": f"Evento registrado: {event_type}",
                    "details": {"action": "register_event", "event": event_type, "details": details}
                }

            else:
                return {
                    "status": "warning",
                    "message": f"Accion desconocida: {action_type}",
                    "details": {"action": action_type}
                }

        except Exception as e:
            logger.error(f"Error al ejecutar acción {action_type}: {e}")
            return {
                "status": "error",
                "message": f"Error al ejecutar acción {action_type}: {str(e)}",
                "details": {"action": action_type, "error": str(e)}
            }

    def requires_approval_for_action(self, action_type, alert_data):
        """Determinar si una acción específica requiere aprobación"""
        try:
            # Acciones que siempre requieren aprobación
            if action_type in ['Bloquear_IP', 'Guardar_en_Obsidian', 'Crear_Nuevo_Nodo']:
                return True

            # Acciones que requieren aprobación según el contexto
            alert_type = alert_data.get('type', '').lower()
            alert_severity = alert_data.get('severity', '').lower()
            alert_metadata = alert_data.get('metadata', {})

            # Si la alerta es crítica o de alta severidad, algunas acciones requieren aprobación
            if alert_severity in ['critical', 'high']:
                if action_type == 'Notificar' and alert_data.get('metadata', {}).get('channel') in ['security_team', 'all']:
                    return True

            # Si la alerta es de tipo phishing, malware o data_leak, algunas acciones requieren aprobación
            if alert_type in ['phishing', 'malware', 'data_leak']:
                if action_type == 'Notificar':
                    return True

            return False

        except Exception as e:
            logger.error(f"Error al determinar si requiere aprobación: {e}")
            return False

    def get_value_from_alert(self, path: str, alert_data: Dict) -> Optional[str]:
        """Obtener un valor de la alerta usando notación de camino"""
        try:
            keys = path.split('.')
            value = alert_data

            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                elif isinstance(value, list) and key.isdigit() and int(key) < len(value):
                    value = value[int(key)]
                else:
                    return None

            return value if value is not None else None
        except Exception as e:
            logger.error(f"Error al obtener valor {path} de alerta: {e}")
            return None

    def log_action_execution(self, action_data: Dict):
        """Registrar ejecución de acción en el log"""
        try:
            timestamp = datetime.utcnow().isoformat()
            log_entry = {
                "timestamp": timestamp,
                "action": action_data,
                "status": action_data.get('status', 'unknown')
            }

            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] EJECUCIÓN DE ACCIÓN: {action_data.get('action_type', 'desconocido')} - {action_data.get('status', 'desconocido')}\n")
                f.write(f"  ID: {action_data.get('action_id', 'desconocido')}\n")
                f.write(f"  Detalles: {action_data.get('details', 'N/A')}\n")
                f.write(f"  Estado: {action_data.get('status', 'desconocido')}\n")
                f.write("  ============================================\n\n")

            logger.info(f"Ejecución de acción registrada: {action_data.get('action_id', 'desconocido')} - {action_data.get('status', 'desconocido')}")
            return True
        except Exception as e:
            logger.error(f"Error al registrar ejecución de acción: {e}")
            return False

    def get_status(self) -> Dict:
        """Obtener estado actual del Decision Core"""
        return {
            "status": "operational" if self.connected else "disconnected",
            "timestamp": datetime.utcnow().isoformat(),
            "connected": self.connected,
            "action_queue_connected": self.action_queue_connected,
            "last_alert_processed": self.get_last_alert_time(),
            "rules_loaded": len(self.config.rules['threat_rules']),
            "log_file": str(self.log_file_path),
            "version": "1.0.0"
        }

    def get_last_alert_time(self) -> str:
        """Obtener hora de la última alerta procesada (de los logs)"""
        try:
            if self.log_file_path.exists():
                with open(self.log_file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if lines:
                        last_line = lines[-1]
                        if '[' in last_line and ']' in last_line:
                            timestamp_str = last_line.split('[')[1].split(']')[0]
                            return timestamp_str
            return "Nunca"
        except Exception as e:
            logger.error(f"Error al obtener última hora de alerta: {e}")
            return "Desconocido"

def main():
    """Función principal para iniciar el Decision Core"""
    logger.info("🚀 Iniciando Decision Core para AURA con soporte para Action Queue")
    logger.info("📋 Configuración cargada desde decision_core.py")

    # Inicializar Decision Core
    decision_core = DecisionCore()

    # Conectar al servidor
    if decision_core.connect():
        logger.info("✅ Decision Core conectado y listo para procesar alertas")

        # Reportar estado inicial
        decision_core.report_status("initialized", "Decision Core listo para operar")

        try:
            # Mantener el Decision Core en ejecución
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("🛑 Decision Core detenido por el usuario")
        finally:
            decision_core.disconnect()
            logger.info("🔌 Decision Core desconectado")
    else:
        logger.error("❌ No se pudo conectar Decision Core al servidor")
        return False

    return True

if __name__ == "__main__":
    main()