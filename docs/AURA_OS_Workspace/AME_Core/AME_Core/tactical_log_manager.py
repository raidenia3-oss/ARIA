"""
Módulo para gestionar logs tácticos de la Caja Negra.
Incluye un sistema de logs centralizado para el dashboard.
"""

import time
import os
import json
import logging

class TacticalLogManager:
    def __init__(self):
        self.logs = {
            'system': {'entries': []},
            'emergency': {'entries': []},
            'server': {'entries': []},
            'osint': {'entries': []},
            'security': {'entries': []}
        }
        self.max_entries = 500  # Máximo de entradas por tipo de log

    def add_log(self, log_type, message, level='info'):
        """
        Añade un log táctico al sistema.
        :param log_type: Tipo de log (system, emergency, server, osint, security)
        :param message: Mensaje del log
        :param level: Nivel del log (info, warning, error, critical)
        """
        if log_type not in self.logs:
            return

        # Formatear el mensaje con nivel y timestamp
        timestamp = time.strftime('%Y-%m-%dT%H:%M:%S')
        formatted_message = f"[{timestamp}] [{level.upper()}] {message}"

        # Añadir al tipo de log correspondiente
        self.logs[log_type]['entries'].append(formatted_message)

        # Limitar el número de entradas
        if len(self.logs[log_type]['entries']) > self.max_entries:
            self.logs[log_type]['entries'] = self.logs[log_type]['entries'][-self.max_entries:]

    def get_logs(self, log_type=None):
        """
        Obtiene los logs tácticos.
        :param log_type: Tipo de log específico (None para todos)
        :return: Diccionario con los logs
        """
        if log_type:
            return {log_type: self.logs[log_type]} if log_type in self.logs else {}
        return self.logs

    def clear_logs(self, log_type=None):
        """
        Limpia los logs tácticos.
        :param log_type: Tipo de log específico (None para todos)
        """
        if log_type and log_type in self.logs:
            self.logs[log_type]['entries'] = []
        else:
            for key in self.logs:
                self.logs[key]['entries'] = []

# Instancia global del sistema de logs tácticos
tactical_log_manager = TacticalLogManager()

# Handler para integrar logs tácticos con el sistema de logging de Flask
class TacticalLogHandler(logging.Handler):
    def __init__(self, tactical_log_manager):
        super().__init__()
        self.tactical_log_manager = tactical_log_manager

    def emit(self, record):
        try:
            level = record.levelname.lower()
            message = self.format(record)

            # Determinar el tipo de log según el nivel
            if level == 'error':
                self.tactical_log_manager.add_log('emergency', message, 'error')
            elif level == 'warning':
                self.tactical_log_manager.add_log('security', message, 'warning')
            else:
                self.tactical_log_manager.add_log('server', message, 'info')
        except Exception as e:
            print(f"⚠️ Error en TacticalLogHandler: {e}")

# Función para cargar logs desde archivos
def load_logs_from_files():
    """
    Carga logs desde archivos del sistema y los añade al TacticalLogManager.
    """
    log_files = {
        'system': os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'AURA_Core', 'system_health.log'),
        'server': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'ame_server.log')
    }

    for log_type, log_path in log_files.items():
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    for line in lines[-50:]:  # Últimas 50 líneas
                        if line.strip() and not line.startswith('#'):
                            tactical_log_manager.add_log(log_type, line.strip(), 'info')
            except Exception as e:
                print(f"⚠️ Error leyendo logs desde {log_path}: {e}")

# Función para cargar alertas desde el sistema
def load_alerts_from_system():
    """
    Carga alertas del sistema desde alerts_buffer.json y las añade al TacticalLogManager.
    """
    alerts_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'alerts_buffer.json')
    if os.path.exists(alerts_path):
        try:
            with open(alerts_path, 'r', encoding='utf-8') as f:
                alerts = json.load(f)
                for alert in alerts[-10:]:  # Últimas 10 alertas
                    message = f"{alert.get('message', '')} (Fuente: {alert.get('source', 'desconocida')})"
                    tactical_log_manager.add_log('security', message, 'warning' if 'warning' in alert.get('type', '').lower() else 'critical')
        except Exception as e:
            print(f"⚠️ Error leyendo alertas del sistema: {e}")

# Inicializar el sistema de logs tácticos
def init_tactical_logs():
    """
    Inicializa el sistema de logs tácticos y carga logs desde archivos.
    """
    load_logs_from_files()
    load_alerts_from_system()
    return tactical_log_manager