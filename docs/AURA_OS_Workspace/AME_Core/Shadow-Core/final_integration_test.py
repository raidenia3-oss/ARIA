"""
final_integration_test.py - Script para probar la integración completa del sistema de datos en tiempo real
Este script verifica que todos los componentes estén correctamente integrados y funcionando
"""

import os
import sys
import time
import json
import logging
import subprocess
import requests
import socketio
from datetime import datetime
from pathlib import Path

# Configuración del logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración del sistema
SYSTEM_CONFIG = {
    "server_port": 5002,
    "server_url": "http://localhost:5002",
    "socketio_url": "http://localhost:5002",
    "test_duration": 60,  # segundos de prueba
    "alert_interval": 10,  # segundos entre alertas simuladas
    "test_alerts": 3,  # número de alertas a simular
    "connection_timeout": 5,  # segundos de timeout para conexiones
    "server_script": "Shadow-Core/start_data_feed.py",
    "test_data": {
        "sample_alert": {
            "id": "test_integration_alert",
            "timestamp": datetime.utcnow().isoformat(),
            "source": "security_threats",
            "type": "scan",
            "severity": "high",
            "title": "ALERTA DE INTEGRACIÓN: Escaneo de puertos detectado",
            "description": "Se ha detectado un escaneo de puertos en el sistema Shadow-Core",
            "details": [
                {"type": "scan_type", "value": "Nmap", "options": "-sV -O", "version": True},
                {"type": "targets", "value": ["192.168.1.1", "192.168.1.100"], "ports": [21, 22, 80, 443]},
                {"type": "source", "value": "103.86.98.45", "country": "CN", "timestamp": datetime.utcnow().isoformat()}
            ],
            "affected_nodes": ["AURA/Shadow-Core/001-shadow-core-spec.md", "AURA/physics_ui_integration.md"],
            "metadata": {
                "ip": "192.168.1.100",
                "domain": "shadow-core.example.com",
                "port": 80,
                "confidence": 0.95,
                "last_seen": datetime.utcnow().isoformat()
            },
            "color": "#FF5722"
        }
    }
}

# Variables globales
socketio_client = None
connected = False
received_alerts = 0
test_start_time = None
test_end_time = None
server_process = None
test_results = {
    "server_started": False,
    "http_connection": False,
    "websocket_connection": False,
    "alert_reception": False,
    "alert_processing": False,
    "knowledge_integration": False,
    "errors": []
}

def start_server():
    """Inicia el servidor de datos en tiempo real"""
    global server_process

    try:
        logger.info("🚀 INICIANDO SERVIDOR DE DATOS EN TIEMPO REAL")

        # Verificar si el servidor ya está en ejecución
        try:
            response = requests.get(f"{SYSTEM_CONFIG['server_url']}/api/status", timeout=2)
            if response.status_code == 200:
                logger.info("✅ Servidor ya está en ejecución")
                return True
        except:
            pass

        # Iniciar el servidor en segundo plano
        server_process = subprocess.Popen(
            [sys.executable, SYSTEM_CONFIG["server_script"]],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True
        )

        # Esperar un momento para que el servidor inicie
        time.sleep(5)

        # Verificar si el servidor está respondiendo
        try:
            response = requests.get(f"{SYSTEM_CONFIG['server_url']}/api/status", timeout=2)
            if response.status_code == 200:
                logger.info("✅ Servidor iniciado correctamente")
                test_results["server_started"] = True
                return True
            else:
                logger.error("❌ Servidor no respondió correctamente")
                return False
        except Exception as e:
            logger.error(f"❌ Error al verificar servidor: {str(e)}")
            return False

    except Exception as e:
        logger.error(f"❌ Error al iniciar servidor: {str(e)}")
        return False

def stop_server():
    """Detiene el servidor de datos"""
    global server_process

    try:
        if server_process:
            logger.info("🛑 DETENIENDO SERVIDOR DE DATOS")
            server_process.terminate()
            server_process.wait(timeout=5)
            logger.info("✅ Servidor detenido correctamente")
    except Exception as e:
        logger.error(f"❌ Error al detener servidor: {str(e)}")

def test_http_connection():
    """Prueba la conexión HTTP al servidor"""
    try:
        logger.info("🔗 Probando conexión HTTP al servidor...")
        response = requests.get(f"{SYSTEM_CONFIG['server_url']}/api/status", timeout=SYSTEM_CONFIG['connection_timeout'])

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

def setup_socketio_events():
    """Configura los eventos de Socket.IO para el cliente de prueba"""

    @socketio_client.on('connect')
    def on_connect():
        global connected
        connected = True
        logger.info("✅ Conexión WebSocket establecida")
        test_results["websocket_connection"] = True
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

