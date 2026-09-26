"""
start_test_server.py - Script para iniciar un servidor de prueba de datos en tiempo real
Este script inicia un servidor Flask-SocketIO simple para pruebas
"""

import os
import sys
import time
import logging
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from threading import Thread
import random
from datetime import datetime

# Configuración del logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración del servidor
app = Flask(__name__)
app.config['SECRET_KEY'] = 'test-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

# Configuración de datos de prueba
DATA_SOURCES = {
    'osint_alerts': {
        'name': 'OSINT Alerts',
        'description': 'Alertas de inteligencia de fuentes abiertas',
        'categories': ['phishing', 'data_leak', 'malware', 'vulnerability'],
        'severity_levels': ['low', 'medium', 'high', 'critical']
    },
    'security_threats': {
        'name': 'Security Threats',
        'description': 'Amenazas de seguridad detectadas en la red',
        'categories': ['brute_force', 'scan', 'exploit', 'anomaly'],
        'severity_levels': ['warning', 'alert', 'critical']
    }
}

# Configuración de colores por severidad
THREAT_LEVELS = {
    'low': {'color': '#4CAF50', 'severity': 1},
    'medium': {'color': '#FFC107', 'severity': 2},
    'high': {'color': '#FF5722', 'severity': 3},
    'critical': {'color': '#F44336', 'severity': 4},
    'warning': {'color': '#FF9800', 'severity': 2},
    'alert': {'color': '#FF5722', 'severity': 3}
}

# Variables globales
active_clients = 0
test_mode = True
test_counter = 0

# Función para generar alertas simuladas
def generate_test_alert():
    """Genera una alerta simulada de prueba"""
    global test_counter

    source_types = ['osint_alerts', 'security_threats']
    source = random.choice(source_types)

    # Datos base de la alerta
    alert = {
        'timestamp': datetime.utcnow().isoformat(),
        'source': source,
        'id': f"test_alert_{test_counter}",
        'type': random.choice(DATA_SOURCES[source]['categories']),
        'severity': random.choice(DATA_SOURCES[source]['severity_levels']),
        'title': f"ALERTA DE PRUEBA: {random.choice(['Incidente detectado', 'Posible amenaza', 'Evento crítico', 'Anomalía encontrada'])}",
        'description': generate_random_description(source, alert['type']),
        'details': generate_random_details(source, alert['type']),
        'affected_nodes': ['AURA/Shadow-Core/001-shadow-core-spec.md', 'AURA/physics_ui_integration.md'],
        'metadata': {
            'ip': f"192.168.1.{random.randint(1, 254)}",
            'domain': f"example{random.randint(100, 999)}.com",
            'port': random.choice([80, 443, 22, 3389, 8080, None]),
            'confidence': random.uniform(0.7, 0.99),
            'last_seen': datetime.utcnow().isoformat()
        }
    }

    # Añadir color basado en severidad
    alert['color'] = THREAT_LEVELS[alert['severity']]['color']

    # Incrementar contador
    test_counter += 1

    return alert

