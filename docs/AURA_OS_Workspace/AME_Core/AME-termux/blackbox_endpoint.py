"""
Endpoint para la Caja Negra (BlackBox) de AURA.
Proporciona logs tácticos del sistema en tiempo real.
"""

from flask import jsonify
import time
import os
import json
from AME_Core.tactical_log_manager import tactical_log_manager

def register_blackbox_endpoint(app):
    """
    Registra el endpoint /api/tactical/logs en la aplicación Flask.
    """
    @app.route('/api/tactical/logs')
    def api_tactical_logs():
        """
        Endpoint para obtener logs tácticos del sistema.
        Devuelve logs categorizados en sistema, emergencia, servidor, OSINT y seguridad.
        """
        try:
            # Obtener logs tácticos
            logs = tactical_log_manager.get_logs()

            # Añadir logs del servidor principal
            log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
            if os.path.exists(log_dir):
                for log_file in os.listdir(log_dir):
                    if log_file.endswith('.log'):
                        log_path = os.path.join(log_dir, log_file)
                        try:
                            with open(log_path, 'r', encoding='utf-8') as f:
                                lines = f.readlines()
                                for line in lines[-50:]:  # Últimas 50 líneas
                                    if line.strip():
                                        tactical_log_manager.add_log('server', line.strip(), 'info')
                        except Exception as e:
                            print(f"⚠️ Error leyendo logs del servidor: {e}")

            # Añadir logs de salud del sistema
            health_log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'AURA_Core', 'system_health.log')
            if os.path.exists(health_log_path):
                try:
                    with open(health_log_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        for line in lines[-20:]:  # Últimas 20 líneas
                            if line.strip() and not line.startswith('#'):
                                tactical_log_manager.add_log('system', line.strip(), 'info')
                except Exception as e:
                    print(f"⚠️ Error leyendo logs de salud: {e}")

            # Añadir logs de alertas del sistema
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

            return jsonify({
                "status": "ok",
                "message": "Logs tácticos obtenidos",
                "logs": logs
            })
        except Exception as e:
            print(f"❌ Error obteniendo logs tácticos: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500