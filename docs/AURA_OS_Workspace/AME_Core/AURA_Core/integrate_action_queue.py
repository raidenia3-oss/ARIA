"""
integrate_action_queue.py - Integración del Action Queue Manager con el sistema de datos
Este script integra el Action Queue Manager con el servidor de datos en tiempo real
y configura la comunicación bidireccional para acciones que requieren aprobación.
"""

import os
import sys
import time
import json
import logging
from pathlib import Path
import socketio
from dotenv import load_dotenv

# Configuración del logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

class ActionQueueIntegration:
    def __init__(self):
        self.server_url = "http://localhost:5002"
        self.socket_url = "http://localhost:5002"
        self.action_queue_url = "http://localhost:5004"  # Puerto para Action Queue Manager
        self.sio = socketio.Client(logger=True, engineio_logger=True)
        self.connected = False
        self.setup_socket_events()

    def setup_socket_events(self):
        """Configurar eventos para Socket.IO"""
        connected = False

        @self.sio.on('connect')
        def on_connect():
            nonlocal connected
            connected = True
            logger.info("🔗 Conexión WebSocket establecida con el servidor principal")
            self.sio.emit('subscribe', {'room': 'global'})
            self.sio.emit('subscribe', {'room': 'action_queue'})

        @self.sio.on('disconnect')
        def on_disconnect():
            nonlocal connected
            connected = False
            logger.warning("⚠️ Desconectado del servidor WebSocket principal")

        @self.sio.on('new_alert')
        def on_new_alert(alert_data):
            """Redirigir alertas al Decision Core y Action Queue si es necesario"""
            logger.info(f"🚨 Alerta recibida: {alert_data.get('id', 'desconocido')}")

            # Verificar si esta alerta requiere aprobación
            if self.requires_approval(alert_data):
                self.forward_to_action_queue(alert_data)
            else:
                # Si no requiere aprobación, procesar directamente con Decision Core
                self.forward_to_decision_core(alert_data)

        @self.sio.on('action_approved')
        def on_action_approved(action_data):
            """Recibir notificación de acción aprobada"""
            logger.info(f"✅ Acción aprobada: {action_data.get('action_id', 'desconocido')}")
            self.forward_to_decision_core_for_execution(action_data)

        @self.sio.on('action_denied')
        def on_action_denied(action_data):
            """Recibir notificación de acción denegada"""
            logger.info(f"❌ Acción denegada: {action_data.get('action_id', 'desconocido')}")
            self.log_action_denied(action_data)

        @self.sio.on('action_queue_status')
        def on_action_queue_status(status_data):
            """Recibir estado del Action Queue Manager"""
            logger.info(f"📡 Estado del Action Queue: {status_data.get('status', 'desconocido')}")
            self.broadcast_action_queue_status(status_data)

    def connect(self):
        """Conectarse al servidor principal"""
        try:
            logger.info("🔌 Conectando al servidor principal...")
            self.sio.connect(self.socket_url, transports=['websocket'])
            return True
        except Exception as e:
            logger.error(f"Error al conectar al servidor principal: {e}")
            return False

    def disconnect(self):
        """Desconectarse del servidor"""
        try:
            if self.connected:
                self.sio.disconnect()
                logger.info("🔌 Desconectado del servidor principal")
            return True
        except Exception as e:
            logger.error(f"Error al desconectar del servidor: {e}")
            return False

    def requires_approval(self, alert_data):
        """Determinar si una alerta requiere aprobación"""
        try:
            # Las acciones que requieren aprobación son:
            # 1. Bloquear IPs
            # 2. Guardar en Obsidian (para contenido sensible)
            # 3. Crear nuevos nodos (para información crítica)
            # 4. Notificaciones a canales sensibles

            action_type = alert_data.get('type', '').lower()
            action_details = alert_data.get('details', [])

            # Verificar si hay acciones que requieren aprobación en los detalles
            for detail in action_details:
                if isinstance(detail, dict):
                    if detail.get('type') in ['block_ip', 'save_to_obsidian', 'create_node'] and detail.get('value', '').lower() in ['critical', 'sensitive', 'high_risk']:
                        return True

            # Verificar tipo de alerta
            if action_type in ['phishing', 'critical_threat', 'data_leak', 'malware']:
                return True

            # Verificar severidad
            if alert_data.get('severity', '').lower() in ['critical', 'high']:
                return True

            return False

        except Exception as e:
            logger.error(f"Error al determinar si requiere aprobación: {e}")
            return False

    def forward_to_action_queue(self, alert_data):
        """Redirigir alerta al Action Queue Manager para aprobación"""
        try:
            logger.info(f"🔄 Redirigiendo alerta al Action Queue para aprobación: {alert_data.get('id', 'desconocido')}")

            # Crear solicitud de aprobación
            action_request = {
                "action_id": alert_data.get('id', 'unknown'),
                "action_type": alert_data.get('type', 'unknown'),
                "details": alert_data.get('description', ''),
                "metadata": alert_data.get('metadata', {}),
                "timestamp": alert_data.get('timestamp', ''),
                "timeout": 300,  # 5 minutos por defecto
                "severity": alert_data.get('severity', 'medium'),
                "source": alert_data.get('source', 'unknown')
            }

            # Enviar solicitud al Action Queue Manager
            if self.connected:
                self.sio.emit('action_approval_request', action_request)

            # Registrar en logs
            self.log_action_requested(action_request)

            return True
        except Exception as e:
            logger.error(f"Error al redirigir alerta al Action Queue: {e}")
            return False

    def forward_to_decision_core(self, alert_data):
        """Redirigir alerta al Decision Core para procesamiento directo"""
        try:
            logger.info(f"🤖 Redirigiendo alerta al Decision Core: {alert_data.get('id', 'desconocido')}")

            # Enviar alerta al Decision Core (simulado)
            # En un entorno real, esto enviaría la alerta al Decision Core

            # Simular procesamiento por parte del Decision Core
            time.sleep(1)  # Simular tiempo de procesamiento

            # Crear resultado simulado
            result_data = {
                "alert_id": alert_data.get('id', 'unknown'),
                "alert_type": alert_data.get('type', 'unknown'),
                "severity": alert_data.get('severity', 'unknown'),
                "timestamp": alert_data.get('timestamp', ''),
                "actions_taken": 1,
                "status": "success",
                "details": f"Alerta procesada directamente: {alert_data.get('title', 'Sin título')}",
                "decision_time": alert_data.get('timestamp', '')
            }

            # Enviar resultado al servidor principal
            self.broadcast_decision_result(result_data)

            return True
        except Exception as e:
            logger.error(f"Error al redirigir alerta al Decision Core: {e}")
            return False

    def forward_to_decision_core_for_execution(self, action_data):
        """Redirigir acción aprobada al Decision Core para ejecución"""
        try:
            logger.info(f"🤖 Redirigiendo acción aprobada al Decision Core: {action_data.get('action_id', 'desconocido')}")

            # Crear alerta simulada para el Decision Core
            alert_for_decision_core = {
                "id": action_data.get('action_id', 'unknown'),
                "timestamp": action_data.get('timestamp', ''),
                "source": "action_queue",
                "type": action_data.get('action_type', 'approved_action'),
                "severity": action_data.get('severity', 'medium'),
                "title": f"Acción aprobada: {action_data.get('action_type', 'Desconocido')}",
                "description": action_data.get('details', ''),
                "metadata": {
                    "action_id": action_data.get('action_id', 'unknown'),
                    "action_type": action_data.get('action_type', 'unknown'),
                    "status": "approved",
                    "timestamp": action_data.get('timestamp', '')
                },
                "details": [
                    {
                        "type": "action_details",
                        "value": action_data.get('details', '')
                    },
                    {
                        "type": "action_metadata",
                        "value": action_data.get('metadata', {})
                    }
                ]
            }

            # Enviar alerta al Decision Core (simulado)
            # En un entorno real, esto enviaría la alerta al Decision Core

            # Simular procesamiento por parte del Decision Core
            time.sleep(1)  # Simular tiempo de procesamiento

            # Crear resultado simulado
            result_data = {
                "alert_id": alert_for_decision_core.get('id', 'unknown'),
                "alert_type": alert_for_decision_core.get('type', 'unknown'),
                "severity": alert_for_decision_core.get('severity', 'unknown'),
                "timestamp": alert_for_decision_core.get('timestamp', ''),
                "actions_taken": 1,
                "status": "success",
                "details": f"Acción ejecutada: {action_data.get('action_type', 'Desconocido')}",
                "decision_time": alert_for_decision_core.get('timestamp', '')
            }

            # Enviar resultado al servidor principal
            self.broadcast_decision_result(result_data)

            # Notificar que la acción fue ejecutada
            self.broadcast_action_executed(action_data.get('action_id', 'unknown'))

            return True
        except Exception as e:
            logger.error(f"Error al redirigir acción aprobada al Decision Core: {e}")
            return False

    def broadcast_decision_result(self, result_data):
        """Enviar resultado de decisión a todos los clientes suscritos"""
        try:
            logger.info(f"📢 Enviando resultado de decisión a clientes: {result_data.get('alert_id', 'desconocido')}")

            # Enviar evento personalizado con el resultado de la decisión
            self.sio.emit('decision_result', result_data)

            # También enviar como alerta procesada
            processed_alert = {
                "id": result_data.get('alert_id'),
                "timestamp": result_data.get('decision_time', result_data.get('timestamp', '')),
                "source": "decision_engine",
                "type": "decision_processed",
                "severity": "info",
                "title": f"Decisión procesada: {result_data.get('alert_type', 'desconocido')}",
                "description": result_data.get('details', ''),
                "metadata": {
                    "actions_taken": result_data.get('actions_taken', 0),
                    "status": result_data.get('status', 'unknown'),
                    "original_alert": result_data.get('alert_id', 'unknown')
                }
            }

            self.sio.emit('new_alert', processed_alert)

            return True
        except Exception as e:
            logger.error(f"Error al enviar resultado de decisión: {e}")
            return False

    def broadcast_action_queue_status(self, status_data):
        """Enviar estado del Action Queue Manager a todos los clientes suscritos"""
        try:
            logger.info(f"📡 Enviando estado del Action Queue: {status_data.get('status', 'desconocido')}")

            # Enviar evento personalizado con el estado del Action Queue
            self.sio.emit('action_queue_status', status_data)

            # También enviar como alerta de estado
            status_alert = {
                "id": f"action_queue_status_{status_data.get('timestamp', '')}",
                "timestamp": status_data.get('timestamp', ''),
                "source": "action_queue_manager",
                "type": "action_queue_status",
                "severity": "info",
                "title": f"Estado del Action Queue: {status_data.get('status', 'desconocido')}",
                "description": status_data.get('message', ''),
                "metadata": {
                    "component": status_data.get('component', 'action_queue_manager'),
                    "version": status_data.get('version', '1.0.0'),
                    "queue_size": status_data.get('queue_size', 0),
                    "timestamp": status_data.get('timestamp', '')
                }
            }

            self.sio.emit('new_alert', status_alert)

            return True
        except Exception as e:
            logger.error(f"Error al enviar estado del Action Queue: {e}")
            return False

    def broadcast_action_executed(self, action_id):
        """Enviar notificación de acción ejecutada"""
        try:
            logger.info(f"📢 Enviando notificación de acción ejecutada: {action_id}")

            # Enviar evento personalizado
            self.sio.emit('action_executed', action_id)

            # También enviar como alerta
            action_alert = {
                "id": f"action_executed_{action_id}",
                "timestamp": datetime.now().isoformat(),
                "source": "action_queue_manager",
                "type": "action_executed",
                "severity": "success",
                "title": f"Acción ejecutada: {action_id}",
                "description": "La acción ha sido ejecutada con éxito",
                "metadata": {
                    "action_id": action_id,
                    "status": "executed",
                    "timestamp": datetime.now().isoformat()
                }
            }

            self.sio.emit('new_alert', action_alert)

            return True
        except Exception as e:
            logger.error(f"Error al enviar notificación de acción ejecutada: {e}")
            return False

    def log_action_requested(self, action_data):
        """Registrar solicitud de acción en logs"""
        try:
            log_message = f"📋 Solicitud de acción recibida: {action_data.get('action_id', 'desconocido')} - {action_data.get('action_type', 'desconocido')}"
            logger.info(log_message)

            # En un entorno real, esto guardaría en un archivo de logs
            return True
        except Exception as e:
            logger.error(f"Error al registrar solicitud de acción: {e}")
            return False

    def log_action_denied(self, action_data):
        """Registrar acción denegada en logs"""
        try:
            log_message = f"❌ Acción denegada: {action_data.get('action_id', 'desconocido')} - {action_data.get('action_type', 'desconocido')}"
            logger.warning(log_message)

            # En un entorno real, esto guardaría en un archivo de logs
            return True
        except Exception as e:
            logger.error(f"Error al registrar acción denegada: {e}")
            return False

def main():
    """Función principal para iniciar la integración"""
    logger.info("🚀 Iniciando integración del Action Queue Manager con el sistema principal")
    logger.info("=" * 60)

    # Inicializar integración
    integration = ActionQueueIntegration()

    # Conectar al servidor principal
    if integration.connect():
        logger.info("✅ Integración conectada al servidor principal")

        try:
            # Mantener la integración en ejecución
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("🛑 Integración detenida por el usuario")
        finally:
            integration.disconnect()
            logger.info("🔌 Integración desconectada del servidor principal")
    else:
        logger.error("❌ No se pudo conectar la integración al servidor principal")
        return False

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)