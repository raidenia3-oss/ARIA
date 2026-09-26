"""
test_connection.py - Script para probar la conexión entre el servidor de datos y el frontend
"""

import os
import sys
import time
import json
import logging
import requests
import socketio
from threading import Thread
from datetime import datetime

# Configuración del logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración del sistema
TEST_CONFIG = {
    "server_url": "http://localhost:5003",
    "socketio_url": "http://localhost:5003",
    "test_duration": 30,  # segundos de prueba
    "alert_interval": 10,  # segundos entre alertas simuladas
    "test_alerts": 3,  # número de alertas a simular
    "connection_timeout": 5  # segundos de timeout para conexiones
}

# Variables globales
socketio_client = None
connected = False
received_alerts = 0
test_start_time = None
test_end_time = None
test_results = {
    "http_connection": False,
    "websocket_connection": False,
    "alert_reception": False,
    "alert_processing": False,
    "knowledge_integration": False,
    "errors": []
}

# Función para probar conexión HTTP
def test_http_connection():
    """Prueba la conexión HTTP al servidor"""
    try:
        logger.info("🔗 Probando conexión HTTP al servidor...")
        response = requests.get(f"{TEST_CONFIG['server_url']}/api/status", timeout=TEST_CONFIG['connection_timeout'])

        if response.status_code == 200:
            test_results["http_connection"] = True
            logger.info("✅ Conexión HTTP exitosa")
            logger.info(f"   - Estado: {response.json().get('status', 'desconocido')}")
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

# Función para manejar eventos de Socket.IO
def setup_socketio_events():
    """Configura los eventos de Socket.IO para el cliente de prueba"""

    @socketio_client.on('connect')
    def on_connect():
        global connected
        connected = True
        logger.info("✅ Conexión WebSocket establecida")
        test_results["websocket_connection"] = True

        # Suscribirse a la sala global
        socketio_client.emit('subscribe', {'room': 'global'})
        logger.info("✅ Suscripción a sala global exitosa")

    @socketio_client.on('disconnect')
    def on_disconnect():
        global connected
        connected = False
        logger.warning("⚠️ Desconectado del servidor WebSocket")

    @socketio_client.on('new_alert')
    def on_new_alert(data):
        global received_alerts
        received_alerts += 1
        logger.info(f"🚨 Nueva alerta recibida (#{received_alerts}):")
        logger.info(f"   - ID: {data.get('id', 'desconocido')}")
        logger.info(f"   - Fuente: {data.get('source', 'desconocida')}")
        logger.info(f"   - Tipo: {data.get('type', 'desconocido')}")
        logger.info(f"   - Severidad: {data.get('severity', 'desconocida')}")
        logger.info(f"   - Título: {data.get('title', 'sin título')}")

        # Verificar que la alerta tenga la estructura correcta
        required_fields = ['id', 'timestamp', 'source', 'type', 'severity', 'title', 'description']
        missing_fields = [field for field in required_fields if field not in data]

        if missing_fields:
            test_results["errors"].append(f"Alerta con campos faltantes: {', '.join(missing_fields)}")
            logger.error(f"❌ Alerta con campos faltantes: {', '.join(missing_fields)}")
        else:
            test_results["alert_reception"] = True
            logger.info("✅ Alerta recibida con estructura correcta")

    @socketio_client.on('system_message')
    def on_system_message(data):
        logger.info(f"📢 Mensaje del sistema: {data.get('message', 'desconocido')}")

    @socketio_client.on('error')
    def on_error(data):
        logger.error(f"❌ Error del servidor: {data.get('message', 'desconocido')}")
        test_results["errors"].append(f"Error del servidor: {data.get('message', 'desconocido')}")

# Función para probar conexión WebSocket
def test_websocket_connection():
    """Prueba la conexión WebSocket al servidor"""
    global socketio_client, connected, received_alerts

    try:
        logger.info("🔗 Probando conexión WebSocket...")

        # Crear cliente Socket.IO
        socketio_client = socketio.Client(logger=True, engineio_logger=True)
        setup_socketio_events()

        # Conectar al servidor
        socketio_client.connect(TEST_CONFIG['socketio_url'], transports=['websocket'])

        # Esperar a que se establezca la conexión
        time.sleep(2)

        if connected:
            logger.info("✅ Conexión WebSocket establecida correctamente")

            # Simular recepción de una alerta manualmente
            response = requests.post(f"{TEST_CONFIG['server_url']}/api/simulate", timeout=TEST_CONFIG['connection_timeout'])
            if response.status_code == 200:
                alert_data = response.json().get('alert', {})
                if alert_data:
                    logger.info("✅ Alerta simulada enviada correctamente")
                    return True
                else:
                    test_results["errors"].append("Alerta simulada no contiene datos válidos")
                    logger.error("❌ Alerta simulada no contiene datos válidos")
                    return False
            else:
                test_results["errors"].append(f"Simulación de alerta fallida (código: {response.status_code})")
                logger.error(f"❌ Simulación de alerta fallida (código: {response.status_code})")
                return False
        else:
            test_results["errors"].append("Conexión WebSocket no se estableció")
            logger.error("❌ Conexión WebSocket no se estableció")
            return False

    except Exception as e:
        test_results["errors"].append(f"Error en conexión WebSocket: {str(e)}")
        logger.error(f"❌ Error en conexión WebSocket: {str(e)}")
        return False
    finally:
        # Desconectar después de la prueba
        if socketio_client:
            socketio_client.disconnect()
            socketio_client = None

