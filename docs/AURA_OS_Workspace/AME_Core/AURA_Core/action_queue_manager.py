"""
action_queue_manager.py - Gestor de cola de acciones pendientes para AURA
Este módulo maneja las acciones que requieren aprobación antes de ejecutarse.
"""

import os
import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import socketio
from dotenv import load_dotenv

# Configuración del logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

class ActionQueueConfig:
    def __init__(self):
        self.log_file = "action_queue.log"
        self.max_actions = 10
        self.default_timeout = 300  # 5 minutos en segundos
        self.socket_url = "http://localhost:5002"

class ActionQueueManager:
    def __init__(self):
        self.config = ActionQueueConfig()
        self.action_queue = []
        self.setup_logging()
        self.sio = socketio.Client(logger=True, engineio_logger=True)
        self.connected = False
        self.setup_socket_events()

    def setup_logging(self):
        """Configurar sistema de logging"""
        self.log_file_path = Path(self.config.log_file)
        if not self.log_file_path.exists():
            with open(self.log_file_path, 'w', encoding='utf-8') as f:
                f.write("# Log de cola de acciones de AURA\n")
                f.write(f"# Iniciado: {datetime.utcnow().isoformat()}\n")
                f.write("# ============================================\n\n")

    def log_action(self, action_data: Dict, status: str):
        """Registrar una acción en el log"""
        try:
            timestamp = datetime.utcnow().isoformat()
            log_entry = {
                "timestamp": timestamp,
                "action": action_data,
                "status": status
            }

            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] ACCIÓN: {action_data.get('action_type', 'desconocido')} - {status}\n")
                f.write(f"  ID: {action_data.get('action_id', 'desconocido')}\n")
                f.write(f"  Detalles: {action_data.get('details', 'N/A')}\n")
                f.write(f"  Estado: {status}\n")
                f.write(f"  Tiempo: {action_data.get('timeout', 0)} segundos\n")
                f.write("  ============================================\n\n")

            logger.info(f"Acción registrada: {action_data.get('action_id', 'desconocido')} - {status}")
            return True
        except Exception as e:
            logger.error(f"Error al registrar acción: {e}")
            return False

    def setup_socket_events(self):
        """Configurar eventos para Socket.IO"""
        connected = False

        @self.sio.on('connect')
        def on_connect():
            nonlocal connected
            connected = True
            logger.info("🔗 Conexión WebSocket establecida con Action Queue Manager")
            self.report_status("connected")

        @self.sio.on('disconnect')
        def on_disconnect():
            nonlocal connected
            connected = False
            logger.warning("⚠️ Desconectado del servidor WebSocket")
            self.report_status("disconnected")

        @self.sio.on('action_approval_request')
        def on_action_approval_request(action_data):
            """Recibir solicitud de aprobación de acción"""
            logger.info(f"📋 Solicitud de aprobación recibida: {action_data.get('action_id', 'desconocido')}")
            self.add_to_queue(action_data)

        @self.sio.on('action_approved')
        def on_action_approved(action_id):
            """Recibir notificación de acción aprobada"""
            logger.info(f"✅ Acción aprobada: {action_id}")
            self.process_approved_action(action_id)

        @self.sio.on('action_denied')
        def on_action_denied(action_id):
            """Recibir notificación de acción denegada"""
            logger.info(f"❌ Acción denegada: {action_id}")
            self.process_denied_action(action_id)

    def connect(self):
        """Conectarse al servidor"""
        try:
            logger.info("🔌 Conectando Action Queue Manager al servidor...")
            self.sio.connect(self.config.socket_url, transports=['websocket'])
            return True
        except Exception as e:
            logger.error(f"Error al conectar Action Queue Manager: {e}")
            return False

    def disconnect(self):
        """Desconectarse del servidor"""
        try:
            if self.connected:
                self.sio.disconnect()
                logger.info("🔌 Action Queue Manager desconectado del servidor")
            return True
        except Exception as e:
            logger.error(f"Error al desconectar Action Queue Manager: {e}")
            return False

    def report_status(self, status: str, message: str = ""):
        """Reportar estado al dashboard"""
        try:
            status_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "status": status,
                "message": message,
                "component": "action_queue_manager",
                "version": "1.0.0",
                "queue_size": len(self.action_queue)
            }

            if self.connected:
                self.sio.emit('action_queue_status', status_data)
            else:
                logger.warning("No se pudo reportar estado: No conectado a WebSocket")

            # También guardar en log local
            self.log_action({
                "action_id": "status_report",
                "action_type": "system_status",
                "details": message,
                "timeout": 0
            }, status)

            return True
        except Exception as e:
            logger.error(f"Error al reportar estado: {e}")
            return False

    def add_to_queue(self, action_data: Dict) -> bool:
        """Agregar una acción a la cola de pendientes"""
        try:
            # Verificar si la acción ya existe en la cola
            for action in self.action_queue:
                if action.get('action_id') == action_data.get('action_id'):
                    logger.warning(f"Acción ya existe en la cola: {action_data.get('action_id')}")
                    return False

            # Agregar la acción a la cola
            action_data['status'] = 'pending'
            action_data['timestamp'] = datetime.utcnow().isoformat()
            action_data['timeout_at'] = (datetime.utcnow() + timedelta(seconds=action_data.get('timeout', self.config.default_timeout))).isoformat()

            self.action_queue.insert(0, action_data)
            self.log_action(action_data, 'added_to_queue')

            # Reportar estado actualizado
            self.report_status("new_action_in_queue", f"Acción agregada a la cola: {action_data.get('action_id', 'desconocido')}")

            # Notificar al frontend que hay una nueva acción pendiente
            if self.connected:
                self.sio.emit('new_action_pending', action_data)

            logger.info(f"✅ Acción agregada a la cola: {action_data.get('action_id', 'desconocido')}")
            return True

        except Exception as e:
            logger.error(f"Error al agregar acción a la cola: {e}")
            return False

    def process_approved_action(self, action_id: str) -> bool:
        """Procesar una acción aprobada"""
        try:
            for i, action in enumerate(self.action_queue):
                if action.get('action_id') == action_id:
                    # Marcar como ejecutada
                    action['status'] = 'executed'
                    action['execution_time'] = datetime.utcnow().isoformat()

                    # Notificar al Decision Core que ejecute la acción
                    if self.connected:
                        self.sio.emit('execute_approved_action', action)

                    # Registrar en log
                    self.log_action(action, 'executed')

                    # Reportar estado
                    self.report_status("action_executed", f"Acción ejecutada: {action_id}")

                    # Eliminar de la cola
                    del self.action_queue[i]

                    logger.info(f"✅ Acción ejecutada: {action_id}")
                    return True

            logger.warning(f"Acción no encontrada en la cola: {action_id}")
            return False

        except Exception as e:
            logger.error(f"Error al procesar acción aprobada: {e}")
            return False

    def process_denied_action(self, action_id: str) -> bool:
        """Procesar una acción denegada"""
        try:
            for i, action in enumerate(self.action_queue):
                if action.get('action_id') == action_id:
                    # Marcar como denegada
                    action['status'] = 'denied'
                    action['denial_time'] = datetime.utcnow().isoformat()

                    # Registrar en log
                    self.log_action(action, 'denied')

                    # Reportar estado
                    self.report_status("action_denied", f"Acción denegada: {action_id}")

                    # Eliminar de la cola
                    del self.action_queue[i]

                    logger.info(f"❌ Acción denegada: {action_id}")
                    return True

            logger.warning(f"Acción no encontrada en la cola: {action_id}")
            return False

        except Exception as e:
            logger.error(f"Error al procesar acción denegada: {e}")
            return False

    def check_timeout_actions(self):
        """Verificar acciones que hayan excedido su tiempo de espera"""
        try:
            current_time = datetime.utcnow()
            expired_actions = []

            for i, action in enumerate(self.action_queue):
                timeout_at = datetime.fromisoformat(action.get('timeout_at', current_time.isoformat()))
                if current_time > timeout_at and action.get('status') == 'pending':
                    expired_actions.append((i, action))

            for i, action in expired_actions:
                # Marcar como expirada
                action['status'] = 'expired'
                action['expired_time'] = datetime.utcnow().isoformat()

                # Registrar en log
                self.log_action(action, 'expired')

                # Reportar estado
                self.report_status("action_expired", f"Acción expirada: {action.get('action_id', 'desconocido')}")

                # Eliminar de la cola
                del self.action_queue[i]

                logger.warning(f"⏰ Acción expirada: {action.get('action_id', 'desconocido')}")

            return len(expired_actions) > 0

        except Exception as e:
            logger.error(f"Error al verificar acciones expiradas: {e}")
            return False

    def get_queue_status(self) -> Dict:
        """Obtener estado actual de la cola de acciones"""
        return {
            "status": "operational" if self.connected else "disconnected",
            "timestamp": datetime.utcnow().isoformat(),
            "connected": self.connected,
            "queue_size": len(self.action_queue),
            "pending_actions": len([a for a in self.action_queue if a.get('status') == 'pending']),
            "executed_actions": len([a for a in self.action_queue if a.get('status') == 'executed']),
            "denied_actions": len([a for a in self.action_queue if a.get('status') == 'denied']),
            "expired_actions": len([a for a in self.action_queue if a.get('status') == 'expired']),
            "log_file": str(self.log_file_path),
            "version": "1.0.0"
        }

    def get_action_queue(self) -> List[Dict]:
        """Obtener la cola completa de acciones"""
        return self.action_queue.copy()

    def main_loop(self):
        """Bucle principal para procesar la cola de acciones"""
        try:
            logger.info("🔄 Iniciando bucle principal de Action Queue Manager")

            while True:
                # Verificar acciones expiradas cada 10 segundos
                self.check_timeout_actions()

                # Reportar estado cada 30 segundos
                self.report_status("queue_updated", f"Cola actualizada. Acciones pendientes: {len(self.action_queue)}")

                time.sleep(10)

        except KeyboardInterrupt:
            logger.info("🛑 Action Queue Manager detenido por el usuario")
        except Exception as e:
            logger.error(f"Error en bucle principal: {e}")
        finally:
            self.disconnect()
            logger.info("🔌 Action Queue Manager desconectado")

from datetime import timedelta

def main():
    """Función principal para iniciar el Action Queue Manager"""
    logger.info("🚀 Iniciando Action Queue Manager para AURA")
    logger.info("📋 Configuración cargada desde action_queue_manager.py")

    # Inicializar Action Queue Manager
    action_queue_manager = ActionQueueManager()

    # Conectar al servidor
    if action_queue_manager.connect():
        logger.info("✅ Action Queue Manager conectado y listo para procesar acciones")

        # Reportar estado inicial
        action_queue_manager.report_status("initialized", "Action Queue Manager listo para operar")

        # Iniciar bucle principal
        action_queue_manager.main_loop()
    else:
        logger.error("❌ No se pudo conectar Action Queue Manager al servidor")
        return False

    return True

if __name__ == "__main__":
    main()