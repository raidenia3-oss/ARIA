"""
integrate_data_feed.py - Módulo para integrar el servidor de datos en tiempo real
con el frontend de AURA
"""

import os
import json
import logging
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from threading import Thread, Lock
import time
import requests
from datetime import datetime

# Configuración del logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración global
DATA_FEED_CONFIG = {
    'shadow_core_url': 'http://localhost:5002',
    'socketio_port': 5002,
    'reconnect_interval': 5,  # segundos entre reconexiones
    'max_reconnect_attempts': 10,
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
    },
    'connection_timeout': 30  # segundos de timeout para conexiones
}

# Variables globales
socketio_client = None
connected = False
reconnect_attempts = 0
last_alert_time = None
alert_history = []
history_lock = Lock()

# Función para conectar al servidor de datos
def connect_to_data_feed():
    """Establece conexión con el servidor de datos en tiempo real"""
    global socketio_client, connected, reconnect_attempts

    try:
        logger.info("Conectando al servidor de datos en tiempo real...")

        # Crear cliente Socket.IO
        socketio_client = SocketIO(
            DATA_FEED_CONFIG['shadow_core_url'],
            transports=['websocket'],
            logger=True,
            engineio_logger=True,
            path='/socket.io/',
            query_string='transport=websocket'
        )

        # Registrar eventos
        socketio_client.on('connect', on_connect)
        socketio_client.on('disconnect', on_disconnect)
        socketio_client.on('new_alert', on_new_alert)
        socketio_client.on('system_message', on_system_message)
        socketio_client.on('config_update', on_config_update)

        # Conectar
        socketio_client.connect()

        # Esperar a que se establezca la conexión
        time.sleep(1)

        # Verificar conexión
        if socketio_client.connected:
            connected = True
            reconnect_attempts = 0
            logger.info("Conexión establecida con el servidor de datos")

            # Suscribirse a salas importantes
            subscribe_to_rooms(['global', 'security', 'osint', 'threat'])

            return True
        else:
            logger.warning("Conexión fallida. Reintentando...")
            return False

    except Exception as e:
        logger.error(f"Error al conectar al servidor de datos: {e}")
        return False

# Función para manejar eventos de conexión
def on_connect():
    """Maneja evento de conexión exitosa"""
    global connected, reconnect_attempts
    connected = True
    reconnect_attempts = 0
    logger.info("Conexión establecida con el servidor de datos")

# Función para manejar eventos de desconexión
def on_disconnect():
    """Maneja evento de desconexión"""
    global connected, reconnect_attempts
    connected = False
    reconnect_attempts += 1
    logger.warning(f"Desconectado del servidor de datos. Reintentos: {reconnect_attempts}")

    # Notificar al sistema
    notify_disconnection()

# Función para manejar nuevas alertas
def on_new_alert(data):
    """Maneja nuevas alertas recibidas del servidor"""
    global last_alert_time

    try:
        # Procesar la alerta
        processed_alert = process_alert(data)

        # Guardar en historial
        with history_lock:
            alert_history.append(processed_alert)
            # Limitar historial a las últimas 100 alertas
            if len(alert_history) > 100:
                alert_history = alert_history[-100:]

        # Notificar al sistema principal
        notify_new_alert(processed_alert)

        # Actualizar tiempo de última alerta
        last_alert_time = datetime.utcnow()

        logger.info(f"Alerta recibida: {processed_alert['id']} - {processed_alert['severity']}")

    except Exception as e:
        logger.error(f"Error al procesar alerta: {e}")

# Función para manejar mensajes del sistema
def on_system_message(data):
    """Maneja mensajes del sistema del servidor"""
    try:
        logger.info(f"Mensaje del sistema: {data.get('message', 'Desconocido')}")
        notify_system_message(data)
    except Exception as e:
        logger.error(f"Error al procesar mensaje del sistema: {e}")