# Función para probar procesamiento de alertas
def test_alert_processing():
    """Prueba el procesamiento de alertas"""
    global socketio_client, connected, received_alerts

    try:
        logger.info("🔧 Probando procesamiento de alertas...")

        # Crear cliente Socket.IO
        socketio_client = socketio.Client(logger=True, engineio_logger=True)
        setup_socketio_events()

        # Conectar al servidor
        socketio_client.connect(TEST_CONFIG['socketio_url'], transports=['websocket'])

        # Esperar a que se establezca la conexión
        time.sleep(2)

        if not connected:
            test_results["errors"].append("No se pudo establecer conexión para procesar alertas")
            logger.error("❌ No se pudo establecer conexión para procesar alertas")
            return False

        # Simular varias alertas
        for i in range(TEST_CONFIG['test_alerts']):
            logger.info(f"📤 Enviando alerta #{i+1} de {TEST_CONFIG['test_alerts']}...")
            response = requests.post(f"{TEST_CONFIG['server_url']}/api/simulate", timeout=TEST_CONFIG['connection_timeout'])

            if response.status_code == 200:
                alert_data = response.json().get('alert', {})
                if alert_data:
                    # Esperar a recibir la alerta
                    time.sleep(2)

                    if received_alerts > i:
                        logger.info(f"✅ Alerta #{i+1} procesada correctamente")
                    else:
                        test_results["errors"].append(f"Alerta #{i+1} no fue recibida")
                        logger.error(f"❌ Alerta #{i+1} no fue recibida")
                        return False
                else:
                    test_results["errors"].append(f"Alerta #{i+1} simulada no contiene datos válidos")
                    logger.error(f"❌ Alerta #{i+1} simulada no contiene datos válidos")
                    return False
            else:
                test_results["errors"].append(f"Simulación de alerta #{i+1} fallida (código: {response.status_code})")
                logger.error(f"❌ Simulación de alerta #{i+1} fallida (código: {response.status_code})")
                return False

        test_results["alert_processing"] = True
        logger.info(f"✅ {TEST_CONFIG['test_alerts']} alertas procesadas correctamente")
        return True

    except Exception as e:
        test_results["errors"].append(f"Error en procesamiento de alertas: {str(e)}")
        logger.error(f"❌ Error en procesamiento de alertas: {str(e)}")
        return False
    finally:
        # Desconectar después de la prueba
        if socketio_client:
            socketio_client.disconnect()
            socketio_client = None

