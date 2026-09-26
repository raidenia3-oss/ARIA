"""
data_feed.py - Módulo para la ingestión de datos en tiempo real desde Shadow-Core
Implementa un servidor WebSocket con Socket.IO para transmitir alertas de seguridad y OSINT
"""

import os
import json
import time
import random
import feedparser
from datetime import datetime
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from threading import Thread
import logging
from logging.handlers import RotatingFileHandler

# Configuración del logger
logging.basicConfig(level=logging.INFO, encoding='utf-8')
logger = logging.getLogger(__name__)
logger.handlers.clear()  # Limpiar handlers existentes
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Configuración de archivos de log rotativos
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

handler = RotatingFileHandler(
    os.path.join(log_dir, 'data_feed.log'),
    maxBytes=1000000,
    backupCount=3
)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Configuración del servidor Flask y Socket.IO
app = Flask(__name__)
app.config['SECRET_KEY'] = 'aura-shadow-core-secret-key'

# Determinar el mejor modo asíncrono disponible para Flask-SocketIO
async_mode = None
try:
    import eventlet
    eventlet.monkey_patch()
    async_mode = 'eventlet'
    logger.info('Eventlet encontrado y parche aplicado para Socket.IO')
except ImportError:
    logger.warning('Eventlet no encontrado. Buscando gevent...')

if async_mode is None:
    try:
        import gevent
        async_mode = 'gevent'
        logger.info('Gevent encontrado y será usado para Socket.IO')
    except ImportError:
        logger.warning('Gevent no encontrado. Socket.IO usará threading como fallback')

# Configurar Socket.IO sin manejo de sesiones
socketio = SocketIO(app, cors_allowed_origins="*", async_mode=async_mode or 'threading', logger=True, engineio_logger=True, session=False)

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
    },
    'shadow_core_status': {
        'name': 'Shadow-Core Status',
        'description': 'Estado del sistema Shadow-Core',
        'categories': ['connection', 'threat', 'performance'],
        'severity_levels': ['info', 'warning', 'critical']
    }
}

# Datos de configuración
CONFIG = {
    'data_interval': 10,  # segundos entre alertas simuladas
    'max_clients': 100,
    'rooms': {
        'global': 'Alerta global para todos los clientes',
        'osint': 'Alertas específicas de OSINT',
        'security': 'Alertas específicas de seguridad',
        'threat': 'Alertas de amenaza crítica'
    },
    'threat_levels': {
        'low': {'color': '#4CAF50', 'severity': 1},
        'medium': {'color': '#FFC107', 'severity': 2},
        'high': {'color': '#FF5722', 'severity': 3},
        'critical': {'color': '#F44336', 'severity': 4},
        'warning': {'color': '#FF9800', 'severity': 2},
        'alert': {'color': '#FF5722', 'severity': 3},
        'info': {'color': '#2196F3', 'severity': 1}
    },
    'node_mapping': {
        'AURA/Shadow-Core/001-shadow-core-spec.md': ['security', 'threat'],
        'AURA/physics_ui_integration.md': ['security'],
        'AURA/antigravity_nodes.md': ['security', 'osint'],
        'AURA/obsidian_integration.md': ['osint']
    }
}

# Variables globales
active_clients = 0
client_rooms = {}
threat_simulation_active = True
simulation_thread = None

