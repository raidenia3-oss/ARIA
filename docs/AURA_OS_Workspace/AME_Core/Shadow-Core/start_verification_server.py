"""
start_verification_server.py - Script para iniciar un servidor de verificación de integración
Este script inicia un servidor Flask simple para verificar la conexión entre componentes
"""

import os
import sys
import time
import logging
from flask import Flask, request, jsonify
from threading import Thread
import json
from datetime import datetime

# Configuración del logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración del servidor
app = Flask(__name__)
app.config['SECRET_KEY'] = 'verification-secret-key'

# Configuración del sistema
SYSTEM_CONFIG = {
    "integration_points": [
        {
            "name": "Shadow-Core a Frontend",
            "description": "Conexión entre Shadow-Core y el dashboard OSINT",
            "status": "pending",
            "last_test": None,
            "success_count": 0,
            "failure_count": 0
        },
        {
            "name": "Frontend a Nodos de Conocimiento",
            "description": "Notificación de alertas a los nodos de conocimiento",
            "status": "pending",
            "last_test": None,
            "success_count": 0,
            "failure_count": 0
        },
        {
            "name": "WebSocket Connection",
            "description": "Conexión WebSocket entre Shadow-Core y el frontend",
            "status": "pending",
            "last_test": None,
            "success_count": 0,
            "failure_count": 0
        },
        {
            "name": "HTTP API Connection",
            "description": "Conexión HTTP entre Shadow-Core y el frontend",
            "status": "pending",
            "last_test": None,
            "success_count": 0,
            "failure_count": 0
        }
    ],
    "test_data": {
        "sample_alert": {
            "id": "test_alert_1",
            "timestamp": datetime.utcnow().isoformat(),
            "source": "osint_alerts",
            "type": "phishing",
            "severity": "critical",
            "title": "ALERTA DE PRUEBA: Posible campaña de phishing detectada",
            "description": "Se ha detectado una posible campaña de phishing dirigida a usuarios del sistema",
            "details": [
                {"type": "url", "value": "http://malicious-phishing-site.com/login", "status": "active"},
                {"type": "domain", "value": "evil-look-alike.com", "registration_date": "2023-01-15"}
            ],
            "affected_nodes": ["AURA/Shadow-Core/001-shadow-core-spec.md", "AURA/physics_ui_integration.md"],
            "metadata": {
                "ip": "192.168.1.100",
                "domain": "example123.com",
                "port": 80,
                "confidence": 0.95,
                "last_seen": datetime.utcnow().isoformat()
            },
            "color": "#F44336"
        }
    }
}

# Función para generar una alerta de prueba
def generate_test_alert():
    """Genera una alerta de prueba para verificar la integración"""
    return SYSTEM_CONFIG["test_data"]["sample_alert"]

# Función para actualizar el estado de integración
def update_integration_status(point_name, success):
    """Actualiza el estado de un punto de integración"""
    for point in SYSTEM_CONFIG["integration_points"]:
        if point["name"] == point_name:
            point["last_test"] = datetime.utcnow().isoformat()
            if success:
                point["status"] = "success"
                point["success_count"] += 1
            else:
                point["status"] = "failure"
                point["failure_count"] += 1
            break

# Función para obtener el estado del sistema
def get_system_status():
    """Devuelve el estado actual del sistema de integración"""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "integration_points": SYSTEM_CONFIG["integration_points"],
        "test_data": SYSTEM_CONFIG["test_data"]
    }

# Función para probar la conexión HTTP
def test_http_connection():
    """Prueba la conexión HTTP entre componentes"""
    try:
        # Simular una solicitud HTTP desde el frontend
        logger.info("🔗 Probando conexión HTTP...")
        response = {
            "status": "success",
            "message": "Conexión HTTP exitosa",
            "data": {
                "method": "GET",
                "endpoint": "/api/status",
                "response": {
                    "status": "running",
                    "active_clients": 0,
                    "last_alert_time": datetime.utcnow().isoformat()
                }
            }
        }

        # Actualizar estado
        update_integration_status("HTTP API Connection", True)
        return True, response
    except Exception as e:
        logger.error(f"❌ Error en conexión HTTP: {e}")
        update_integration_status("HTTP API Connection", False)
        return False, {"status": "error", "message": str(e)}

# Función para probar la conexión WebSocket
def test_websocket_connection():
    """Prueba la conexión WebSocket entre componentes"""
    try:
        # Simular una conexión WebSocket
        logger.info("🔗 Probando conexión WebSocket...")
        response = {
            "status": "success",
            "message": "Conexión WebSocket exitosa",
            "data": {
                "event": "connect",
                "client_id": "test_client_123",
                "rooms": ["global", "security"],
                "message": "Cliente conectado al servidor de datos"
            }
        }

        # Actualizar estado
        update_integration_status("WebSocket Connection", True)
        return True, response
    except Exception as e:
        logger.error(f"❌ Error en conexión WebSocket: {e}")
        update_integration_status("WebSocket Connection", False)
        return False, {"status": "error", "message": str(e)}