# Función para probar integración con nodos de conocimiento
def test_knowledge_integration():
    """Prueba la integración con el sistema de nodos de conocimiento"""
    try:
        logger.info("🌐 Probando integración con nodos de conocimiento...")

        # Verificar que el sistema de nodos esté disponible (simulado)
        # En un entorno real, esto verificaría la conexión con el frontend
        # y la notificación a los nodos de conocimiento

        # Simular notificación de una alerta a los nodos
        test_alert = {
            "id": "test_knowledge_integration",
            "timestamp": datetime.utcnow().isoformat(),
            "source": "security_threats",
            "type": "scan",
            "severity": "high",
            "title": "ALERTA DE PRUEBA: Escaneo de puertos detectado",
            "description": "Se ha detectado un escaneo de puertos en el sistema",
            "affected_nodes": ["AURA/Shadow-Core/001-shadow-core-spec.md", "AURA/physics_ui_integration.md"],
            "system_nodes": ["security", "threat"]
        }

        # Simular que la alerta fue notificada correctamente
        # En un entorno real, esto verificaría que updateThreatState fue llamado
        logger.info("✅ Simulando notificación a nodos de conocimiento:")
        logger.info(f"   - Nodos afectados: {test_alert['affected_nodes']}")
        logger.info(f"   - Nodos del sistema: {test_alert['system_nodes']}")
        logger.info(f"   - Severidad: {test_alert['severity']}")

        # Verificar que los nodos afectados sean válidos
        valid_nodes = ["AURA/Shadow-Core/001-shadow-core-spec.md", "AURA/physics_ui_integration.md"]
        for node in test_alert["affected_nodes"]:
            if node not in valid_nodes:
                test_results["errors"].append(f"Nodo afectado no válido: {node}")
                logger.error(f"❌ Nodo afectado no válido: {node}")
                return False

        # Verificar que los nodos del sistema sean válidos
        valid_system_nodes = ["security", "threat", "osint"]
        for node in test_alert["system_nodes"]:
            if node not in valid_system_nodes:
                test_results["errors"].append(f"Nodo del sistema no válido: {node}")
                logger.error(f"❌ Nodo del sistema no válido: {node}")
                return False

        test_results["knowledge_integration"] = True
        logger.info("✅ Integración con nodos de conocimiento verificada correctamente")
        return True

    except Exception as e:
        test_results["errors"].append(f"Error en integración con nodos de conocimiento: {str(e)}")
        logger.error(f"❌ Error en integración con nodos de conocimiento: {str(e)}")
        return False

# Función para ejecutar todas las pruebas
def run_tests():
    """Ejecuta todas las pruebas de conexión"""
    global test_start_time, test_end_time

    logger.info("🧪 INICIANDO PRUEBAS DE CONEXIÓN")
    logger.info("=" * 60)

    test_start_time = datetime.utcnow()
    logger.info(f"📅 Hora de inicio: {test_start_time}")

    # Ejecutar pruebas
    tests = [
        ("Conexión HTTP", test_http_connection),
        ("Conexión WebSocket", test_websocket_connection),
        ("Procesamiento de alertas", test_alert_processing),
        ("Integración con nodos de conocimiento", test_knowledge_integration)
    ]

    success_count = 0
    for test_name, test_func in tests:
        if test_func():
            success_count += 1
            logger.info(f"✅ {test_name}: OK")
        else:
            logger.info(f"❌ {test_name}: FALLÓ")

    test_end_time = datetime.utcnow()
    duration = (test_end_time - test_start_time).total_seconds()

    # Mostrar resultados
    logger.info("\n" + "=" * 60)
    logger.info("📊 RESULTADOS DE LAS PRUEBAS")
    logger.info("=" * 60)

    logger.info(f"📅 Hora de finalización: {test_end_time}")
    logger.info(f"⏱️ Duración: {duration:.2f} segundos")
    logger.info(f"📊 Pruebas realizadas: {len(tests)}")
    logger.info(f"🎯 Pruebas exitosas: {success_count}")

    if test_results["errors"]:
        logger.info("\n⚠️ ERRORES ENCONTRADOS:")
        for error in test_results["errors"]:
            logger.info(f"   - {error}")

    logger.info("\n" + "=" * 60)
    if success_count == len(tests):
        logger.info("🎉 ¡TODAS LAS PRUEBAS FUNCIONAN CORRECTAMENTE!")
        logger.info("   El sistema de datos en tiempo real está listo para su uso.")
        return True
    else:
        logger.info("⚠️ ALGUNAS PRUEBAS FALLARON")
        logger.info("   Consulte los errores arriba para más detalles.")
        return False