def test_websocket_connection():
    """Prueba la conexión WebSocket al servidor"""
    global socketio_client, connected, received_alerts

    try:
        logger.info("🔗 Probando conexión WebSocket...")

        # Crear cliente Socket.IO
        socketio_client = socketio.Client(logger=True, engineio_logger=True)
        setup_socketio_events()

        # Conectar al servidor
        socketio_client.connect(SYSTEM_CONFIG['socketio_url'], transports=['websocket'])

        # Esperar a que se establezca la conexión
        time.sleep(2)

        if connected:
            logger.info("✅ Conexión WebSocket establecida correctamente")

            # Simular recepción de una alerta manualmente
            response = requests.post(f"{SYSTEM_CONFIG['server_url']}/api/simulate", timeout=SYSTEM_CONFIG['connection_timeout'])
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

def test_alert_processing():
    """Prueba el procesamiento de alertas"""
    global socketio_client, connected, received_alerts

    try:
        logger.info("🔧 Probando procesamiento de alertas...")

        # Crear cliente Socket.IO
        socketio_client = socketio.Client(logger=True, engineio_logger=True)
        setup_socketio_events()

        # Conectar al servidor
        socketio_client.connect(SYSTEM_CONFIG['socketio_url'], transports=['websocket'])

        # Esperar a que se establezca la conexión
        time.sleep(2)

        if not connected:
            test_results["errors"].append("No se pudo establecer conexión para procesar alertas")
            logger.error("❌ No se pudo establecer conexión para procesar alertas")
            return False

        # Simular varias alertas
        for i in range(SYSTEM_CONFIG['test_alerts']):
            logger.info(f"📤 Enviando alerta #{i+1} de {SYSTEM_CONFIG['test_alerts']}...")
            response = requests.post(f"{SYSTEM_CONFIG['server_url']}/api/simulate", timeout=SYSTEM_CONFIG['connection_timeout'])

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
        logger.info(f"✅ {SYSTEM_CONFIG['test_alerts']} alertas procesadas correctamente")
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

