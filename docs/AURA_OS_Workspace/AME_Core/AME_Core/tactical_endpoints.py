"""
Endpoints para el dashboard táctico.
Proporciona datos dinámicos para los nuevos paneles.
"""

from flask import jsonify
import time
import random

def register_tactical_endpoints(app):
    """
    Registra los endpoints para el dashboard táctico.
    """
    @app.route('/api/tactical/world_state')
    def api_tactical_world_state():
        """
        Endpoint para obtener el estado del mundo táctico.
        Devuelve datos simulados para el radar de amenazas y otros paneles.
        """
        try:
            # Simular datos del mundo táctico
            world_state = {
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S'),
                "threat_score": random.randint(10, 90),
                "threat_level": "CRÍTICO" if random.random() > 0.7 else "ALTO" if random.random() > 0.4 else "MEDIO" if random.random() > 0.2 else "BAJO",
                "active_alerts": random.randint(0, 10),
                "critical_alerts": random.randint(0, 3),
                "connection_status": "online" if random.random() > 0.2 else "offline",
                "latency": random.randint(10, 100),
                "tunnel_status": "active" if random.random() > 0.3 else "inactive",
                "resources": {
                    "cpu": random.randint(10, 80),
                    "ram": random.randint(20, 70),
                    "bandwidth": random.randint(15, 60)
                }
            }

            return jsonify({
                "status": "ok",
                "world_state": world_state
            })
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

    @app.route('/api/tactical/resources')
    def api_tactical_resources():
        """
        Endpoint para obtener el estado de los recursos del sistema.
        """
        try:
            # Simular datos de recursos
            resources = {
                "cpu": {
                    "usage": random.randint(10, 80),
                    "cores": random.randint(2, 16)
                },
                "ram": {
                    "total_gb": random.randint(4, 32),
                    "used_gb": random.randint(1, 16),
                    "free_gb": random.randint(1, 16)
                },
                "bandwidth": {
                    "upload_mbps": random.randint(1, 100),
                    "download_mbps": random.randint(1, 100),
                    "latency": random.randint(10, 100)
                }
            }

            return jsonify({
                "status": "ok",
                "resources": resources
            })
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

    @app.route('/api/tactical/network')
    def api_tactical_network():
        """
        Endpoint para obtener el estado de la red.
        """
        try:
            # Simular datos de red
            network = {
                "connection": {
                    "status": "online" if random.random() > 0.2 else "offline",
                    "ip": "192.168.1.100" if random.random() > 0.5 else "10.0.0.5",
                    "gateway": "192.168.1.1"
                },
                "tunnel": {
                    "status": "active" if random.random() > 0.3 else "inactive",
                    "url": "https://aura-tunnel.ngrok.io" if random.random() > 0.5 else "Desconectado",
                    "expires_in": "1h" if random.random() > 0.5 else "Desconectado"
                },
                "latency": random.randint(10, 100),
                "packets": {
                    "sent": random.randint(100, 1000),
                    "received": random.randint(100, 1000),
                    "lost": random.randint(0, 5)
                }
            }

            return jsonify({
                "status": "ok",
                "network": network
            })
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

    @app.route('/api/tactical/console')
    def api_tactical_console():
        """
        Endpoint para obtener logs de la consola táctica.
        """
        try:
            # Simular logs de la consola
            logs = [
                {"type": "info", "message": "📡 AURA Tactical Console iniciada"},
                {"type": "info", "message": "🔍 Escaneando entorno..."},
                {"type": "info", "message": "🌐 Conexión establecida con el núcleo"},
                {"type": "warning", "message": "⚠️ 3 alertas pendientes en el ticker"},
                {"type": "info", "message": "📊 Radar de amenazas actualizado"},
                {"type": "info", "message": "🖥️ Recursos del sistema estables"},
                {"type": "info", "message": "🌐 Conexión de red establecida"}
            ]

            return jsonify({
                "status": "ok",
                "logs": logs
            })
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500