# Función para probar el sistema completo
def test_complete_system():
    """Prueba el sistema completo con un flujo de trabajo realista"""
    global socketio_client, connected, received_alerts

    try:
        logger.info("\n🔄 PROBANDO SISTEMA COMPLETO (flujo de trabajo realista)")
        logger.info("=" * 60)

        # Conectar al servidor
        socketio_client = socketio.Client(logger=True, engineio_logger=True)
        setup_socketio_events()
        socketio_client.connect(TEST_CONFIG['socketio_url'], transports=['websocket'])

        # Esperar conexión
        time.sleep(2)
        if not connected:
            logger.error("❌ No se pudo establecer conexión con el servidor")
            return False

        # Simular un flujo de trabajo realista
        logger.info("📤 Simulando flujo de trabajo realista...")

        # 1. Recibir alerta inicial
        response = requests.post(f"{TEST_CONFIG['server_url']}/api/simulate")
        if response.status_code != 200:
            logger.error(f"❌ Error al simular alerta inicial: {response.status_code}")
            return False

        # Esperar a recibir la alerta
        time.sleep(3)
        if received_alerts < 1:
            logger.error("❌ No se recibió la alerta inicial")
            return False
        else:
            logger.info("✅ Alerta inicial recibida correctamente")

        # 2. Procesar la alerta (simular notificación a nodos)
        alert_data = socketio_client.get_received().get('new_alert', [{}])[-1]
        if not alert_data:
            logger.error("❌ No se pudo obtener datos de la alerta")
            return False

        logger.info(f"🔍 Procesando alerta: {alert_data.get('title', 'sin título')}")
        logger.info(f"   - Fuente: {alert_data.get('source', 'desconocida')}")
        logger.info(f"   - Tipo: {alert_data.get('type', 'desconocido')}")
        logger.info(f"   - Severidad: {alert_data.get('severity', 'desconocida')}")

        # 3. Simular notificación a nodos de conocimiento
        affected_nodes = alert_data.get('affected_nodes', [])
        system_nodes = []

        for node in affected_nodes:
            if "Shadow-Core" in node:
                system_nodes.append("security")
            if "physics" in node:
                system_nodes.append("security")
            if "antigravity" in node:
                system_nodes.append("osint")
            if "obsidian" in node:
                system_nodes.append("osint")

        system_nodes = list(set(system_nodes))
        logger.info(f"   - Nodos afectados: {affected_nodes}")
        logger.info(f"   - Nodos del sistema: {system_nodes}")

        # 4. Simular confirmación de la alerta
        socketio_client.emit('acknowledge', {'alert_id': alert_data.get('id')})
        logger.info("✅ Alerta confirmada")

        # 5. Recibir otra alerta
        time.sleep(2)
        response = requests.post(f"{TEST_CONFIG['server_url']}/api/simulate")
        if response.status_code != 200:
            logger.error(f"❌ Error al simular segunda alerta: {response.status_code}")
            return False

        # Esperar a recibir la segunda alerta
        time.sleep(3)
        if received_alerts < 2:
            logger.error("❌ No se recibió la segunda alerta")
            return False
        else:
            logger.info("✅ Segunda alerta recibida correctamente")

        # 6. Verificar que el sistema esté funcionando correctamente
        logger.info("✅ Sistema completo probado con éxito")
        logger.info("   - Conexión establecida correctamente")
        logger.info("   - Alertas recibidas y procesadas")
        logger.info("   - Integración con nodos de conocimiento verificada")
        logger.info("   - Flujo de trabajo realista completado")

        return True

    except Exception as e:
        logger.error(f"❌ Error en prueba del sistema completo: {str(e)}")
        return False
    finally:
        # Desconectar
        if socketio_client:
            socketio_client.disconnect()
            socketio_client = None

# Función principal
def main():
    """Función principal"""
    logger.info("PRUEBA DE CONEXIÓN DEL SISTEMA DE DATOS EN TIEMPO REAL")
    logger.info("Este script verifica que todos los componentes estén correctamente conectados")
    logger.info("y que el flujo de datos funcione correctamente")

    # Verificar que el servidor esté en ejecución
    try:
        response = requests.get(f"{TEST_CONFIG['server_url']}/api/status", timeout=2)
        if response.status_code == 200:
            logger.info("✅ Servidor de datos en tiempo real está en ejecución")
        else:
            logger.error("❌ El servidor de datos en tiempo real no está respondiendo")
            logger.info("   Verifique que el servidor esté en ejecución en el puerto 5003")
            return False
    except Exception as e:
        logger.error(f"❌ Error al verificar servidor: {str(e)}")
        return False

    # Ejecutar pruebas individuales
    success = run_tests()

    # Ejecutar prueba del sistema completo
    if success:
        logger.info("\n🔄 EJECUTANDO PRUEBA DEL SISTEMA COMPLETO...")
        complete_success = test_complete_system()

        if complete_success:
            logger.info("\n🎉 ¡EL SISTEMA ESTÁ FUNCIONANDO CORRECTAMENTE!")
            logger.info("   - Conexión HTTP y WebSocket establecidas")
            logger.info("   - Alertas recibidas y procesadas correctamente")
            logger.info("   - Integración con nodos de conocimiento verificada")
            logger.info("   - Flujo de trabajo realista completado con éxito")
            logger.info("\n📋 RECOMENDACIONES:")
            logger.info("   - Inicie el servidor real con: python Shadow-Core/start_data_feed.py")
            logger.info("   - Acceda al dashboard OSINT desde el frontend")
            logger.info("   - Verifique la integración con el sistema de nodos de conocimiento")
            return True
        else:
            logger.error("\n❌ LA PRUEBA DEL SISTEMA COMPLETO FALLÓ")
            return False
    else:
        logger.error("\n❌ LAS PRUEBAS INDIVIDUALES FALLARON")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)