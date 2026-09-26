"""
integrate_decision_core.py - Integración del Decision Core con el sistema de datos (versión corregida)
Este script integra el Decision Core con el servidor de datos en tiempo real
y configura la comunicación bidireccional.
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

class DecisionCoreIntegration:
    def __init__(self):
        self.server_url = "http://localhost:5002"
        self.socket_url = "http://localhost:5002"
        self.decision_core_url = "http://localhost:5003"  # Puerto para Decision Core
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
            self.sio.emit('subscribe', {'room': 'decision_engine'})

        @self.sio.on('disconnect')
        def on_disconnect():
            nonlocal connected
            connected = False
            logger.warning("⚠️ Desconectado del servidor WebSocket principal")

        @self.sio.on('new_alert')
        def on_new_alert(alert_data):
            """Redirigir alertas al Decision Core"""
            logger.info(f"🚨 Alerta recibida: {alert_data.get('id', 'desconocido')}")
            self.forward_to_decision_core(alert_data)

        @self.sio.on('agent_status')
        def on_agent_status(status_data):
            """Recibir estado del Decision Core"""
            logger.info(f"📡 Estado del Decision Core: {status_data.get('status', 'desconocido')}")
            self.broadcast_agent_status(status_data)

        @self.sio.on('decision_result')
        def on_decision_result(result_data):
            """Recibir resultados de decisiones del Decision Core"""
            logger.info(f"🤖 Resultado de decisión: {result_data.get('alert_id', 'desconocido')}")
            self.broadcast_decision_result(result_data)

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

    def forward_to_decision_core(self, alert_data):
        """Redirigir alertas al Decision Core"""
        try:
            logger.info(f"🔄 Redirigiendo alerta al Decision Core: {alert_data.get('id', 'desconocido')}")

            # En un entorno real, esto enviaría la alerta al Decision Core
            # Por ahora, solo registramos la acción y simulamos el procesamiento

            # Simular procesamiento por parte del Decision Core
            time.sleep(1)  # Simular tiempo de procesamiento

            # Crear resultado simulado
            result_data = {
                "alert_id": alert_data.get('id', 'unknown'),
                "alert_type": alert_data.get('type', 'unknown'),
                "severity": alert_data.get('severity', 'unknown'),
                "timestamp": alert_data.get('timestamp', ''),
                "actions_taken": 2,
                "status": "success",
                "details": f"Alerta procesada por Decision Core: {alert_data.get('title', 'Sin título')}",
                "decision_time": alert_data.get('timestamp', '')
            }

            # Enviar resultado al servidor principal
            self.broadcast_decision_result(result_data)

            return True
        except Exception as e:
            logger.error(f"Error al redirigir alerta al Decision Core: {e}")
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

    def broadcast_agent_status(self, status_data):
        """Enviar estado del Decision Core a todos los clientes suscritos"""
        try:
            logger.info(f"📡 Enviando estado del Decision Core: {status_data.get('status', 'desconocido')}")

            # Enviar evento personalizado con el estado del agente
            self.sio.emit('agent_status', status_data)

            # También enviar como alerta de estado
            status_alert = {
                "id": f"status_{status_data.get('timestamp', '')}",
                "timestamp": status_data.get('timestamp', ''),
                "source": "decision_engine",
                "type": "agent_status",
                "severity": "info",
                "title": f"Estado del Decision Core: {status_data.get('status', 'desconocido')}",
                "description": status_data.get('message', ''),
                "metadata": {
                    "component": status_data.get('component', 'decision_core'),
                    "version": status_data.get('version', '1.0.0'),
                    "timestamp": status_data.get('timestamp', '')
                }
            }

            self.sio.emit('new_alert', status_alert)

            return True
        except Exception as e:
            logger.error(f"Error al enviar estado del Decision Core: {e}")
            return False

def main():
    """Función principal para iniciar la integración"""
    logger.info("🚀 Iniciando integración del Decision Core con el sistema principal")
    logger.info("=" * 60)

    # Inicializar integración
    integration = DecisionCoreIntegration()

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