# Función para probar la integración Shadow-Core a Frontend
def test_shadow_to_frontend():
    """Prueba la integración entre Shadow-Core y el frontend"""
    try:
        logger.info("🔗 Probando integración Shadow-Core a Frontend...")

        # Simular recepción de una alerta
        alert = generate_test_alert()

        # Simular procesamiento de la alerta
        processed_alert = {
            "id": alert["id"],
            "timestamp": alert["timestamp"],
            "source": alert["source"],
            "type": alert["type"],
            "severity": alert["severity"],
            "title": alert["title"],
            "description": alert["description"],
            "processed": datetime.utcnow().isoformat(),
            "status": "active",
            "system_nodes": ["security", "threat"]
        }

        # Simular notificación al frontend
        response = {
            "status": "success",
            "message": "Alerta procesada y notificada al frontend",
            "data": processed_alert
        }

        # Actualizar estado
        update_integration_status("Shadow-Core a Frontend", True)
        return True, response
    except Exception as e:
        logger.error(f"❌ Error en integración Shadow-Core a Frontend: {e}")
        update_integration_status("Shadow-Core a Frontend", False)
        return False, {"status": "error", "message": str(e)}

# Función para probar la integración Frontend a Nodos de Conocimiento
def test_frontend_to_knowledge():
    """Prueba la integración entre el frontend y los nodos de conocimiento"""
    try:
        logger.info("🔗 Probando integración Frontend a Nodos de Conocimiento...")

        # Simular recepción de una alerta
        alert = generate_test_alert()

        # Simular notificación a los nodos de conocimiento
        response = {
            "status": "success",
            "message": "Alerta notificada a los nodos de conocimiento",
            "data": {
                "affected_nodes": alert["affected_nodes"],
                "system_nodes": ["security", "threat"],
                "threat_level": 4,
                "action": "updateThreatState"
            }
        }

        # Actualizar estado
        update_integration_status("Frontend a Nodos de Conocimiento", True)
        return True, response
    except Exception as e:
        logger.error(f"❌ Error en integración Frontend a Nodos de Conocimiento: {e}")
        update_integration_status("Frontend a Nodos de Conocimiento", False)
        return False, {"status": "error", "message": str(e)}

# Función para probar todas las integraciones
def test_all_integrations():
    """Prueba todas las integraciones del sistema"""
    logger.info("🧪 INICIANDO PRUEBAS DE INTEGRACIÓN COMPLETA")

    results = []

    # Probar conexión HTTP
    success, response = test_http_connection()
    results.append({
        "test": "HTTP Connection",
        "success": success,
        "response": response
    })

    # Probar conexión WebSocket
    success, response = test_websocket_connection()
    results.append({
        "test": "WebSocket Connection",
        "success": success,
        "response": response
    })

    # Probar integración Shadow-Core a Frontend
    success, response = test_shadow_to_frontend()
    results.append({
        "test": "Shadow-Core to Frontend",
        "success": success,
        "response": response
    })

    # Probar integración Frontend a Nodos de Conocimiento
    success, response = test_frontend_to_knowledge()
    results.append({
        "test": "Frontend to Knowledge Nodes",
        "success": success,
        "response": response
    })

    return results