# Función para generar alertas simuladas
def generate_simulated_alert():
    """Genera una alerta simulada de seguridad/OSINT"""
    source_types = ['osint_alerts', 'security_threats', 'shadow_core_status']
    source = random.choice(source_types)

    # Seleccionar tipo y severidad
    alert_type = random.choice(DATA_SOURCES[source]['categories'])
    severity = random.choice(DATA_SOURCES[source]['severity_levels'])

    # Datos base de la alerta
    alert = {
        'timestamp': datetime.utcnow().isoformat(),
        'source': source,
        'id': f"alert_{int(time.time() * 1000)}",
        'type': alert_type,
        'severity': severity,
        'title': f"ALERTA: {random.choice(['Incidente detectado', 'Posible amenaza', 'Evento crítico', 'Anomalía encontrada'])}",
        'description': generate_random_description(source, alert_type),
        'details': generate_random_details(source, alert_type),
        'affected_nodes': get_affected_nodes(source, alert_type),
        'metadata': {
            'ip': f"192.168.1.{random.randint(1, 254)}",
            'domain': f"example{random.randint(100, 999)}.com",
            'port': random.choice([80, 443, 22, 3389, 8080, None]),
            'confidence': random.uniform(0.7, 0.99),
            'last_seen': datetime.utcnow().isoformat()
        }
    }

    # Añadir color basado en severidad
    alert['color'] = CONFIG['threat_levels'][alert['severity']]['color']

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
        },
        'shadow_core_status': {
            'connection': [
                "Estado de conexión del Shadow-Core: {}",
                "Latencia en la conexión con Shadow-Core: {}ms",
                "Problema de conectividad detectado con Shadow-Core",
                "Shadow-Core ha recuperado la conexión"
            ],
            'threat': [
                "Nuevo nivel de amenaza detectado: {}",
                "Shadow-Core ha detectado una amenaza potencial",
                "Amenaza resuelta en el sistema",
                "Nuevo evento de amenaza registrado: {}"
            ],
            'performance': [
                "Rendimiento del Shadow-Core: {}%",
                "Recursos del sistema bajo presión",
                "Shadow-Core operando con normalidad",
                "Optimización recomendada para Shadow-Core"
            ]
        }
    }

    # Seleccionar una descripción aleatoria
    if source in descriptions and alert_type in descriptions[source]:
        description_template = random.choice(descriptions[source][alert_type])
        if "{} intentando acceder a {}" in description_template:
            return description_template.format(
                random.choice(['198.51.100.78', '103.86.98.45', '203.0.113.45']),
                random.choice(['SSH', 'RDP', 'FTP', 'HTTP', 'HTTPS'])
            )
        else:
            return description_template.format(
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
        },
        'shadow_core_status': {
            'connection': [
                {"type": "status", "value": "online", "uptime": "4 days, 12 hours"},
                {"type": "latency", "value": "45ms", "direction": "client-server"},
                {"type": "issue", "value": "Network latency spike", "duration": "2 minutes"},
                {"type": "recovery", "value": "Connection restored", "timestamp": datetime.utcnow().isoformat()}
            ],
            'threat': [
                {"type": "level", "value": "high", "description": "Multiple scan attempts detected"},
                {"type": "source", "value": "external", "ip": "203.0.113.45"},
                {"type": "action", "value": "Isolation initiated", "duration": "30 seconds"},
                {"type": "resolution", "value": "Threat neutralized", "timestamp": datetime.utcnow().isoformat()}
            ],
            'performance': [
                {"type": "cpu", "value": "87%", "threshold": "90%"},
                {"type": "memory", "value": "65%", "available": "3.2GB"},
                {"type": "disk", "value": "12%", "path": "/var/log"},
                {"type": "network", "value": "2.1Mbps", "direction": "inbound"}
            ]
        }
    }

    # Seleccionar detalles aleatorios
    if source in details and alert_type in details[source]:
        return random.sample(details[source][alert_type], random.randint(1, 3))
    return [{"type": "info", "value": f"Detalles de la alerta de {alert_type}"}]

