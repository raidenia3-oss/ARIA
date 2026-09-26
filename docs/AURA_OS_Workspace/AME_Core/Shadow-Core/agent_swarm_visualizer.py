#!/usr/bin/env python3
"""
Agent Swarm Visualizer para AURA.
Proporciona una visualización en tiempo real del estado de los agentes del enjambre.
Incluye nodos visuales, feed de actividad y conexión mediante WebSockets.
"""

import os
import json
import time
import uuid
import asyncio
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import eventlet
eventlet.monkey_patch()

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Configuración global
AGENT_CONFIG = {
    "coder": {
        "name": "Coder",
        "description": "Agente especializado en programación y generación de código.",
        "color": "#4CAF50",  # Verde (inactivo)
        "active_color": "#2196F3",  # Azul (activo)
        "orchestrating_color": "#FFC107",  # Amarillo (orquestando)
        "position": {"x": 100, "y": 100}
    },
    "researcher": {
        "name": "Researcher",
        "description": "Agente especializado en investigación y análisis profundo.",
        "color": "#4CAF50",  # Verde (inactivo)
        "active_color": "#2196F3",  # Azul (activo)
        "orchestrating_color": "#FFC107",  # Amarillo (orquestando)
        "position": {"x": 300, "y": 100}
    },
    "generalist": {
        "name": "Generalist",
        "description": "Agente generalista para consultas diversas.",
        "color": "#4CAF50",  # Verde (inactivo)
        "active_color": "#2196F3",  # Azul (activo)
        "orchestrating_color": "#FFC107",  # Amarillo (orquestando)
        "position": {"x": 200, "y": 250}
    }
}

# Estado del enjambre
SWARM_VISUALIZER_STATUS = {
    "last_updated": None,
    "agents": {},
    "activity_log": [],
    "swarm_status": "inactive",
    "last_error": None
}

# Conexión con el Model Router
MODEL_ROUTER_URL = "http://localhost:5011"
MODEL_ROUTER_WS_URL = "ws://localhost:5011/ws"
AUTH_KEY = "SECRET_AUTH_KEY_12345"

# Estado de conexión WebSocket
ws_connection = None

async def connect_to_model_router():
    """Conectar al Model Router mediante WebSocket para recibir actualizaciones en tiempo real."""
    global ws_connection
    try:
        print("🔗 Intentando conectar al Model Router mediante WebSocket...")

        async def ws_listener():
            global ws_connection
            while True:
                try:
                    if ws_connection and ws_connection.connected:
                        # Enviar mensaje de suscripción
                        await ws_connection.send(json.dumps({
                            "action": "subscribe",
                            "auth_key": AUTH_KEY,
                            "channel": "agent_status"
                        }))

                        # Esperar mensajes del servidor
                        message = await ws_connection.recv()
                        if message:
                            try:
                                data = json.loads(message)
                                if data.get("action") == "agent_status":
                                    update_agent_status(data)
                                elif data.get("action") == "swarm_activity":
                                    add_activity_log(data)
                            except json.JSONDecodeError:
                                print(f"⚠️ Mensaje no válido del Model Router: {message}")
                    else:
                        await asyncio.sleep(1)
                except Exception as e:
                    print(f"⚠️ Error en la conexión WebSocket con Model Router: {e}")
                    await asyncio.sleep(5)

        # Intentar conectar al WebSocket del Model Router
        ws_connection = await asyncio.open_connection(MODEL_ROUTER_WS_URL)
        print("✅ Conectado al Model Router mediante WebSocket")

        # Iniciar el listener en un hilo separado
        asyncio.create_task(ws_listener())

        return True
    except Exception as e:
        print(f"❌ Error al conectar al Model Router: {e}")
        return False