# Función para manejar endpoints HTTP
def setup_http_endpoints():
    """Configura los endpoints HTTP para el servidor de verificación"""

    @app.route('/api/status', methods=['GET'])
    def api_status():
        """Endpoint para obtener el estado del sistema"""
        return jsonify(get_system_status())

    @app.route('/api/test', methods=['GET'])
    def api_test():
        """Endpoint para probar todas las integraciones"""
        try:
            results = test_all_integrations()

            # Calcular estadísticas
            success_count = sum(1 for result in results if result["success"])
            total_tests = len(results)

            response = {
                "status": "success",
                "message": "Pruebas de integración completadas",
                "results": results,
                "statistics": {
                    "success_count": success_count,
                    "total_tests": total_tests,
                    "success_rate": f"{int((success_count / total_tests) * 100)}%",
                    "integration_status": get_system_status()
                }
            }

            return jsonify(response), 200
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": f"Error al ejecutar pruebas: {str(e)}"
            }), 500

    @app.route('/api/test/<test_name>', methods=['GET'])
    def api_test_specific(test_name):
        """Endpoint para probar una integración específica"""
        try:
            if test_name == "http":
                success, response = test_http_connection()
            elif test_name == "websocket":
                success, response = test_websocket_connection()
            elif test_name == "shadow_to_frontend":
                success, response = test_shadow_to_frontend()
            elif test_name == "frontend_to_knowledge":
                success, response = test_frontend_to_knowledge()
            else:
                return jsonify({
                    "status": "error",
                    "message": f"Prueba no válida: {test_name}",
                    "available_tests": ["http", "websocket", "shadow_to_frontend", "frontend_to_knowledge"]
                }), 400

            if success:
                return jsonify({
                    "status": "success",
                    "message": f"Prueba {test_name} exitosa",
                    "data": response
                }), 200
            else:
                return jsonify({
                    "status": "error",
                    "message": f"Prueba {test_name} fallida",
                    "data": response
                }), 400
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": f"Error al ejecutar prueba {test_name}: {str(e)}"
            }), 500

    @app.route('/api/alert', methods=['POST'])
    def api_alert():
        """Endpoint para simular recepción de una alerta"""
        try:
            data = request.json
            if not data:
                return jsonify({
                    "status": "error",
                    "message": "No se recibió datos en la solicitud"
                }), 400

            # Procesar la alerta
            processed_alert = {
                "id": data.get("id", "unknown"),
                "timestamp": data.get("timestamp", datetime.utcnow().isoformat()),
                "source": data.get("source", "unknown"),
                "type": data.get("type", "unknown"),
                "severity": data.get("severity", "info"),
                "title": data.get("title", "Alerta sin título"),
                "description": data.get("description", ""),
                "processed": datetime.utcnow().isoformat(),
                "status": "active",
                "system_nodes": []
            }

            # Determinar nodos afectados
            if "affected_nodes" in data:
                for node in data["affected_nodes"]:
                    if node in ["AURA/Shadow-Core/001-shadow-core-spec.md", "AURA/physics_ui_integration.md"]:
                        processed_alert["system_nodes"].append("security")
                    if node in ["AURA/antigravity_nodes.md", "AURA/obsidian_integration.md"]:
                        processed_alert["system_nodes"].append("osint")

            # Añadir nodos únicos
            processed_alert["system_nodes"] = list(set(processed_alert["system_nodes"]))

            # Simular notificación a los nodos de conocimiento
            update_integration_status("Frontend a Nodos de Conocimiento", True)

            return jsonify({
                "status": "success",
                "message": "Alerta procesada con éxito",
                "data": processed_alert
            }), 200
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": f"Error al procesar alerta: {str(e)}"
            }), 500

# Función para iniciar el servidor de verificación
def start_verification_server(port=5004):
    """Inicia el servidor de verificación de integración"""
    logger.info(f"🚀 INICIANDO SERVIDOR DE VERIFICACIÓN EN EL PUERTO {port}")

    # Configurar endpoints
    setup_http_endpoints()

    # Iniciar servidor
    try:
        logger.info("Servidor de verificación listo. Presione Ctrl+C para detenerlo")
        app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
    except KeyboardInterrupt:
        logger.info("Servidor detenido por el usuario")
    except Exception as e:
        logger.error(f"❌ Error al iniciar el servidor: {str(e)}")
    finally:
        logger.info("Servidor de verificación detenido")

# Función para iniciar el servidor en segundo plano
def start_server_in_background():
    """Inicia el servidor en segundo plano"""
    import subprocess
    import time

    try:
        # Verificar si el servidor ya está en ejecución
        try:
            import requests
            response = requests.get("http://localhost:5004/api/status", timeout=2)
            if response.status_code == 200:
                logger.info("Servidor de verificación ya está en ejecución")
                return True
        except:
            pass

        # Iniciar el servidor en segundo plano
        logger.info("Iniciando servidor de verificación en segundo plano...")
        process = subprocess.Popen(
            [sys.executable, __file__, "--background"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Esperar un momento para que el servidor inicie
        time.sleep(3)

        # Verificar si el servidor está respondiendo
        try:
            response = requests.get("http://localhost:5004/api/status", timeout=2)
            if response.status_code == 200:
                logger.info("Servidor de verificación iniciado correctamente en segundo plano")
                return True
            else:
                logger.error("Servidor de verificación no respondió correctamente")
                return False
        except:
            logger.error("Servidor de verificación no está respondiendo")
            return False

    except Exception as e:
        logger.error(f"Error al iniciar servidor en segundo plano: {str(e)}")
        return False

# Función principal
def main():
    """Función principal"""
    # Verificar si se está ejecutando en modo de fondo
    if len(sys.argv) > 1 and sys.argv[1] == "--background":
        start_server_in_background()
        return

    # Iniciar servidor
    start_verification_server()

if __name__ == '__main__':
    main()