# Función para obtener nodos afectados
def get_affected_nodes(source, alert_type):
    """Determina qué nodos del conocimiento podrían estar afectados por esta alerta"""
    affected = []

    # Nodos específicos según el tipo de alerta
    if source == 'osint_alerts':
        if alert_type in ['phishing', 'data_leak', 'malware']:
            affected.extend(['AURA/Shadow-Core/001-shadow-core-spec.md', 'AURA/obsidian_integration.md'])
        elif alert_type == 'vulnerability':
            affected.extend(['AURA/physics_ui_integration.md', 'AURA/antigravity_nodes.md'])

    elif source == 'security_threats':
        if alert_type in ['brute_force', 'exploit']:
            affected.extend(['AURA/Shadow-Core/001-shadow-core-spec.md', 'AURA/physics_ui_integration.md'])
        elif alert_type in ['scan', 'anomaly']:
            affected.extend(['AURA/antigravity_nodes.md', 'AURA/obsidian_integration.md'])

    elif source == 'shadow_core_status':
        if alert_type in ['connection', 'threat']:
            affected.extend(['AURA/Shadow-Core/001-shadow-core-spec.md', 'AURA/physics_ui_integration.md'])
        elif alert_type == 'performance':
            affected.extend(['AURA/antigravity_nodes.md', 'AURA/obsidian_integration.md'])

    # Asegurarnos de que no haya duplicados
    affected = list(set(affected))

    # Si no hay nodos específicos afectados, seleccionar algunos aleatorios
    if len(affected) == 0:
        all_nodes = list(CONFIG['node_mapping'].keys())
        affected = random.sample(all_nodes, min(2, len(all_nodes)))

    return affected