# Función para generar descripciones aleatorias
def generate_random_description(source, alert_type):
    descriptions = {
        'osint_alerts': {
            'phishing': [
                "Se ha detectado un sitio de phishing que imita a {}",
                "Campaña de phishing dirigida a usuarios de {}",
                "URL sospechosa encontrada en foros relacionados con {}",
                "Dominio recién registrado que podría estar relacionado con phishing"
            ],
            'data_leak': [
                "Posible fuga de datos detectada en {}",
                "Archivo con información sensible encontrado en {}",
                "Base de datos expuesta en {}",
                "Credenciales filtradas en foro público relacionado con {}"
            ],
            'malware': [
                "Nueva muestra de malware detectada en {}",
                "Archivo malicioso distribuido desde {}",
                "Dominio asociado a malware encontrado en {}",
                "Campaña de malware dirigida a servidores en {}"
            ],
            'vulnerability': [
                "Vulnerabilidad crítica detectada en {}",
                "Servicio en {} expuesto a exploits conocidos",
                "Configuración insegura encontrada en {}",
                "Versión obsoleta de software en {}"
            ]
        },
        'security_threats': {
            'brute_force': [
                "Intento de fuerza bruta detectado en {}",
                "Múltiples intentos de autenticación fallidos en {}",
                "Ataco de fuerza bruta contra servicio en {}",
                "IP {} intentando acceder a {} con credenciales incorrectas"
            ],
            'scan': [
                "Escaneo de puertos detectado desde {}",
                "Actividad de reconocimiento en {}",
                "IP {} explorando servicios en la red",
                "Escaneo de vulnerabilidades en progreso contra {}"
            ],
            'exploit': [
                "Intento de explotación detectado en {}",
                "Ataque exploit contra servicio en {}",
                "Vulnerabilidad siendo explotada activamente en {}",
                "Conexión sospechosa desde {} intentando explotar {}"
            ],
            'anomaly': [
                "Comportamiento anómalo detectado en {}",
                "Tráfico inusual desde {}",
                "Patrón de red sospechoso en {}",
                "Actividad no autorizada detectada en {}"
            ]
        }
    }

    # Seleccionar una descripción aleatoria
    if source in descriptions and alert_type in descriptions[source]:
        return random.choice(descriptions[source][alert_type]).format(
            random.choice(['el sistema', 'la red', 'el servidor', 'la aplicación', 'Shadow-Core'])
        )
    return f"Alerta de {alert_type} detectada en {source}"

# Función para generar detalles aleatorios
def generate_random_details(source, alert_type):
    details = {
        'osint_alerts': {
            'phishing': [
                {"type": "url", "value": "http://malicious-phishing-site.com/login", "status": "active"},
                {"type": "domain", "value": "evil-look-alike.com", "registration_date": "2023-01-15"},
                {"type": "email", "value": "support@fake-bank.com", "template": "Urgent: Your account has been compromised!"},
                {"type": "payload", "value": "Malicious JavaScript payload detected"}
            ],
            'data_leak': [
                {"type": "file", "value": "credentials.csv", "size": "1.2MB", "sensitive": True},
                {"type": "database", "value": "user_data", "records": "5000", "exposed": True},
                {"type": "api", "value": "/user/profile", "endpoint": "example.com/api/v1"},
                {"type": "leak_source", "value": "Public GitHub repository", "url": "https://github.com/leaked-data"}
            ],
            'malware': [
                {"type": "sample", "value": "Trojan.Win32.Generic", "md5": "a1b2c3d4e5f67890"},
                {"type": "c2", "value": "185.143.223.56", "port": 443, "protocol": "HTTPS"},
                {"type": "file", "value": "setup.exe", "size": "2.1MB", "detected_by": "ClamAV"},
                {"type": "technique", "value": "Phishing + Drive-by Download", "tactic": "Initial Access"}
            ],
            'vulnerability': [
                {"type": "cve", "value": "CVE-2023-4567", "severity": "Critical", "cvss": 9.8},
                {"type": "service", "value": "Apache Tomcat", "version": "9.0.12", "exploit": "RCE"},
                {"type": "config", "value": "Default credentials", "service": "FTP", "port": 21},
                {"type": "patch", "value": "Available", "url": "https://example.com/security/patch"}
            ]
        },
        'security_threats': {
            'brute_force': [
                {"type": "target", "value": "SSH", "port": 22, "attempts": 124},
                {"type": "source", "value": "198.51.100.78", "country": "RU", "asn": "AS12345"},
                {"type": "pattern", "value": "admin:password123", "success": False},
                {"type": "timing", "value": "3 attempts per second", "duration": "15 minutes"}
            ],
            'scan': [
                {"type": "scan_type", "value": "Nmap", "options": "-sV -O", "version": True},
                {"type": "targets", "value": ["192.168.1.1", "192.168.1.100", "192.168.1.200"], "ports": [21, 22, 80, 443]},
                {"type": "source", "value": "103.86.98.45", "country": "CN", "timestamp": datetime.utcnow().isoformat()},
                {"type": "services", "value": ["HTTP/1.1", "SSH-2.0", "OpenVPN 2.4.9"], "os": "Linux"}
            ],
            'exploit': [
                {"type": "vulnerability", "value": "Heartbleed", "cve": "CVE-2014-0160"},
                {"type": "target", "value": "192.168.1.5:443", "service": "OpenSSL"},
                {"type": "payload", "value": "Heartbleed exploit payload", "size": "64 bytes"},
                {"type": "outcome", "value": "Memory leak detected", "data_size": "1.2KB"}
            ],
            'anomaly': [
                {"type": "pattern", "value": "Unusual traffic spike", "time": "03:45 UTC"},
                {"type": "source", "value": "185.143.223.56", "country": "RU"},
                {"type": "destination", "value": "192.168.1.100:80", "service": "HTTP"},
                {"type": "behavior", "value": "Data exfiltration pattern detected", "volume": "4.5GB"}
            ]
        }
    }

    # Seleccionar detalles aleatorios
    if source in details and alert_type in details[source]:
        return random.sample(details[source][alert_type], random.randint(1, 3))
    return [{"type": "info", "value": f"Detalles de la alerta de {alert_type}"}]

