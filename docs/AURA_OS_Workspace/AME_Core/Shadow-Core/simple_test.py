"""
simple_test.py - Script simple para probar la conexión con el servidor de datos
"""

import os
import sys
import time
import json
import logging
import requests
import socketio
from datetime import datetime

# Configuración del logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración del sistema
SERVER_URL = "http://localhost:5003"
SOCKETIO_URL = "http://localhost:5003"
TEST_TIMEOUT = 10  # segundos de timeout para pruebas

def test_http_connection():
    """Prueba la conexión HTTP al servidor"""
    try:
        logger.info("🔗 Probando conexión HTTP...")
        response = requests.get(f"{SERVER_URL}/api/status", timeout=TEST_TIMEOUT)

        if response.status_code == 200:
            logger.info("✅ Conexión HTTP exitosa")
            logger.info(f"   - Estado: {response.json().get('status', 'desconocido')}")
            logger.info(f"   - Clientes activos: {response.json().get('active_clients', 0)}")
            return True
        else:
            logger.error(f"❌ Conexión HTTP fallida (código: {response.status_code})")
            return False
    except Exception as e:
        logger.error(f"❌ Error en conexión HTTP: {str(e)}")
        return False

def test_websocket_connection():
    """Prueba la conexión WebSocket al servidor"""
    try:
        logger.info("🔗 Probando conexión WebSocket...")

        # Crear cliente Socket.IO
        sio = socketio.Client(logger=True, engineio_logger=True)

        @sio.on('connect')
        def on_connect():
            nonlocal connected
            connected = True
            logger.info("✅ Conexión WebSocket establecida")
            sio.emit('subscribe', {'room': 'global'})
            logger.info("✅ Suscripción a sala global exitosa")

        @sio.on('disconnect')
        def on_disconnect():
            nonlocal connected
            connected = False
            logger.warning("⚠️ Desconectado del servidor WebSocket")

        @sio.on('new_alert')
        def on_new_alert(data):
            nonlocal received_alerts
            received_alerts += 1
            logger.info(f"🚨 Nueva alerta recibida (#{received_alerts}):")
            logger.info(f"   - ID: {data.get('id', 'desconocido')}")
            logger.info(f"   - Fuente: {data.get('source', 'desconocida')}")
            logger.info(f"   - Tipo: {data.get('type', 'desconocido')}")
            logger.info(f"   - Severidad: {data.get('severity', 'desconocida')}")

        connected = False
        received_alerts = 0

        # Conectar al servidor
        sio.connect(SOCKETIO_URL, transports=['websocket'])

        # Esperar a que se establezca la conexión
        time.sleep(2)

        if connected:
            logger.info("✅ Conexión WebSocket establecida correctamente")

            # Simular recepción de una alerta manualmente
            response = requests.post(f"{SERVER_URL}/api/simulate", timeout=TEST_TIMEOUT)
            if response.status_code == 200:
                alert_data = response.json().get('alert', {})
                if alert_data:
                    logger.info("✅ Alerta simulada enviada correctamente")
                    return True
                else:
                    logger.error("❌ Alerta simulada no contiene datos válidos")
                    return False
            else:
                logger.error(f"❌ Simulación de alerta fallida (código: {response.status_code})")
                return False
        else:
            logger.error("❌ Conexión WebSocket no se estableció")
            return False

    except Exception as e:
        logger.error(f"❌ Error en conexión WebSocket: {str(e)}")
        return False
    finally:
        # Desconectar
        if 'sio' in locals():
            sio.disconnect()