# Función para manejar eventos de Socket.IO
def handle_socket_events():
    """Maneja eventos de Socket.IO para la transmisión de datos en tiempo real"""
    @socketio.on('connect')
    def on_connect():
        global active_clients
        client_id = request.sid
        logger.info(f"Cliente conectado: {client_id} (Total: {active_clients + 1})")

        # Añadir cliente a la sala global
        join_room('global', client_id)
        active_clients += 1

        # Enviar mensaje de bienvenida
        socketio.emit('system_message', {
            'type': 'info',
            'message': 'Conectado al servidor de alertas de Shadow-Core',
            'timestamp': datetime.utcnow().isoformat(),
            'client_id': client_id
        }, room=client_id)

        # Enviar configuración inicial
        socketio.emit('config_update', {
            'threat_levels': CONFIG['threat_levels'],
            'node_mapping': CONFIG['node_mapping'],
            'data_sources': DATA_SOURCES
        }, room=client_id)

    @socketio.on('disconnect')
    def on_disconnect():
        global active_clients
        client_id = request.sid
        logger.info(f"Cliente desconectado: {client_id} (Total: {active_clients})")

        # Eliminar cliente de todas las salas
        for room in client_rooms.get(client_id, []):
            leave_room(room)
        if client_id in client_rooms:
            del client_rooms[client_id]

        active_clients -= 1

    @socketio.on('subscribe')
    def on_subscribe(data):
        """Maneja suscripciones a salas específicas"""
        client_id = request.sid
        room = data.get('room')

        if room in CONFIG['rooms']:
            join_room(room, client_id)
            if client_id not in client_rooms:
                client_rooms[client_id] = []
            if room not in client_rooms[client_id]:
                client_rooms[client_id].append(room)

            logger.info(f"Cliente {client_id} suscripto a sala: {room}")
            socketio.emit('subscription_confirm', {
                'room': room,
                'message': f"Suscripto a alertas de {room}",
                'timestamp': datetime.utcnow().isoformat()
            }, room=client_id)
        else:
            socketio.emit('error', {
                'message': f"Sala no válida: {room}",
                'available_rooms': list(CONFIG['rooms'].keys())
            }, room=client_id)

    @socketio.on('unsubscribe')
    def on_unsubscribe(data):
        """Maneja cancelación de suscripciones"""
        client_id = request.sid
        room = data.get('room')

        if room in CONFIG['rooms'] and client_id in client_rooms:
            leave_room(room, client_id)
            client_rooms[client_id].remove(room)
            if len(client_rooms[client_id]) == 0:
                del client_rooms[client_id]

            logger.info(f"Cliente {client_id} canceló suscripción a sala: {room}")
            socketio.emit('subscription_cancel', {
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
            socketio.emit('acknowledgment', {
                'alert_id': alert_id,
                'message': 'Alerta confirmada',
                'timestamp': datetime.utcnow().isoformat(),
                'client_id': client_id
            }, room=client_id)

    @socketio.on('new_alert')
    def on_new_alert(alert_data):
        """Maneja alertas entrantes desde clientes externos"""
        logger.info(f"Alerta recibida desde cliente externo: {alert_data.get('id', 'desconocido')}")
        socketio.emit('new_alert', alert_data, room='global')
        socketio.emit('new_alert', alert_data, room='security')

# Función para iniciar la simulación de alertas
def start_alert_simulation():
    """Inicia el hilo de simulación de alertas"""
    global simulation_thread, threat_simulation_active

    def simulation_loop():
        while threat_simulation_active:
            try:
                # Generar alerta simulada
                alert = None
                try:
                    alert = generate_simulated_alert()
                except Exception as e:
                    logger.error(f"Error al generar alerta simulada: {str(e)}")
                    time.sleep(CONFIG['data_interval'])
                    continue

                # Emitir alerta a todos los clientes en la sala global
                socketio.emit('new_alert', alert, room='global')

                # Emitir alerta a salas específicas según el tipo
                if alert['source'] == 'osint_alerts':
                    socketio.emit('new_alert', alert, room='osint')
                elif alert['source'] == 'security_threats':
                    socketio.emit('new_alert', alert, room='security')
                elif alert['source'] == 'shadow_core_status':
                    socketio.emit('new_alert', alert, room='security')
                    socketio.emit('new_alert', alert, room='threat')

                # Emitir alerta a clientes suscritos a nodos afectados
                for node_path in alert['affected_nodes']:
                    if node_path in CONFIG['node_mapping']:
                        for room in CONFIG['node_mapping'][node_path]:
                            socketio.emit('new_alert', alert, room=room)

                logger.info(f"Alerta emitida: {alert['id']} - {alert['severity']} - {alert['type']}")

            except Exception as e:
                logger.error(f"Error inesperado en la simulación de alertas: {str(e)}")

            # Esperar antes de la siguiente alerta
            time.sleep(CONFIG['data_interval'])

    # Iniciar el hilo de simulación
    simulation_thread = Thread(target=simulation_loop, daemon=True)
    simulation_thread.start()
    logger.info("Simulación de alertas iniciada")

# Función para detener la simulación
def stop_alert_simulation():
    """Detiene la simulación de alertas"""
    global threat_simulation_active, simulation_thread

    threat_simulation_active = False
    if simulation_thread:
        simulation_thread.join(timeout=1)
    logger.info("Simulación de alertas detenida")

# Función para reiniciar la simulación
def restart_alert_simulation():
    """Reinicia la simulación de alertas"""
    stop_alert_simulation()
    start_alert_simulation()

# Configuración para el feed RSS de noticias de seguridad
RSS_FEED_CONFIG = {
    'url': 'https://thehackernews.com/feed/',
    'keywords': ['vulnerability', 'breach', 'zero-day', 'exploit', 'malware', 'phishing', 'data leak'],
    'interval': 300,  # segundos (5 minutos)
    'last_checked': None,
    'processed_entries': set()
}

# Función para procesar feed RSS de noticias de seguridad
def process_rss_feed():
    """Procesa el feed RSS de noticias de seguridad y envía alertas relevantes"""
    try:
        logger.info("Procesando feed RSS de noticias de seguridad...")

        # Obtener feed RSS
        feed = feedparser.parse(RSS_FEED_CONFIG['url'])

        # Actualizar última hora de procesamiento
        RSS_FEED_CONFIG['last_checked'] = datetime.utcnow().isoformat()

        # Procesar cada entrada del feed
        for entry in feed.entries:
            entry_id = f"rss_{entry.link}_{entry.published}"

            # Verificar si ya procesamos esta entrada
            if entry_id in RSS_FEED_CONFIG['processed_entries']:
                continue

            # Obtener título y descripción
            title = entry.title
            description = entry.description

            # Verificar si contiene palabras clave
            text_content = f"{title} {description}".lower()
            has_keywords = any(keyword in text_content for keyword in RSS_FEED_CONFIG['keywords'])

            if has_keywords:
                # Crear datos básicos de la noticia
                news_data = {
                    'title': title,
                    'description': description,
                    'url': entry.link,
                    'date': entry.published
                }

                # Analizar la noticia con el LLM
                from llm_analyzer import process_news_article
                analysis = process_news_article(news_data)

                # Crear alerta de OSINT con el análisis del LLM
                alert = {
                    'timestamp': datetime.utcnow().isoformat(),
                    'source': 'osint_news',
                    'id': entry_id,
                    'type': 'security_news',
                    'severity': 'medium',
                    'title': title,
                    'description': description,
                    'analysis': analysis,  # Añadir el análisis del LLM
                    'details': [
                        {'type': 'url', 'value': entry.link},
                        {'type': 'source', 'value': 'The Hacker News'},
                        {'type': 'published', 'value': entry.published},
                        {'type': 'keywords', 'value': [kw for kw in RSS_FEED_CONFIG['keywords'] if kw in text_content]},
                        {'type': 'llm_analysis', 'value': analysis}  # Añadir el análisis del LLM
                    ],
                    'metadata': {
                        'url': entry.link,
                        'source': 'The Hacker News',
                        'confidence': 0.85,
                        'last_seen': datetime.utcnow().isoformat(),
                        'published': entry.published,
                        'threat_level': analysis.get('nivel_amenaza', 3),  # Nivel de amenaza del LLM
                        'tags': analysis.get('tags', [])  # Tags del LLM
                    },
                    'action_required': True,
                    'action_type': 'save_to_obsidian',
                    'action_target': title,
                    'resumen_tactico': analysis.get('resumen_tactico', '')  # Resumen táctico para el frontend
                }

                # Guardar alertas en una cola para procesamiento posterior
                global rss_alert_queue
                rss_alert_queue.append(alert)

                # Registrar que procesamos esta entrada
                RSS_FEED_CONFIG['processed_entries'].add(entry_id)

                logger.info(f"Alerta OSINT encontrada y analizada: {alert['title']} (Nivel de amenaza: {alert['metadata'].get('threat_level', 3)})")

        return True
    except Exception as e:
        logger.error(f"Error al procesar feed RSS: {str(e)}")
        return False

# Cola global para alertas RSS
rss_alert_queue = []

# Función para procesar alertas de la cola RSS
def process_rss_alert_queue():
    """Procesa las alertas de la cola RSS y las envía a los clientes"""
    global rss_alert_queue

    while True:
        try:
            # Procesar alertas en la cola
            if rss_alert_queue:
                alert = rss_alert_queue.pop(0)

                # Emitir alerta a todos los clientes en la sala global
                socketio.emit('new_alert', alert, room='global')

                # Emitir alerta a sala de OSINT
                socketio.emit('new_alert', alert, room='osint')

                logger.info(f"Alerta OSINT enviada: {alert['title']}")

            # Esperar antes de la siguiente verificación
            time.sleep(1)
        except Exception as e:
            logger.error(f"Error en el procesamiento de cola RSS: {str(e)}")
            time.sleep(5)  # Esperar 5 segundos antes de reintentar

# Función para procesar feed RSS en segundo plano
def start_rss_feed_processing():
    """Inicia los hilos para procesar el feed RSS y su cola"""
    def rss_processing_loop():
        while True:
            try:
                # Procesar feed RSS
                process_rss_feed()

                # Esperar antes de la siguiente verificación
                time.sleep(RSS_FEED_CONFIG['interval'])
            except Exception as e:
                logger.error(f"Error en el bucle de procesamiento RSS: {str(e)}")
                time.sleep(60)  # Esperar 1 minuto antes de reintentar

    # Iniciar el hilo de procesamiento RSS
    rss_thread = Thread(target=rss_processing_loop, daemon=True)
    rss_thread.start()

    # Iniciar el hilo de procesamiento de cola RSS
    rss_queue_thread = Thread(target=process_rss_alert_queue, daemon=True)
    rss_queue_thread.start()

    logger.info("Procesamiento de feed RSS iniciado")

# Función para obtener el estado del servidor
def get_server_status():
    """Devuelve el estado actual del servidor"""
    return {
        'status': 'running',
        'active_clients': active_clients,
        'threat_simulation': 'active' if threat_simulation_active else 'inactive',
        'rss_feed': {
            'last_checked': RSS_FEED_CONFIG['last_checked'],
            'interval': RSS_FEED_CONFIG['interval'],
            'keywords': RSS_FEED_CONFIG['keywords']
        },
        'last_alert_time': datetime.utcnow().isoformat(),
        'data_interval': CONFIG['data_interval'],
        'rooms': CONFIG['rooms'],
        'threat_levels': CONFIG['threat_levels']
    }

# Función para manejar solicitudes HTTP
def handle_http_requests():
    """Maneja solicitudes HTTP para el servidor"""
    @app.route('/api/status', methods=['GET'])
    def api_status():
        return jsonify(get_server_status())

    @app.route('/api/alerts', methods=['GET'])
    def api_alerts():
        return jsonify({
            'message': 'Endpoint para obtener alertas históricas',
            'status': 'implementar'
        })

    @app.route('/api/simulate', methods=['POST'])
    def api_simulate():
        """Simula una alerta manual"""
        try:
            alert = generate_simulated_alert()
            socketio.emit('new_alert', alert, room='global')
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
            start_alert_simulation()
            return jsonify({
                'status': 'success',
                'message': 'Simulación de alertas iniciada'
            }), 200
        elif action == 'stop':
            stop_alert_simulation()
            return jsonify({
                'status': 'success',
                'message': 'Simulación de alertas detenida'
            }), 200
        elif action == 'restart':
            restart_alert_simulation()
            return jsonify({
                'status': 'success',
                'message': 'Simulación de alertas reiniciada'
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Acción no válida',
                'available_actions': ['start', 'stop', 'restart']
            }), 400

# Función principal para iniciar el servidor
def start_data_feed_server(port=5002):
    """Inicia el servidor de datos en tiempo real"""
    logger.info(f"Iniciando servidor de datos en tiempo real en el puerto {port}")

    # Registrar manejadores de eventos
    handle_socket_events()
    handle_http_requests()

    # Iniciar simulación de alertas
    start_alert_simulation()

    # Iniciar procesamiento de feed RSS
    start_rss_feed_processing()

    # Iniciar Active Threat Scanner (escaneo cada hora)
    logger.info("Iniciando Active Threat Scanner...")
    try:
        from security_scanner import start_scanner_loop, stop_scanner_loop, create_callback_for_data_feed
        scanner_callback = create_callback_for_data_feed(socketio)
        scanner_thread = start_scanner_loop(callback=scanner_callback)
        logger.info("Active Threat Scanner iniciado correctamente")
    except Exception as e:
        logger.error(f"Error al iniciar Active Threat Scanner: {str(e)}")

    # Iniciar servidor
    try:
        socketio.run(app, host='0.0.0.0', port=port, debug=True)
    except KeyboardInterrupt:
        logger.info("Servidor detenido por el usuario")
    except Exception as e:
        logger.error(f"Error al iniciar el servidor: {str(e)}")
    finally:
        # Detener scanner
        try:
            stop_scanner_loop()
        except:
            pass
        stop_alert_simulation()
        logger.info("Servidor de datos en tiempo real detenido")

# Función para ejecutar el servidor como script
if __name__ == '__main__':
    # Verificar si hay requisitos instalados
    try:
        import eventlet
        eventlet.monkey_patch()
        logger.info("Eventlet monkey patch aplicado para mejor rendimiento de Socket.IO")
    except ImportError:
        logger.warning("Eventlet no encontrado. Socket.IO puede tener rendimiento reducido.")

    # Iniciar servidor
    start_data_feed_server()