# Función para manejar eventos de Socket.IO
def setup_socketio_events():
    """Configura los eventos de Socket.IO"""
    @socketio.on('connect')
    def on_connect():
        global active_clients
        client_id = request.sid
        logger.info(f"Cliente conectado: {client_id} (Total: {active_clients + 1})")

        # Añadir cliente a la sala global
        join_room('global', client_id)
        active_clients += 1

        # Enviar mensaje de bienvenida
        emit('system_message', {
            'type': 'info',
            'message': 'Conectado al servidor de prueba de alertas',
            'timestamp': datetime.utcnow().isoformat(),
            'client_id': client_id
        }, room=client_id)

        # Enviar configuración inicial
        emit('config_update', {
            'threat_levels': THREAT_LEVELS,
            'data_sources': DATA_SOURCES
        }, room=client_id)

        # Enviar una alerta de prueba inmediatamente
        alert = generate_test_alert()
        emit('new_alert', alert, room=client_id)

    @socketio.on('disconnect')
    def on_disconnect():
        global active_clients
        client_id = request.sid
        logger.info(f"Cliente desconectado: {client_id} (Total: {active_clients})")
        active_clients -= 1

    @socketio.on('subscribe')
    def on_subscribe(data):
        """Maneja suscripciones a salas específicas"""
        client_id = request.sid
        room = data.get('room')

        if room in ['global', 'osint', 'security', 'threat']:
            join_room(room, client_id)
            logger.info(f"Cliente {client_id} suscripto a sala: {room}")
            emit('subscription_confirm', {
                'room': room,
                'message': f"Suscripto a alertas de {room}",
                'timestamp': datetime.utcnow().isoformat()
            }, room=client_id)
        else:
            emit('error', {
                'message': f"Sala no válida: {room}",
                'available_rooms': ['global', 'osint', 'security', 'threat']
            }, room=client_id)

    @socketio.on('unsubscribe')
    def on_unsubscribe(data):
        """Maneja cancelación de suscripciones"""
        client_id = request.sid
        room = data.get('room')

        if room in ['global', 'osint', 'security', 'threat']:
            leave_room(room, client_id)
            logger.info(f"Cliente {client_id} canceló suscripción a sala: {room}")
            emit('subscription_cancel', {
                'room': room,
                'message': f"Cancelado suscripción a alertas de {room}",
                'timestamp': datetime.utcnow().isoformat()
            }, room=client_id)

    @socketio.on('acknowledge')
    def on_acknowledge(data):
        """Maneja confirmación de recepción de alertas"""
        alert_id = data.get('alert_id')
        client_id = request.sid

        if alert_id:
            logger.info(f"Cliente {client_id} ha confirmado recepción de alerta: {alert_id}")
            emit('acknowledgment', {
                'alert_id': alert_id,
                'message': 'Alerta confirmada',
                'timestamp': datetime.utcnow().isoformat(),
                'client_id': client_id
            }, room=client_id)