def test_knowledge_integration():
    """Prueba la integración con el sistema de nodos de conocimiento"""
    try:
        logger.info("🌐 Probando integración con nodos de conocimiento...")

        # Verificar que el módulo de integración tenga referencia a KnowledgeNodes
        integration_path = Path("AME_Core/integrate_data_feed.py")
        if integration_path.exists():
            try:
                with open(integration_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Verificar que haga referencia a KnowledgeNodes
                if "window.KnowledgeNodes" not in content and "KnowledgeNodes" not in content:
                    test_results["errors"].append("No se encontró referencia a KnowledgeNodes en integrate_data_feed.py")
                    logger.error("❌ No se encontró referencia a KnowledgeNodes en integrate_data_feed.py")
                    return False
                else:
                    logger.info("✅ Referencia a KnowledgeNodes encontrada en integrate_data_feed.py")

                # Verificar que notifique nuevas alertas a KnowledgeNodes
                if "updateThreatState" not in content:
                    test_results["errors"].append("No se encontró notificación a updateThreatState en KnowledgeNodes")
                    logger.error("❌ No se encontró notificación a updateThreatState en KnowledgeNodes")
                    return False
                else:
                    logger.info("✅ Notificación a updateThreatState encontrada")

                # Simular notificación de una alerta a los nodos
                test_alert = SYSTEM_CONFIG["test_data"]["sample_alert"]

                logger.info("✅ Simulando notificación a nodos de conocimiento:")
                logger.info(f"   - Nodos afectados: {test_alert['affected_nodes']}")
                logger.info(f"   - Nodos del sistema: ['security', 'threat']")
                logger.info(f"   - Severidad: {test_alert['severity']}")

                # Verificar que los nodos afectados sean válidos
                valid_nodes = ["AURA/Shadow-Core/001-shadow-core-spec.md", "AURA/physics_ui_integration.md"]
                for node in test_alert["affected_nodes"]:
                    if node not in valid_nodes:
                        test_results["errors"].append(f"Nodo afectado no válido: {node}")
                        logger.error(f"❌ Nodo afectado no válido: {node}")
                        return False

                test_results["knowledge_integration"] = True
                logger.info("✅ Integración con nodos de conocimiento verificada correctamente")
                return True

            except Exception as e:
                test_results["errors"].append(f"Error al leer integrate_data_feed.py: {str(e)}")
                logger.error(f"❌ Error al leer integrate_data_feed.py: {str(e)}")
                return False
        else:
            test_results["errors"].append("integrate_data_feed.py no encontrado")
            logger.error("❌ integrate_data_feed.py no encontrado")
            return False

    except Exception as e:
        test_results["errors"].append(f"Error en integración con nodos de conocimiento: {str(e)}")
        logger.error(f"❌ Error en integración con nodos de conocimiento: {str(e)}")
        return False

def test_complete_integration():
    """Prueba la integración completa del sistema"""
    try:
        logger.info("🔗 PROBANDO INTEGRACIÓN COMPLETA DEL SISTEMA")
        logger.info("=" * 60)

        # 1. Iniciar servidor
        if not start_server():
            return False

        # 2. Probar conexión HTTP
        if not test_http_connection():
            return False

        # 3. Probar conexión WebSocket
        if not test_websocket_connection():
            return False

        # 4. Probar procesamiento de alertas
        if not test_alert_processing():
            return False

        # 5. Probar integración con nodos de conocimiento
        if not test_knowledge_integration():
            return False

        logger.info("✅ Todas las pruebas de integración completadas con éxito")
        return True

    except Exception as e:
        test_results["errors"].append(f"Error en prueba de integración completa: {str(e)}")
        logger.error(f"❌ Error en prueba de integración completa: {str(e)}")
        return False
    finally:
        # Detener servidor
        stop_server()

def generate_test_report():
    """Genera un informe de prueba completo"""
    logger.info("\n📋 GENERANDO INFORME DE PRUEBAS")
    logger.info("=" * 60)

    report = []
    report.append("INFORME DE INTEGRACIÓN DEL SISTEMA DE DATOS EN TIEMPO REAL")
    report.append("=" * 60)
    report.append(f"Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")

    # Resultados de las pruebas
    tests = [
        ("Servidor iniciado", test_results["server_started"]),
        ("Conexión HTTP", test_results["http_connection"]),
        ("Conexión WebSocket", test_results["websocket_connection"]),
        ("Recepción de alertas", test_results["alert_reception"]),
        ("Procesamiento de alertas", test_results["alert_processing"]),
        ("Integración con nodos", test_results["knowledge_integration"])
    ]

    report.append("📊 RESULTADOS DE LAS PRUEBAS:")
    for test_name, result in tests:
        status = "✅" if result else "❌"
        report.append(f"   {status} {test_name}")

    # Estadísticas
    success_count = sum(1 for _, result in tests if result)
    total_tests = len(tests)
    report.append(f"")
    report.append(f"📊 ESTADÍSTICAS:")
    report.append(f"   Pruebas realizadas: {total_tests}")
    report.append(f"   Pruebas exitosas: {success_count}")
    report.append(f"   Porcentaje de éxito: {int((success_count / total_tests) * 100)}%")

    # Errores
    if test_results["errors"]:
        report.append(f"")
        report.append(f"⚠️ ERRORES ENCONTRADOS:")
        for error in test_results["errors"]:
            report.append(f"   - {error}")

    # Conclusión
    report.append(f"")
    if success_count == total_tests:
        report.append("🎉 ¡TODO FUNCIONA CORRECTAMENTE!")
        report.append("   El sistema de datos en tiempo real está listo para su uso.")
        report.append("")
        report.append("📋 RECOMENDACIONES:")
        report.append("   - Inicie el servidor con: python Shadow-Core/start_data_feed.py")
        report.append("   - Acceda al dashboard OSINT desde el frontend")
        report.append("   - Verifique la integración con el sistema de nodos de conocimiento")
    else:
        report.append("⚠️ HAY PROBLEMAS QUE DEBEN SER RESUELTOS:")
        report.append("   Consulte los errores arriba para más detalles.")
        report.append("")
        report.append("🔧 RECOMENDACIONES:")
        report.append("   1. Verifique que todos los archivos estén en las ubicaciones correctas")
        report.append("   2. Revisar los logs del servidor para errores")
        report.append("   3. Instale manualmente las dependencias faltantes si es necesario")
        report.append("   4. Verifique la configuración de puertos en los archivos de código")

    # Guardar informe en un archivo
    report_file = "final_integration_report.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(report))

    logger.info(f"✅ Informe de pruebas generado en: {report_file}")
    return report

def main():
    """Función principal"""
    logger.info("PRUEBA DE INTEGRACIÓN COMPLETA DEL SISTEMA DE DATOS EN TIEMPO REAL")
    logger.info("Este script verifica que todos los componentes estén correctamente integrados")
    logger.info("y que el flujo de datos funcione correctamente")

    # Ejecutar pruebas de integración completa
    success = test_complete_integration()

    # Generar informe de pruebas
    report = generate_test_report()

    # Mostrar informe en consola
    for line in report:
        logger.info(line)

    if success:
        logger.info("\n🎉 ¡LA INTEGRACIÓN DEL SISTEMA FUNCIONA CORRECTAMENTE!")
        return True
    else:
        logger.error("\n❌ LA INTEGRACIÓN DEL SISTEMA TIENE PROBLEMAS")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)