# Función para manejar actualizaciones de configuración
def on_config_update(data):
    """Maneja actualizaciones de configuración del servidor"""
    try:
        logger.info("Configuración actualizada recibida del servidor")
        update_config_from_server(data)
        notify_config_update(data)
    except Exception as e:
        logger.error(f"Error al procesar actualización de configuración: {e}")

# Función para suscribirse a salas
def subscribe_to_rooms(rooms):
    """Suscribe al cliente a las salas especificadas"""
    if not socketio_client or not socketio_client.connected:
        logger.warning("No se puede suscribir a salas: no hay conexión activa")
        return False

    try:
        for room in rooms:
            if room in DATA_FEED_CONFIG['node_mapping'].keys():
                # Suscribirse a nodos específicos
                for node_room in DATA_FEED_CONFIG['node_mapping'][room]:
                    socketio_client.emit('subscribe', {'room': node_room})
            else:
                # Suscribirse a sala global
                socketio_client.emit('subscribe', {'room': room})

        logger.info(f"Suscripto a salas: {rooms}")
        return True
    except Exception as e:
        logger.error(f"Error al suscribirse a salas: {e}")
        return False

# Función para procesar una alerta
def process_alert(alert_data):
    """Procesa una alerta cruda y la convierte a un formato estándar"""
    processed = {
        'id': alert_data.get('id', 'unknown'),
        'timestamp': alert_data.get('timestamp', datetime.utcnow().isoformat()),
        'source': alert_data.get('source', 'unknown'),
        'type': alert_data.get('type', 'unknown'),
        'severity': alert_data.get('severity', 'info'),
        'title': alert_data.get('title', 'Alerta sin título'),
        'description': alert_data.get('description', ''),
        'details': alert_data.get('details', []),
        'affected_nodes': alert_data.get('affected_nodes', []),
        'metadata': alert_data.get('metadata', {}),
        'color': alert_data.get('color', DATA_FEED_CONFIG['threat_levels']['info']['color']),
        'processed': datetime.utcnow().isoformat(),
        'threat_level': DATA_FEED_CONFIG['threat_levels'].get(alert_data.get('severity', 'info'), {}).get('severity', 1)
    }

    # Añadir información adicional
    processed['severity_info'] = {
        'level': processed['severity'],
        'color': processed['color'],
        'description': f"Nivel de amenaza: {processed['severity']}"
    }

    # Determinar nodos afectados en el sistema
    processed['system_nodes'] = []
    for node_path in processed['affected_nodes']:
        if node_path in DATA_FEED_CONFIG['node_mapping']:
            processed['system_nodes'].extend(DATA_FEED_CONFIG['node_mapping'][node_path])

    # Asegurarnos de que no haya duplicados
    processed['system_nodes'] = list(set(processed['system_nodes']))

    return processed

# Función para actualizar configuración desde el servidor
def update_config_from_server(server_config):
    """Actualiza la configuración local con la del servidor"""
    global DATA_FEED_CONFIG

    # Actualizar niveles de amenaza
    if 'threat_levels' in server_config:
        DATA_FEED_CONFIG['threat_levels'] = server_config['threat_levels']

    # Actualizar mapeo de nodos
    if 'node_mapping' in server_config:
        DATA_FEED_CONFIG['node_mapping'] = server_config['node_mapping']

    logger.info("Configuración actualizada desde el servidor")