# Función para manejar solicitudes HTTP
def setup_http_endpoints():
    """Configura los endpoints HTTP"""
    @app.route('/api/status', methods=['GET'])
    def api_status():
        return jsonify({
            'status': 'running',
            'active_clients': active_clients,
            'test_mode': test_mode,
            'last_alert_time': datetime.utcnow().isoformat(),
            'test_counter': test_counter
        })

    @app.route('/api/alerts', methods=['GET'])
    def api_alerts():
        return jsonify({
            'message': 'Endpoint para obtener alertas históricas',
            'status': 'implementado en modo de prueba',
            'alerts': []
        })

    @app.route('/api/simulate', methods=['POST'])
    def api_simulate():
        """Simula una alerta manual"""
        try:
            alert = generate_test_alert()
            emit('new_alert', alert, room='global')
            logger.info(f"Alerta simulada manualmente: {alert['id']}")
            return jsonify({
                'status': 'success',
                'alert': alert
            }), 200
        except Exception as e:
            logger.error(f"Error al simular alerta: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500

    @app.route('/api/control', methods=['POST'])
    def api_control():
        """Controla la simulación de alertas"""
        action = request.json.get('action')

        if action == 'start':
            logger.info("Iniciando simulación de alertas en modo de prueba")
            return jsonify({
                'status': 'success',
                'message': 'Simulación de alertas iniciada en modo de prueba'
            }), 200
        elif action == 'stop':
            logger.info("Deteniendo simulación de alertas en modo de prueba")
            return jsonify({
                'status': 'success',
                'message': 'Simulación de alertas detenida en modo de prueba'
            }), 200
        elif action == 'restart':
            logger.info("Reiniciando simulación de alertas en modo de prueba")
            return jsonify({
                'status': 'success',
                'message': 'Simulación de alertas reiniciada en modo de prueba'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Acción no válida',
                'available_actions': ['start', 'stop', 'restart']
            }), 400

# Función para iniciar el servidor de prueba
def start_test_server(port=5003):
    """Inicia el servidor de prueba de datos en tiempo real"""
    logger.info(f"Iniciando servidor de prueba en tiempo real en el puerto {port}")

    # Configurar eventos
    setup_socketio_events()
    setup_http_endpoints()

    # Iniciar servidor
    try:
        logger.info("Servidor de prueba listo. Presione Ctrl+C para detenerlo")
        socketio.run(app, host='0.0.0.0', port=port, debug=True)
    except KeyboardInterrupt:
        logger.info("Servidor detenido por el usuario")
    except Exception as e:
        logger.error(f"Error al iniciar el servidor: {str(e)}")
    finally:
        logger.info("Servidor de prueba detenido")

# Función para iniciar el servidor en segundo plano
def start_server_in_background():
    """Inicia el servidor en segundo plano"""
    import subprocess
    import time

    try:
        # Verificar si el servidor ya está en ejecución
        import requests
        try:
            response = requests.get("http://localhost:5003/api/status", timeout=2)
            if response.status_code == 200:
                logger.info("Servidor de prueba ya está en ejecución")
                return True
        except:
            pass

        # Iniciar el servidor en segundo plano
        logger.info("Iniciando servidor de prueba en segundo plano...")
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
            response = requests.get("http://localhost:5003/api/status", timeout=2)
            if response.status_code == 200:
                logger.info("Servidor de prueba iniciado correctamente en segundo plano")
                return True
            else:
                logger.error("Servidor de prueba no respondió correctamente")
                return False
        except:
            logger.error("Servidor de prueba no está respondiendo")
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
    start_test_server()

if __name__ == '__main__':
    main()