def test_alert_processing():
    """Prueba el procesamiento de alertas"""
    try:
        logger.info("🔧 Probando procesamiento de alertas...")

        # Crear cliente Socket.IO
        sio = socketio.Client(logger=True, engineio_logger=True)

        @sio.on('connect')
        def on_connect():
            nonlocal connected
            connected = True
            logger.info("✅ Conexión WebSocket establecida")
            sio.emit('subscribe', {'room': 'global'})

        @sio.on('new_alert')
        def on_new_alert(data):
            nonlocal received_alerts
            received_alerts += 1
            logger.info(f"🚨 Nueva alerta recibida (#{received_alerts}): {data.get('title', 'sin título')}")

        connected = False
        received_alerts = 0

        # Conectar al servidor
        sio.connect(SOCKETIO_URL, transports=['websocket'])

        # Esperar a que se establezca la conexión
        time.sleep(2)

        if not connected:
            logger.error("❌ No se pudo establecer conexión para procesar alertas")
            return False

        # Simular varias alertas
        for i in range(3):
            logger.info(f"📤 Enviando alerta #{i+1}...")
            response = requests.post(f"{SERVER_URL}/api/simulate", timeout=TEST_TIMEOUT)

            if response.status_code == 200:
                alert_data = response.json().get('alert', {})
                if alert_data:
                    # Esperar a recibir la alerta
                    time.sleep(2)

                    if received_alerts > i:
                        logger.info(f"✅ Alerta #{i+1} procesada correctamente")
                    else:
                        logger.error(f"❌ Alerta #{i+1} no fue recibida")
                        return False
                else:
                    logger.error(f"❌ Alerta #{i+1} simulada no contiene datos válidos")
                    return False
            else:
                logger.error(f"❌ Simulación de alerta #{i+1} fallida (código: {response.status_code})")
                return False

        logger.info(f"✅ {received_alerts} alertas procesadas correctamente")
        return True

    except Exception as e:
        logger.error(f"❌ Error en procesamiento de alertas: {str(e)}")
        return False
    finally:
        # Desconectar
        if 'sio' in locals():
            sio.disconnect()

def test_integration():
    """Prueba la integración completa del sistema"""
    try:
        logger.info("🌐 Probando integración completa del sistema...")

        # 1. Probar conexión HTTP
        if not test_http_connection():
            return False

        # 2. Probar conexión WebSocket
        if not test_websocket_connection():
            return False

        # 3. Probar procesamiento de alertas
        if not test_alert_processing():
            return False

        logger.info("✅ Todas las pruebas de integración completadas con éxito")
        return True

    except Exception as e:
        logger.error(f"❌ Error en prueba de integración: {str(e)}")
        return False

def main():
    """Función principal"""
    logger.info("PRUEBA SIMPLE DE CONEXIÓN CON EL SERVIDOR DE DATOS")
    logger.info("Este script verifica que el servidor esté funcionando correctamente")

    # Verificar que el servidor esté en ejecución
    try:
        response = requests.get(f"{SERVER_URL}/api/status", timeout=2)
        if response.status_code == 200:
            logger.info("✅ Servidor de datos en tiempo real está en ejecución")
        else:
            logger.error("❌ El servidor de datos en tiempo real no está respondiendo")
            logger.info("   Verifique que el servidor esté en ejecución en el puerto 5003")
            return False
    except Exception as e:
        logger.error(f"❌ Error al verificar servidor: {str(e)}")
        return False

    # Ejecutar pruebas de integración
    success = test_integration()

    if success:
        logger.info("\n🎉 ¡EL SISTEMA ESTÁ FUNCIONANDO CORRECTAMENTE!")
        logger.info("   - Conexión HTTP establecida")
        logger.info("   - Conexión WebSocket establecida")
        logger.info("   - Alertas recibidas y procesadas correctamente")
        logger.info("\n📋 RECOMENDACIONES:")
        logger.info("   - Inicie el servidor real con: python Shadow-Core/start_data_feed.py")
        logger.info("   - Acceda al dashboard OSINT desde el frontend")
        logger.info("   - Verifique la integración con el sistema de nodos de conocimiento")
        return True
    else:
        logger.error("\n❌ ALGUNAS PRUEBAS FALLARON")
        logger.info("   Verifique que el servidor esté en ejecución y que no haya errores de red")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)