def update_agent_status(data):
    """Actualizar el estado de los agentes basado en los datos del Model Router."""
    try:
        if not data or "agents" not in data:
            return

        agents_data = data["agents"]
        current_time = datetime.now().isoformat()

        # Actualizar estado de cada agente
        for agent_id, agent_data in agents_data.items():
            agent_name = agent_id
            if agent_name in AGENT_CONFIG:
                status = agent_data.get("status", "inactive")
                task = agent_data.get("task", "")
                model = agent_data.get("model", "")
                load = agent_data.get("load", 0)

                # Determinar el color según el estado
                if status == "orchestrating":
                    color = AGENT_CONFIG[agent_name]["orchestrating_color"]
                elif status == "active":
                    color = AGENT_CONFIG[agent_name]["active_color"]
                else:
                    color = AGENT_CONFIG[agent_name]["color"]

                # Actualizar el estado del agente
                SWARM_VISUALIZER_STATUS["agents"][agent_name] = {
                    "status": status,
                    "task": task,
                    "model": model,
                    "load": load,
                    "color": color,
                    "last_updated": current_time
                }

                # Actualizar el estado general del enjambre
                if status == "orchestrating":
                    SWARM_VISUALIZER_STATUS["swarm_status"] = "orchestrating"
                elif status == "active":
                    SWARM_VISUALIZER_STATUS["swarm_status"] = "active"
                else:
                    # Verificar si todos los agentes están inactivos
                    all_inactive = True
                    for agent_name, agent_state in SWARM_VISUALIZER_STATUS["agents"].items():
                        if agent_state.get("status") != "inactive":
                            all_inactive = False
                            break

                    if all_inactive:
                        SWARM_VISUALIZER_STATUS["swarm_status"] = "inactive"

        # Actualizar timestamp
        SWARM_VISUALIZER_STATUS["last_updated"] = current_time
        SWARM_VISUALIZER_STATUS["last_error"] = None

        # Notificar a los clientes conectados
        socketio.emit('agent_status_update', SWARM_VISUALIZER_STATUS, namespace='/visualizer')

    except Exception as e:
        print(f"❌ Error al actualizar estado de agentes: {e}")
        SWARM_VISUALIZER_STATUS["last_error"] = str(e)

def add_activity_log(data):
    """Añadir un registro de actividad al log."""
    try:
        if not data or "activity" not in data:
            return

        activity_data = data["activity"]
        timestamp = datetime.now().isoformat()

        log_entry = {
            "timestamp": timestamp,
            "agent": activity_data.get("agent", "desconocido"),
            "action": activity_data.get("action", "actividad"),
            "task": activity_data.get("task", ""),
            "status": activity_data.get("status", "info"),
            "details": activity_data.get("details", "")
        }

        # Añadir al log (limitar a 50 entradas)
        SWARM_VISUALIZER_STATUS["activity_log"].insert(0, log_entry)
        if len(SWARM_VISUALIZER_STATUS["activity_log"]) > 50:
            SWARM_VISUALIZER_STATUS["activity_log"] = SWARM_VISUALIZER_STATUS["activity_log"][:50]

        # Notificar a los clientes conectados
        socketio.emit('activity_log_update', log_entry, namespace='/visualizer')

    except Exception as e:
        print(f"❌ Error al añadir actividad al log: {e}")
        SWARM_VISUALIZER_STATUS["last_error"] = str(e)

def initialize_visualizer():
    """Inicializar el visualizador del enjambre."""
    try:
        print("✅ Agent Swarm Visualizer inicializado correctamente")

        # Inicializar estado de los agentes
        for agent_name in AGENT_CONFIG:
            SWARM_VISUALIZER_STATUS["agents"][agent_name] = {
                "status": "inactive",
                "task": "",
                "model": "",
                "load": 0,
                "color": AGENT_CONFIG[agent_name]["color"],
                "last_updated": datetime.now().isoformat()
            }

        SWARM_VISUALIZER_STATUS["swarm_status"] = "inactive"
        SWARM_VISUALIZER_STATUS["last_updated"] = datetime.now().isoformat()
        SWARM_VISUALIZER_STATUS["last_error"] = None

        # Conectar al Model Router
        asyncio.create_task(connect_to_model_router())

        return True
    except Exception as e:
        print(f"❌ Error al inicializar Agent Swarm Visualizer: {e}")
        SWARM_VISUALIZER_STATUS["last_error"] = str(e)
        return False

# Rutas para el visualizador
@app.route('/')
def index():
    """Página principal del visualizador."""
    return render_template('agent_swarm_visualizer.html', agents=AGENT_CONFIG)

@app.route('/api/visualizer/status')
def get_visualizer_status():
    """Endpoint para obtener el estado actual del visualizador."""
    return jsonify(SWARM_VISUALIZER_STATUS)

# Eventos Socket.IO
@socketio.on('connect', namespace='/visualizer')
def handle_connect():
    """Manejar conexión de un cliente."""
    print(f"🔌 Cliente conectado: {request.sid}")
    emit('agent_status_update', SWARM_VISUALIZER_STATUS)
    emit('activity_log_update', SWARM_VISUALIZER_STATUS.get("activity_log", []))

@socketio.on('disconnect', namespace='/visualizer')
def handle_disconnect():
    """Manejar desconexión de un cliente."""
    print(f"🔌 Cliente desconectado: {request.sid}")

# Plantilla HTML para el visualizador
@app.route('/templates/agent_swarm_visualizer.html')
def template():
    return render_template('agent_swarm_visualizer.html')

if __name__ == "__main__":
    # Inicializar el visualizador
    if not initialize_visualizer():
        print("⚠️ No se pudo inicializar el Agent Swarm Visualizer. Continuando sin funcionalidad completa...")

    # Iniciar el servidor
    socketio.run(app, host='0.0.0.0', port=5017, debug=False)