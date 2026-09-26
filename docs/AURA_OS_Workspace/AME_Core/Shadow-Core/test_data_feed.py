"""
test_data_feed.py - Script de prueba para verificar la funcionalidad del servidor de datos en tiempo real
Este script simula un cliente que se conecta al servidor de datos y verifica su funcionamiento
"""

import os
import sys
import time
import json
import logging
from datetime import datetime
import requests
from threading import Thread
import socketio

# Configuración del logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración del servidor
SERVER_URL = "http://localhost:5002"
SOCKETIO_URL = "http://localhost:5002"
TEST_INTERVAL = 10  # segundos entre pruebas
MAX_TESTS = 5  # número máximo de pruebas

# Configuración de pruebas
TEST_CONFIG = {
    "test_connection": True,
    "test_alert_simulation": True,
    "test_socket_connection": True,
    "test_api_endpoints": True,
    "test_alert_reception": True
}

# Variables globales
socketio_client = None
connected = False
test_results = {
    "connection": False,
    "api_status": False,
    "alert_simulation": False,
    "socket_connection": False,
    "alert_reception": False,
    "errors": []
}

def test_http_connection():
    """Prueba la conexión HTTP al servidor"""
    try:
        logger.info("Pruebas de conexión HTTP...")
        response = requests.get(f"{SERVER_URL}/api/status", timeout=5)
        if response.status_code == 200:
            test_results["connection"] = True
            logger.info("✅ Conexión HTTP exitosa")
            logger.info(f"   - Estado del servidor: {response.json().get('status', 'desconocido')}")
            logger.info(f"   - Clientes activos: {response.json().get('active_clients', 0)}")
            return True
        else:
            test_results["errors"].append(f"Conexión HTTP fallida (código: {response.status_code})")
            logger.error(f"❌ Conexión HTTP fallida (código: {response.status_code})")
            return False
    except Exception as e:
        test_results["errors"].append(f"Error en conexión HTTP: {str(e)}")
        logger.error(f"❌ Error en conexión HTTP: {str(e)}")
        return False

def test_api_endpoints():
    """Prueba los endpoints API del servidor"""
    try:
        logger.info("Pruebas de endpoints API...")

        # Probar endpoint /api/status
        response = requests.get(f"{SERVER_URL}/api/status", timeout=5)
        if response.status_code != 200:
            test_results["errors"].append(f"Endpoint /api/status falló (código: {response.status_code})")
            return False

        # Probar endpoint /api/simulate
        response = requests.post(f"{SERVER_URL}/api/simulate", timeout=5)
        if response.status_code != 200:
            test_results["errors"].append(f"Endpoint /api/simulate falló (código: {response.status_code})")
            return False

        # Probar endpoint /api/control
        response = requests.post(
            f"{SERVER_URL}/api/control",
            json={"action": "test"},
            timeout=5
        )
        if response.status_code != 200:
            test_results["errors"].append(f"Endpoint /api/control falló (código: {response.status_code})")
            return False

        test_results["api_status"] = True
        logger.info("✅ Todos los endpoints API funcionan correctamente")
        return True
    except Exception as e:
        test_results["errors"].append(f"Error en pruebas de API: {str(e)}")
        logger.error(f"❌ Error en pruebas de API: {str(e)}")
        return False

def test_alert_simulation():
    """Prueba la simulación de alertas"""
    try:
        logger.info("Pruebas de simulación de alertas...")

        # Simular una alerta
        response = requests.post(f"{SERVER_URL}/api/simulate", timeout=5)
        if response.status_code == 200:
            alert_data = response.json()
            if "alert" in alert_data and "id" in alert_data["alert"]:
                test_results["alert_simulation"] = True
                logger.info("✅ Simulación de alerta exitosa")
                logger.info(f"   - ID de alerta: {alert_data['alert']['id']}")
                logger.info(f"   - Fuente: {alert_data['alert']['source']}")
                logger.info(f"   - Tipo: {alert_data['alert']['type']}")
                logger.info(f"   - Severidad: {alert_data['alert']['severity']}")
                return True
            else:
                test_results["errors"].append("Simulación de alerta fallida: no se recibió alerta válida")
                logger.error("❌ Simulación de alerta fallida: no se recibió alerta válida")
                return False
        else:
            test_results["errors"].append(f"Simulación de alerta fallida (código: {response.status_code})")
            logger.error(f"❌ Simulación de alerta fallida (código: {response.status_code})")
            return False
    except Exception as e:
        test_results["errors"].append(f"Error en simulación de alerta: {str(e)}")
        logger.error(f"❌ Error en simulación de alerta: {str(e)}")
        return False