# Función para notificar nuevas alertas al sistema principal
def notify_new_alert(alert):
    """Notifica al sistema principal sobre una nueva alerta"""
    try:
        # Registrar la alerta localmente
        event_payload = {
            'event_type': 'new_alert',
            'alert_id': alert.get('id'),
            'affected_nodes': alert.get('affected_nodes', []),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Aquí se podría enviar a un sistema de eventos remoto o local
        logger.info(f"✅ Alerta registrada en el sistema: {alert['id']}")
        
        # Retornar el evento para que el frontend lo procese si existe
        return {
            'status': 'notified',
            'event': event_payload
        }

    except Exception as e:
        logger.error(f"Error al notificar nueva alerta: {e}")
        return {'status': 'error', 'error': str(e)}

# Función para notificar desconexión
def notify_disconnection():
    """Notifica al sistema principal sobre una desconexión"""
    try:
        # Registrar evento de desconexión
        event_payload = {
            'event_type': 'data_feed_disconnected',
            'reconnect_attempts': reconnect_attempts,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info("✅ Evento de desconexión registrado en el sistema")
        return {
            'status': 'notified',
            'event': event_payload
        }

    except Exception as e:
        logger.error(f"Error al notificar desconexión: {e}")
        return {'status': 'error', 'error': str(e)}

# Función para notificar mensajes del sistema
def notify_system_message(message):
    """Notifica al sistema principal sobre un mensaje del sistema"""
    try:
        # Registrar mensaje del sistema
        event_payload = {
            'event_type': 'system_message',
            'message': message.get('message', ''),
            'severity': message.get('severity', 'info'),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info(f"✅ Mensaje del sistema registrado: {message.get('message', '')}")

    except Exception as e:
        logger.error(f"Error al notificar mensaje del sistema: {e}")
        return {'status': 'error', 'error': str(e)}

# Función para notificar actualización de configuración
def notify_config_update(config):
    """Notifica al sistema principal sobre una actualización de configuración"""
    try:
        # Registrar actualización de configuración
        event_payload = {
            'event_type': 'config_updated',
            'config': config,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info("✅ Actualización de configuración registrada en el sistema")
        return {
            'status': 'notified',
            'event': event_payload
        }

    except Exception as e:
        logger.error(f"Error al notificar actualización de configuración: {e}")
        return {'status': 'error', 'error': str(e)}

# Función para manejar el ciclo de reconexión
def handle_reconnection():
    """Maneja el ciclo de reconexión automática"""
    global connected, reconnect_attempts

    while True:
        if not connected and reconnect_attempts < DATA_FEED_CONFIG['max_reconnect_attempts']:
            logger.info(f"Intentando reconectar... (Intento {reconnect_attempts + 1})")
            if connect_to_data_feed():
                # Si la conexión se restableció, reiniciar contador
                reconnect_attempts = 0
            else:
                # Esperar antes de intentar nuevamente
                time.sleep(DATA_FEED_CONFIG['reconnect_interval'])
        else:
            # Si se agotaron los intentos de reconexión
            if reconnect_attempts >= DATA_FEED_CONFIG['max_reconnect_attempts']:
                logger.error("Máximo de intentos de reconexión alcanzado. Deteniendo intentos automáticos.")
                time.sleep(DATA_FEED_CONFIG['reconnect_interval'] * 2)  # Esperar más tiempo antes de intentar nuevamente
            else:
                time.sleep(DATA_FEED_CONFIG['reconnect_interval'])

# Función para obtener el historial de alertas
def get_alert_history(limit=100):
    """Devuelve el historial de alertas"""
    global alert_history, history_lock

    with history_lock:
        return alert_history[-limit:] if limit > 0 else alert_history.copy()

# Función para obtener el estado de la conexión
def get_connection_status():
    """Devuelve el estado actual de la conexión"""
    return {
        'connected': connected,
        'reconnect_attempts': reconnect_attempts,
        'last_alert_time': last_alert_time.isoformat() if last_alert_time else None,
        'alert_count': len(get_alert_history()),
        'max_attempts': DATA_FEED_CONFIG['max_reconnect_attempts']
    }

# Función para iniciar el módulo de integración
def start_data_feed_integration():
    """Inicia el módulo de integración con el servidor de datos"""
    logger.info("Iniciando módulo de integración con el servidor de datos en tiempo real")

    # Intentar conectar inicialmente
    if not connect_to_data_feed():
        logger.warning("Primera conexión fallida. Iniciando ciclo de reconexión...")

    # Iniciar hilo de reconexión
    reconnection_thread = Thread(target=handle_reconnection, daemon=True)
    reconnection_thread.start()

    # Registrar módulo públicamente (para acceso desde otros módulos Python)
    _data_feed_module = {
        'get_alert_history': get_alert_history,
        'get_connection_status': get_connection_status,
        'process_alert': process_alert,
        'subscribe_to_rooms': subscribe_to_rooms,
        'is_connected': lambda: connected,
        'status': 'initialized'
    }

    logger.info("Módulo de integración iniciado con éxito")
    return _data_feed_module

# Función para detener el módulo de integración
def stop_data_feed_integration():
    """Detiene el módulo de integración con el servidor de datos"""
    global socketio_client, connected

    logger.info("Deteniendo módulo de integración con el servidor de datos")

    if socketio_client:
        try:
            socketio_client.disconnect()
            socketio_client = None
        except Exception as e:
            logger.error(f"Error al desconectar: {e}")

    connected = False
    logger.info("Módulo de integración detenido")

# Función para probar la conexión (para uso en el frontend)
def test_connection():
    """Prueba la conexión al servidor de datos"""
    try:
        # Verificar si el servidor HTTP está respondiendo
        response = requests.get(f"{DATA_FEED_CONFIG['shadow_core_url']}/api/status", timeout=5)
        if response.status_code == 200:
            return {
                'status': 'success',
                'message': 'Servidor HTTP accesible',
                'data': response.json()
            }
        else:
            return {
                'status': 'error',
                'message': f'Servidor HTTP no respondió correctamente (código: {response.status_code})'
            }
    except requests.exceptions.RequestException as e:
        return {
            'status': 'error',
            'message': f'Error al conectar al servidor HTTP: {str(e)}'
        }

# Función para enviar una alerta de prueba
def send_test_alert():
    """Envía una alerta de prueba al servidor"""
    try:
        response = requests.post(
            f"{DATA_FEED_CONFIG['shadow_core_url']}/api/simulate",
            timeout=5
        )
        if response.status_code == 200:
            return {
                'status': 'success',
                'message': 'Alerta de prueba enviada',
                'data': response.json()
            }
        else:
            return {
                'status': 'error',
                'message': f'Servidor no respondió correctamente (código: {response.status_code})',
                'response': response.text
            }
    except requests.exceptions.RequestException as e:
        return {
            'status': 'error',
            'message': f'Error al enviar alerta de prueba: {str(e)}'
        }

# Función para controlar la simulación de alertas
def control_alert_simulation(action):
    """Controla la simulación de alertas en el servidor"""
    try:
        response = requests.post(
            f"{DATA_FEED_CONFIG['shadow_core_url']}/api/control",
            json={'action': action},
            timeout=5
        )
        if response.status_code == 200:
            return {
                'status': 'success',
                'message': response.json().get('message', 'Operación completada'),
                'data': response.json()
            }
        else:
            return {
                'status': 'error',
                'message': f'Servidor no respondió correctamente (código: {response.status_code})',
                'response': response.text
            }
    except requests.exceptions.RequestException as e:
        return {
            'status': 'error',
            'message': f'Error al controlar simulación: {str(e)}'
        }

# Función para inicializar el módulo (para uso en el frontend)
def init():
    """Inicializa el módulo de integración"""
    try:
        # Verificar si ya está inicializado
        if 'DataFeedIntegration' in window:
            logger.warning("Módulo de integración ya inicializado")
            return False

        # Iniciar el módulo
        start_data_feed_integration()

        # Exponer funciones para uso en el frontend
        window.DataFeedIntegration = {
            getAlertHistory: get_alert_history,
            getConnectionStatus: get_connection_status,
            processAlert: process_alert,
            subscribeToRooms: subscribe_to_rooms,
            isConnected: lambda: connected,
            testConnection: test_connection,
            sendTestAlert: send_test_alert,
            controlAlertSimulation: control_alert_simulation,
            config: DATA_FEED_CONFIG
        }

        logger.info("Módulo de integración inicializado en el frontend")
        return True
    except Exception as e:
        logger.error(f"Error al inicializar módulo de integración: {e}")
        return False