def setup_socketio_events():
    """Configura los eventos de Socket.IO"""
    global socketio_client, connected

    @socketio_client.on('connect')
    def on_connect():
        global connected
        connected = True
        logger.info("✅ Conexión Socket.IO establecida")
        test_results["socket_connection"] = True

    @socketio_client.on('disconnect')
    def on_disconnect():
        global connected
        connected = False
        logger.warning("⚠️ Desconectado del servidor Socket.IO")

    @socketio_client.on('new_alert')
    def on_new_alert(data):
        logger.info("🚨 Nueva alerta recibida:")
        logger.info(f"   - ID: {data.get('id', 'desconocido')}")
        logger.info(f"   - Fuente: {data.get('source', 'desconocida')}")
        logger.info(f"   - Tipo: {data.get('type', 'desconocido')}")
        logger.info(f"   - Severidad: {data.get('severity', 'desconocida')}")
        logger.info(f"   - Título: {data.get('title', 'sin título')}")

        # Marcar como exitosa la recepción de alertas
        test_results["alert_reception"] = True

    @socketio_client.on('system_message')
    def on_system_message(data):
        logger.info(f"📢 Mensaje del sistema: {data.get('message', 'desconocido')}")

    @socketio_client.on('error')
    def on_error(data):
        logger.error(f"❌ Error del servidor: {data.get('message', 'desconocido')}")
        test_results["errors"].append(f"Error del servidor: {data.get('message', 'desconocido')}")

def test_socket_connection():
    """Prueba la conexión Socket.IO"""
    global socketio_client, connected

    try:
        logger.info("Pruebas de conexión Socket.IO...")

        # Crear cliente Socket.IO
        socketio_client = socketio.Client(logger=True, engineio_logger=True)
        setup_socketio_events()

        # Conectar al servidor
        socketio_client.connect(SOCKETIO_URL, transports=['websocket'])

        # Esperar a que se establezca la conexión
        time.sleep(2)

        if connected:
            # Suscribirse a la sala global
            socketio_client.emit('subscribe', {'room': 'global'})
            logger.info("✅ Suscripción a sala global exitosa")

            # Esperar a recibir una alerta (simulada por el servidor)
            time.sleep(3)

            return True
        else:
            test_results["errors"].append("Conexión Socket.IO no se estableció")
            logger.error("❌ Conexión Socket.IO no se estableció")
            return False

    except Exception as e:
        test_results["errors"].append(f"Error en conexión Socket.IO: {str(e)}")
        logger.error(f"❌ Error en conexión Socket.IO: {str(e)}")
        return False
    finally:
        # Desconectar
        if socketio_client:
            socketio_client.disconnect()
            socketio_client = None

def run_tests():
    """Ejecuta todas las pruebas"""
    logger.info("🧪 INICIANDO PRUEBAS DEL SERVIDOR DE DATOS EN TIEMPO REAL")
    logger.info("=" * 60)

    # Ejecutar pruebas
    if TEST_CONFIG["test_connection"]:
        test_http_connection()

    if TEST_CONFIG["test_api_endpoints"]:
        test_api_endpoints()

    if TEST_CONFIG["test_alert_simulation"]:
        test_alert_simulation()

    if TEST_CONFIG["test_socket_connection"]:
        test_socket_connection()

    if TEST_CONFIG["test_alert_reception"]:
        # Esto se probará durante la conexión Socket.IO
        pass

    # Mostrar resultados
    logger.info("\n" + "=" * 60)
    logger.info("📊 RESULTADOS DE LAS PRUEBAS")
    logger.info("=" * 60)

    success_count = 0
    for test_name, result in test_results.items():
        if test_name != "errors" and result:
            success_count += 1
            logger.info(f"✅ {test_name.replace('_', ' ').title()}: OK")
        elif test_name != "errors" and not result:
            logger.info(f"❌ {test_name.replace('_', ' ').title()}: FALLÓ")

    if test_results["errors"]:
        logger.info("\n⚠️ ERRORES ENCONTRADOS:")
        for error in test_results["errors"]:
            logger.info(f"   - {error}")

    logger.info("\n" + "=" * 60)
    if success_count > 0:
        logger.info(f"🎉 PRUEBAS COMPLETADAS: {success_count} de {len(test_results) - 1} pruebas exitosas")
    else:
        logger.info("❌ TODAS LAS PRUEBAS FALLARON")

    if test_results["errors"]:
        logger.info("\n🔧 RECOMENDACIONES:")
        logger.info("   - Verifique que el servidor de datos esté en ejecución")
        logger.info("   - Asegúrese de que no haya conflictos de puertos")
        logger.info("   - Revise los logs del servidor para errores")
        logger.info("   - Instale las dependencias requeridas (flask-socketio, eventlet)")
    else:
        logger.info("\n✅ TODO FUNCIONA CORRECTAMENTE")

    return success_count > 0

def main():
    """Función principal"""
    logger.info("Prueba del servidor de datos en tiempo real de Shadow-Core")
    logger.info("Este script verifica la funcionalidad del sistema de alertas")

    # Verificar si el servidor está en ejecución
    try:
        response = requests.get(f"{SERVER_URL}/api/status", timeout=2)
        if response.status_code == 200:
            logger.info("✅ Servidor de datos en tiempo real está en ejecución")
        else:
            logger.warning("⚠️ El servidor de datos en tiempo real no está respondiendo")
            logger.info("   Iniciando servidor de prueba en segundo plano...")
            # Intentar iniciar el servidor en segundo plano
            import subprocess
            try:
                subprocess.Popen([sys.executable, "start_data_feed.py"], cwd="Shadow-Core")
                logger.info("   Servidor iniciado en segundo plano")
                time.sleep(5)  # Esperar a que el servidor inicie
            except Exception as e:
                logger.error(f"❌ Error al intentar iniciar servidor: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Error al verificar servidor: {str(e)}")

    # Ejecutar pruebas
    success = run_tests()

    # Salir con código de error si falló
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()