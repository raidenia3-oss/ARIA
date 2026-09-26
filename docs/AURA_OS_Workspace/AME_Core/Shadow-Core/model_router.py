#!/usr/bin/env python3
"""
Model Router para AURA.
Clasifica tareas según su tipo (CODE_TASK, RESEARCH_TASK, CREATIVE_TASK, GENERAL_TASK)
y asigna el modelo más adecuado según la configuración en config_models.json.
Soporta operaciones en modo offline usando solo modelos locales.
Integra el Shared Context Bus para compartir conocimiento entre agentes.
Añade soporte para WebSockets para notificaciones en tiempo real.
"""

import os
import subprocess
import time
import json
import threading
import socket
import re
import requests
from flask import Flask, request, jsonify
import uuid
from datetime import datetime
from flask_socketio import SocketIO, emit, join_room, leave_room
import eventlet
eventlet.monkey_patch()

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Configuración global
OLLAMA_HOST = "http://localhost:11434"
KNOWLEDGE_RAG_URL = "http://localhost:5012"
CONFIG_FILE = "config_models.json"
MODELS_CONFIG = {}
TASK_TYPES = {}
DEFAULT_TASK_TYPE = "GENERAL_TASK"
MODEL_FALLBACK = "llama3"
CONTEXT_BUS_URL = "http://localhost:5015"

# Estado de los modelos (carga, disponibilidad)
MODEL_STATUS = {}
OFFLINE_MODE = False

# Estado del enjambre para visualización
SWARM_STATUS = {
    "agents": {},
    "swarm_status": "inactive",
    "last_updated": None,
    "activity_log": []
}

# Configuración de agentes para visualización
AGENT_VISUALIZATION_CONFIG = {
    "coder": {
        "name": "Coder",
        "description": "Agente especializado en programación y generación de código.",
        "status": "inactive",
        "task": "",
        "model": "",
        "load": 0,
        "color": "#4CAF50",  # Verde (inactivo)
        "active_color": "#2196F3",  # Azul (activo)
        "orchestrating_color": "#FFC107",  # Amarillo (orquestando)
        "position": {"x": 100, "y": 100}
    },
    "researcher": {
        "name": "Researcher",
        "description": "Agente especializado en investigación y análisis profundo.",
        "status": "inactive",
        "task": "",
        "model": "",
        "load": 0,
        "color": "#4CAF50",  # Verde (inactivo)
        "active_color": "#2196F3",  # Azul (activo)
        "orchestrating_color": "#FFC107",  # Amarillo (orquestando)
        "position": {"x": 300, "y": 100}
    },
    "generalist": {
        "name": "Generalist",
        "description": "Agente generalista para consultas diversas.",
        "status": "inactive",
        "task": "",
        "model": "",
        "load": 0,
        "color": "#4CAF50",  # Verde (inactivo)
        "active_color": "#2196F3",  # Azul (activo)
        "orchestrating_color": "#FFC107",  # Amarillo (orquestando)
        "position": {"x": 200, "y": 250}
    }
}

# Configuración para notificaciones WebSocket
NOTIFICATION_CONFIG = {
    "notification_namespace": "/notifications",
    "task_completed_channel": "task_completed",
    "swarm_activity_channel": "swarm_activity",
    "agent_status_channel": "agent_status",
    "offline_mode_channel": "offline_mode"
}

# Estado de notificaciones
NOTIFICATION_STATE = {
    "connected_clients": 0,
    "last_notification_time": None,
    "notification_queue": []
}

def load_config():
    """Cargar la configuración de modelos desde el archivo JSON."""
    global MODELS_CONFIG, TASK_TYPES, DEFAULT_TASK_TYPE, MODEL_FALLBACK

    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)

        # Cargar tipos de tareas
        TASK_TYPES = config.get("task_types", {})

        # Cargar configuración de modelos
        MODELS_CONFIG = {
            "dolphin-llama3": {
                "name": "Dolphin-Llama3",
                "description": "Modelo especializado en análisis lógico, preguntas técnicas y respuestas precisas.",
                "capabilities": ["logic", "technical_questions", "precise_answers", "analysis"],
                "priority": 1,
                "backup": False,
                "knowledge_enhanced": True,
                "offline_capable": True,
                "task_type": None,
                "publishes_to_bus": True,
                "notifies_on_completion": True
            },
            "mistral-nemo-uncensored": {
                "name": "Mistral-Nemo (Uncensored)",
                "description": "Modelo especializado en investigación creativa, generación de ideas y contenido libre.",
                "capabilities": ["creative_research", "idea_generation", "uncensored_content", "brainstorming"],
                "priority": 2,
                "backup": True,
                "knowledge_enhanced": True,
                "offline_capable": True,
                "task_type": None,
                "publishes_to_bus": True,
                "notifies_on_completion": True
            },
            "deepseek-coder-v2": {
                "name": "DeepSeek-Coder",
                "description": "Modelo especializado en programación, depuración y generación de código.",
                "capabilities": ["coding", "debugging", "code_generation", "programming_questions"],
                "priority": 3,
                "backup": True,
                "knowledge_enhanced": True,
                "offline_capable": True,
                "task_type": None,
                "publishes_to_bus": True,
                "notifies_on_completion": True
            },
            "llama3": {
                "name": "Llama3",
                "description": "Modelo generalista para tareas diversas.",
                "capabilities": ["general", "default"],
                "priority": 4,
                "backup": True,
                "knowledge_enhanced": False,
                "offline_capable": True,
                "task_type": None,
                "publishes_to_bus": False,
                "notifies_on_completion": False
            }
        }

        # Asignar tipos de tareas a modelos según la configuración
        for task_type, task_config in config.get("task_types", {}).items():
            model_name = task_config.get("model")
            if model_name in MODELS_CONFIG:
                MODELS_CONFIG[model_name]["task_type"] = task_type

        DEFAULT_TASK_TYPE = config.get("default_task_type", "GENERAL_TASK")
        MODEL_FALLBACK = config.get("model_fallback", "llama3")

        # Inicializar estado de modelos
        for model_name in MODELS_CONFIG:
            MODEL_STATUS[model_name] = {
                "available": False,
                "load": 0,
                "last_used": None,
                "task_type": MODELS_CONFIG[model_name].get("task_type"),
                "notifies_on_completion": MODELS_CONFIG[model_name].get("notifies_on_completion", False)
            }

        print("✅ Configuración de modelos cargada correctamente")
        return True
    except Exception as e:
        print(f"❌ Error al cargar configuración de modelos: {e}")
        return False

def check_internet_connection():
    """Verificar si hay conexión a internet."""
    try:
        socket.create_connection(("8.8.8.8", 53))
        return True
    except Exception:
        return False

def set_offline_mode(mode):
    """Configurar el modo offline."""
    global OFFLINE_MODE
    OFFLINE_MODE = mode
    print(f"🌐 Modo {'offline' if mode else 'online'} activado")

    # Notificar a los clientes conectados
    socketio.emit('offline_mode_update', {
        "mode": mode,
        "timestamp": datetime.now().isoformat()
    }, namespace=NOTIFICATION_CONFIG.notification_namespace)

    # Notificar a través de WebSocket regular también
    socketio.emit('offline_mode_update', {
        "mode": mode,
        "timestamp": datetime.now().isoformat()
    })

def call_knowledge_rag(endpoint, data):
    """Llamar al Knowledge RAG para obtener conocimiento relevante."""
    try:
        if OFFLINE_MODE:
            print("⚠️ Modo offline: no se puede acceder a Knowledge RAG externo")
            return None

        response = requests.post(f"{KNOWLEDGE_RAG_URL}/{endpoint}", json=data, timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error al llamar a Knowledge RAG ({endpoint}): {response.text}")
            return None
    except Exception as e:
        print(f"Error al llamar a Knowledge RAG ({endpoint}): {e}")
        return None

def call_context_bus(endpoint, data=None):
    """Llamar al Shared Context Bus."""
    try:
        url = f"{CONTEXT_BUS_URL}/{endpoint}"
        if data:
            response = requests.post(url, json=data, timeout=5)
        else:
            response = requests.get(url, timeout=5)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error al llamar a Context Bus ({endpoint}): {response.text}")
            return None
    except Exception as e:
        print(f"Error al llamar a Context Bus ({endpoint}): {e}")
        return None

def publish_to_context_bus(context_item):
    """Publicar un elemento de contexto en el Shared Context Bus."""
    try:
        if OFFLINE_MODE:
            print("⚠️ Modo offline: no se puede publicar en el Context Bus externo")
            return None

        data = {
            "auth_key": "SECRET_AUTH_KEY_12345",
            "context": context_item
        }

        result = call_context_bus("api/context_bus/publish", data)
        if result and result.get("status") == "ok":
            return result.get("context_id")
        else:
            print(f"⚠️ No se pudo publicar en el Context Bus: {result.get('message', 'Error desconocido')}")
            return None
    except Exception as e:
        print(f"⚠️ Error al publicar en el Context Bus: {e}")
        return None

def initialize_models():
    """Inicializar los modelos disponibles en Ollama."""
    try:
        # Verificar conexión a internet
        internet_available = check_internet_connection()

        # Verificar modelos disponibles en Ollama
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5 if internet_available else 1)
        if response.status_code == 200:
            available_models = response.json().get("models", [])
            for model_name in MODELS_CONFIG:
                MODEL_STATUS[model_name]["available"] = model_name in available_models
                if MODEL_STATUS[model_name]["available"]:
                    print(f"✅ Modelo {model_name} disponible")
                else:
                    if internet_available:
                        print(f"⚠️ Modelo {model_name} no disponible (descargando si es necesario)...")
                        download_model(model_name)
                    else:
                        print(f"⚠️ Modelo {model_name} no disponible (modo offline)")
        else:
            print(f"⚠️ No se pudo verificar modelos disponibles: {response.text}")
    except Exception as e:
        print(f"Error al inicializar modelos: {e}")

def download_model(model_name):
    """Descargar un modelo específico de Ollama."""
    try:
        if OFFLINE_MODE:
            print(f"⚠️ Modo offline: no se pueden descargar modelos")
            return

        print(f"🔄 Descargando modelo {model_name}...")
        result = subprocess.run(
            ["ollama", "pull", model_name],
            capture_output=True,
            text=True,
            timeout=300  # Tiempo máximo de descarga
        )
        if result.returncode == 0:
            print(f"✅ Modelo {model_name} descargado correctamente")
            MODEL_STATUS[model_name]["available"] = True
        else:
            print(f"❌ Error al descargar modelo {model_name}: {result.stderr}")
            MODEL_STATUS[model_name]["available"] = False
    except Exception as e:
        print(f"Error al descargar modelo {model_name}: {e}")
        MODEL_STATUS[model_name]["available"] = False

def start_model(model_name):
    """Iniciar un modelo específico en Ollama."""
    try:
        print(f"🚀 Iniciando modelo {model_name}...")
        result = subprocess.run(
            ["ollama", "run", model_name],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"✅ Modelo {model_name} iniciado correctamente")
            MODEL_STATUS[model_name]["available"] = True
        else:
            print(f"❌ Error al iniciar modelo {model_name}: {result.stderr}")
            MODEL_STATUS[model_name]["available"] = False
    except Exception as e:
        print(f"Error al iniciar modelo {model_name}: {e}")
        MODEL_STATUS[model_name]["available"] = False

def check_model_load():
    """Verificar la carga de los modelos y ajustar según sea necesario."""
    def check_load_loop():
        while True:
            try:
                for model_name in MODELS_CONFIG:
                    if MODEL_STATUS[model_name]["available"]:
                        # Simular carga (en un entorno real, esto podría ser una métrica real)
                        if MODEL_STATUS[model_name]["last_used"]:
                            time_since_use = (datetime.now() - MODEL_STATUS[model_name]["last_used"]).total_seconds()
                            if time_since_use < 30:  # Si se usó hace menos de 30 segundos
                                MODEL_STATUS[model_name]["load"] = min(1.0, MODEL_STATUS[model_name]["load"] + 0.05)
                            else:
                                MODEL_STATUS[model_name]["load"] = max(0.0, MODEL_STATUS[model_name]["load"] - 0.02)

                        # Limitar la carga máxima
                        MODEL_STATUS[model_name]["load"] = min(1.0, MODEL_STATUS[model_name]["load"])

                        # Notificar actualización de carga (para visualización)
                        update_agent_status(model_name)

            except Exception as e:
                print(f"Error al verificar carga de modelos: {e}")

            time.sleep(5)

    # Iniciar el hilo para verificar carga
    threading.Thread(target=check_load_loop, daemon=True).start()

def enrich_prompt_with_knowledge(prompt, system_prompt=None, task_type=None):
    """Enriquecer un prompt con conocimiento relevante del Knowledge RAG."""
    if OFFLINE_MODE:
        print("⚠️ Modo offline: no se puede enriquecer prompt con conocimiento externo")
        return prompt, system_prompt

    # Solo enriquecer prompts para modelos que lo soportan
    selected_model = select_model(prompt, system_prompt)
    if not selected_model or not MODELS_CONFIG[selected_model].get("knowledge_enhanced", False):
        return prompt, system_prompt

    try:
        # Llamar al Knowledge RAG para enriquecer el prompt
        data = {
            "auth_key": "SECRET_AUTH_KEY_12345",
            "prompt": prompt,
            "system_prompt": system_prompt
        }

        result = call_knowledge_rag("api/knowledge/enhance", data)
        if result and result.get("status") == "ok":
            return result["enhanced_prompt"], system_prompt
        else:
            print(f"⚠️ No se pudo enriquecer el prompt con conocimiento: {result.get('message', 'Error desconocido')}")
            return prompt, system_prompt
    except Exception as e:
        print(f"⚠️ Error al enriquecer prompt: {e}")
        return prompt, system_prompt

def classify_task(task_description, system_prompt=None):
    """Clasificar una tarea según su descripción y system_prompt."""
    task_lower = task_description.lower()
    system_prompt_lower = system_prompt.lower() if system_prompt else ""

    # Verificar cada tipo de tarea
    for task_type, task_config in TASK_TYPES.items():
        # Verificar palabras clave en la descripción de la tarea
        for keyword in task_config.get("keywords", []):
            if keyword.lower() in task_lower or keyword.lower() in system_prompt_lower:
                return task_type

    # Si no se encontró un tipo específico, usar el tipo por defecto
    return DEFAULT_TASK_TYPE

def select_model_by_task_type(task_type):
    """Seleccionar el modelo según el tipo de tarea."""
    # Buscar modelo específico para el tipo de tarea
    for model_name, model_config in MODELS_CONFIG.items():
        if model_config.get("task_type") == task_type and MODEL_STATUS[model_name]["available"]:
            return model_name

    # Si no hay modelo específico disponible, usar el modelo de fallback
    if MODEL_FALLBACK in MODEL_STATUS and MODEL_STATUS[MODEL_FALLBACK]["available"]:
        return MODEL_FALLBACK

    # Si no hay modelos disponibles, intentar iniciar uno
    for model_name in MODELS_CONFIG:
        if not MODEL_STATUS[model_name]["available"] and MODELS_CONFIG[model_name].get("offline_capable", False):
            start_model(model_name)
            if MODEL_STATUS[model_name]["available"]:
                return model_name

    # Si no se puede iniciar ningún modelo, devolver None
    return None

def select_model(task_description, system_prompt=None):
    """Seleccionar el modelo más adecuado según la descripción de la tarea y el system_prompt."""
    task_type = classify_task(task_description, system_prompt)
    return select_model_by_task_type(task_type)

def create_context_item_from_response(prompt, response, model_name, task_type):
    """Crear un elemento de contexto a partir de una respuesta de modelo."""
    context_item = {
        "id": str(uuid.uuid4()),
        "agent_type": "model_router",
        "model": model_name,
        "type": task_type,
        "timestamp": datetime.now().isoformat(),
        "prompt": prompt,
        "response": response,
        "summary": f"Respuesta generada por {model_name} para {task_type}: {response[:100]}...",
        "format": "text"
    }

    # Intentar extraer un resumen más descriptivo
    if task_type == "CODE_TASK":
        context_item["summary"] = f"Implementación de código para {prompt[:50]}..."
    elif task_type == "RESEARCH_TASK":
        context_item["summary"] = f"Análisis sobre {prompt[:50]}..."
    elif task_type == "CREATIVE_TASK":
        context_item["summary"] = f"Ideas creativas sobre {prompt[:50]}..."

    return context_item

def update_agent_status(model_name=None, status=None, task=None, load=None):
    """Actualizar el estado de un agente para la visualización."""
    try:
        # Actualizar estado del modelo
        if model_name and status:
            MODEL_STATUS[model_name]["status"] = status
            MODEL_STATUS[model_name]["task"] = task or ""
            MODEL_STATUS[model_name]["load"] = load if load is not None else MODEL_STATUS[model_name].get("load", 0)

        # Determinar el estado del enjambre
        swarm_status = "inactive"
        active_agents = 0
        orchestrating_agents = 0

        for model, model_status in MODEL_STATUS.items():
            if model_status.get("status") == "orchestrating":
                orchestrating_agents += 1
            elif model_status.get("status") == "active":
                active_agents += 1

        if orchestrating_agents > 0:
            swarm_status = "orchestrating"
        elif active_agents > 0:
            swarm_status = "active"

        # Actualizar estado global del enjambre
        SWARM_STATUS["swarm_status"] = swarm_status
        SWARM_STATUS["last_updated"] = datetime.now().isoformat()

        # Notificar a los clientes conectados en el namespace de visualización
        socketio.emit('agent_status_update', {
            "agents": MODEL_STATUS,
            "swarm_status": swarm_status,
            "last_updated": SWARM_STATUS["last_updated"]
        }, namespace='/visualizer')

        # Notificar a los clientes conectados en el namespace de notificaciones
        socketio.emit('agent_status_update', {
            "agents": MODEL_STATUS,
            "swarm_status": swarm_status,
            "last_updated": SWARM_STATUS["last_updated"]
        }, namespace=NOTIFICATION_CONFIG.notification_namespace)

        # Notificar actividad específica
        if model_name and status:
            activity_message = {
                "timestamp": datetime.now().isoformat(),
                "agent": model_name,
                "action": f"Estado cambiado a {status}",
                "task": task or "",
                "status": status,
                "details": f"Modelo: {model_name}, Carga: {load:.2f}" if load else ""
            }

            # Añadir al log de actividad
            SWARM_STATUS["activity_log"].insert(0, activity_message)
            if len(SWARM_STATUS["activity_log"]) > 50:
                SWARM_STATUS["activity_log"] = SWARM_STATUS["activity_log"][:50]

            # Notificar a través de WebSocket
            socketio.emit('swarm_activity', {
                "activity": activity_message
            }, namespace='/visualizer')

            socketio.emit('swarm_activity', {
                "activity": activity_message
            }, namespace=NOTIFICATION_CONFIG.notification_namespace)

    except Exception as e:
        print(f"❌ Error al actualizar estado del agente: {e}")

def notify_task_completed(model_name, task_description, response, task_type):
    """Notificar que una tarea ha sido completada."""
    try:
        if not MODELS_CONFIG.get(model_name, {}).get("notifies_on_completion", False):
            return

        # Crear mensaje de notificación
        notification_message = {
            "type": "TASK_COMPLETED",
            "timestamp": datetime.now().isoformat(),
            "agent": model_name,
            "task": task_description[:100] + ("..." if len(task_description) > 100 else ""),
            "task_type": task_type,
            "response_summary": response[:150] + ("..." if len(response) > 150 else ""),
            "model": model_name,
            "status": "completed"
        }

        # Notificar a través de WebSocket
        socketio.emit('task_completed', notification_message, namespace=NOTIFICATION_CONFIG.notification_namespace)

        # También notificar a través del namespace regular para compatibilidad
        socketio.emit('task_completed', notification_message)

        print(f"🔔 Notificación de tarea completada enviada para {model_name}: {task_description[:50]}...")

    except Exception as e:
        print(f"❌ Error al notificar tarea completada: {e}")

def query_ollama(model_name, prompt, system_prompt=None, options=None):
    """Consultar Ollama con un modelo específico."""
    if not MODEL_STATUS[model_name]["available"]:
        return {"status": "error", "message": f"Modelo {model_name} no disponible"}

    try:
        # Actualizar el estado del modelo (marcar como activo)
        MODEL_STATUS[model_name]["status"] = "active"
        MODEL_STATUS[model_name]["task"] = prompt[:100] + "..."
        MODEL_STATUS[model_name]["last_used"] = datetime.now()
        MODEL_STATUS[model_name]["load"] = min(1.0, MODEL_STATUS[model_name]["load"] + 0.2)

        # Notificar actualización de estado
        update_agent_status(model_name, "active", prompt[:100] + "...", MODEL_STATUS[model_name]["load"])

        # Preparar los datos de la consulta
        data = {
            "model": model_name,
            "prompt": prompt,
            "stream": False
        }

        if system_prompt:
            data["system"] = system_prompt

        if options:
            data.update(options)

        # Enviar la consulta a Ollama
        response = requests.post(f"{OLLAMA_HOST}/api/generate", json=data, timeout=30)

        if response.status_code == 200:
            result_data = response.json().get("response", "")

            # Crear elemento de contexto si el modelo está configurado para publicar
            if MODELS_CONFIG[model_name].get("publishes_to_bus", False) and not OFFLINE_MODE:
                task_type = MODELS_CONFIG[model_name].get("task_type", "GENERAL_TASK")
                context_item = create_context_item_from_response(prompt, result_data, model_name, task_type)
                publish_to_context_bus(context_item)

            # Actualizar estado del modelo (marcar como inactivo después de la consulta)
            MODEL_STATUS[model_name]["status"] = "inactive"
            MODEL_STATUS[model_name]["task"] = ""
            MODEL_STATUS[model_name]["load"] = max(0.0, MODEL_STATUS[model_name]["load"] - 0.1)

            # Notificar finalización de la consulta
            update_agent_status(model_name, "inactive", "", MODEL_STATUS[model_name]["load"])

            # Notificar que la tarea ha sido completada
            notify_task_completed(model_name, prompt, result_data, task_type)

            return {
                "status": "ok",
                "model": model_name,
                "response": result_data,
                "model_load": MODEL_STATUS[model_name]["load"],
                "task_type": MODELS_CONFIG[model_name].get("task_type"),
                "knowledge_sources": []
            }
        else:
            # Actualizar estado del modelo (marcar como inactivo en caso de error)
            MODEL_STATUS[model_name]["status"] = "inactive"
            MODEL_STATUS[model_name]["task"] = ""
            MODEL_STATUS[model_name]["load"] = max(0.0, MODEL_STATUS[model_name]["load"] - 0.1)

            # Notificar error
            update_agent_status(model_name, "inactive", "", MODEL_STATUS[model_name]["load"])

            return {
                "status": "error",
                "message": f"Error al consultar modelo {model_name}: {response.text}",
                "model_load": MODEL_STATUS[model_name]["load"]
            }
    except Exception as e:
        # Actualizar estado del modelo (marcar como inactivo en caso de error)
        MODEL_STATUS[model_name]["status"] = "inactive"
        MODEL_STATUS[model_name]["task"] = ""
        MODEL_STATUS[model_name]["load"] = max(0.0, MODEL_STATUS[model_name]["load"] - 0.1)

        # Notificar error
        update_agent_status(model_name, "inactive", "", MODEL_STATUS[model_name]["load"])

        return {
            "status": "error",
            "message": f"Error al consultar modelo {model_name}: {str(e)}",
            "model_load": MODEL_STATUS[model_name]["load"]
        }

def query_with_fallback(task_description, system_prompt=None, options=None, max_attempts=3):
    """Consultar Ollama con estrategia de fallback si el modelo principal está ocupado."""
    # Clasificar la tarea y seleccionar el modelo adecuado
    task_type = classify_task(task_description, system_prompt)
    selected_model = select_model_by_task_type(task_type)

    if not selected_model:
        return {"status": "error", "message": "No hay modelos disponibles"}

    # Enriquecer el prompt con conocimiento relevante (solo si no estamos en modo offline)
    enriched_prompt, enriched_system_prompt = enrich_prompt_with_knowledge(task_description, system_prompt, task_type)

    attempts = 0
    last_error = None

    while attempts < max_attempts:
        attempts += 1
        result = query_ollama(selected_model, enriched_prompt, enriched_system_prompt, options)

        if result["status"] == "ok":
            # Si el modelo está configurado para usar conocimiento, añadir fuentes
            if MODELS_CONFIG[selected_model].get("knowledge_enhanced", False) and not OFFLINE_MODE:
                # Obtener fuentes de conocimiento
                knowledge_result = call_knowledge_rag("api/knowledge/query", {
                    "auth_key": "SECRET_AUTH_KEY_12345",
                    "query": task_description
                })
                sources = []
                if knowledge_result and knowledge_result.get("status") == "ok":
                    sources = [r["source"] for r in knowledge_result["results"] if r.get("content")]

                result["knowledge_sources"] = sources
            return result
        else:
            last_error = result["message"]
            print(f"⚠️ Intento {attempts} fallido con modelo {selected_model}: {last_error}")

            # Si el modelo está muy cargado, esperar antes de reintentar
            if MODEL_STATUS[selected_model]["load"] > 0.9:
                print(f"🔄 Esperando 2 segundos antes de reintentar con {selected_model}...")
                time.sleep(2)

            # Si es un modelo de respaldo, intentar con otro modelo
            if attempts < max_attempts - 1:
                print(f"🔄 Intentando con otro modelo...")
                selected_model = next(
                    (m for m in MODELS_CONFIG if MODEL_STATUS[m]["available"] and MODELS_CONFIG[m].get("offline_capable", False)),
                    selected_model
                )

    return {
        "status": "error",
        "message": f"Todos los intentos fallidos. Último error: {last_error}",
        "selected_model": selected_model,
        "task_type": task_type
    }

@app.route('/api/models', methods=['GET'])
def list_models():
    """Listar modelos disponibles y su estado."""
    return jsonify({
        "status": "ok",
        "models": MODELS_CONFIG,
        "status": MODEL_STATUS,
        "offline_mode": OFFLINE_MODE,
        "internet_available": check_internet_connection(),
        "task_types": TASK_TYPES,
        "default_task_type": DEFAULT_TASK_TYPE
    })

@app.route('/api/models/load', methods=['GET'])
def get_model_load():
    """Obtener el estado de carga de los modelos."""
    return jsonify({
        "status": "ok",
        "load": MODEL_STATUS,
        "offline_mode": OFFLINE_MODE
    })

@app.route('/api/models/query', methods=['POST'])
def query_model():
    """Consultar un modelo específico de Ollama."""
    data = request.get_json()
    if not data or 'prompt' not in data:
        return jsonify({"status": "error", "message": "Prompt requerido"}), 400

    prompt = data['prompt']
    model_name = data.get('model')
    system_prompt = data.get('system_prompt')
    options = data.get('options', {})

    if model_name and model_name not in MODELS_CONFIG:
        return jsonify({"status": "error", "message": f"Modelo {model_name} no soportado"}), 400

    if model_name and not MODELS_CONFIG[model_name].get("offline_capable", False) and OFFLINE_MODE:
        return jsonify({"status": "error", "message": f"Modelo {model_name} no compatible con modo offline"}), 400

    if model_name:
        # Si se especifica un modelo, no enriquecer con conocimiento a menos que esté configurado
        if MODELS_CONFIG.get(model_name, {}).get("knowledge_enhanced", False) and not OFFLINE_MODE:
            enriched_prompt, enriched_system_prompt = enrich_prompt_with_knowledge(prompt, system_prompt)
            result = query_ollama(model_name, enriched_prompt, enriched_system_prompt, options)
        else:
            result = query_ollama(model_name, prompt, system_prompt, options)
    else:
        result = query_with_fallback(prompt, system_prompt, options)

    return jsonify(result)

@app.route('/api/models/route', methods=['POST'])
def route_query():
    """Ruteo inteligente de consultas a modelos según la tarea."""
    data = request.get_json()
    if not data or 'prompt' not in data:
        return jsonify({"status": "error", "message": "Prompt requerido"}), 400

    prompt = data['prompt']
    system_prompt = data.get('system_prompt')
    options = data.get('options', {})

    result = query_with_fallback(prompt, system_prompt, options)
    return jsonify(result)

@app.route('/api/models/classify', methods=['POST'])
def classify_task_endpoint():
    """Clasificar una tarea según su descripción."""
    data = request.get_json()
    if not data or 'prompt' not in data:
        return jsonify({"status": "error", "message": "Prompt requerido"}), 400

    prompt = data['prompt']
    system_prompt = data.get('system_prompt')

    task_type = classify_task(prompt, system_prompt)
    selected_model = select_model_by_task_type(task_type)

    return jsonify({
        "status": "ok",
        "task_type": task_type,
        "selected_model": selected_model,
        "model_config": MODELS_CONFIG.get(selected_model, {}),
        "task_config": TASK_TYPES.get(task_type, {})
    })

@app.route('/api/models/offline', methods=['POST'])
def set_offline_mode_endpoint():
    """Activar o desactivar el modo offline."""
    data = request.get_json()
    if not data or 'auth_key' not in data or 'mode' not in data:
        return jsonify({"status": "error", "message": "Llave de autorización y modo requeridos"}), 400

    auth_key = data.get('auth_key')
    if auth_key != "SECRET_AUTH_KEY_12345":
        return jsonify({"status": "error", "message": "Llave de autorización inválida"}), 403

    mode = data.get('mode', False)
    set_offline_mode(mode)

    return jsonify({
        "status": "ok",
        "message": f"Modo offline {'activado' if mode else 'desactivado'}",
        "offline_mode": OFFLINE_MODE
    })

# Endpoint para simular notificaciones (para pruebas)
@app.route('/api/simulate-notification', methods=['POST'])
def simulate_notification():
    """Simular el envío de una notificación de tarea completada (para pruebas)."""
    data = request.get_json()
    if not data or 'type' not in data:
        return jsonify({"status": "error", "message": "Tipo de notificación requerido"}), 400

    # Validar el tipo de notificación
    if data['type'] != 'TASK_COMPLETED':
        return jsonify({"status": "error", "message": "Tipo de notificación no soportado"}), 400

    # Validar los datos de la notificación
    required_fields = ['agent', 'task', 'task_type', 'model', 'status']
    for field in required_fields:
        if field not in data:
            return jsonify({"status": "error", "message": f"Campo '{field}' requerido"}), 400

    # Añadir timestamp si no está presente
    if 'timestamp' not in data:
        data['timestamp'] = datetime.now().isoformat()

    # Notificar a través de WebSocket
    socketio.emit('task_completed', data, namespace=NOTIFICATION_CONFIG.notification_namespace)

    # También notificar a través del namespace regular para compatibilidad
    socketio.emit('task_completed', data)

    print(f"🔔 Notificación simulada enviada para {data.get('agent', 'desconocido')}: {data.get('task', '')[:50]}...")

    return jsonify({
        "status": "ok",
        "message": "Notificación simulada enviada correctamente",
        "data": data
    })

# Endpoint para simular actividad del enjambre (para pruebas)
@app.route('/api/simulate-swarm-activity', methods=['POST'])
def simulate_swarm_activity():
    """Simular el envío de una notificación de actividad del enjambre (para pruebas)."""
    data = request.get_json()
    if not data or 'activity' not in data:
        return jsonify({"status": "error", "message": "Actividad del enjambre requerida"}), 400

    # Validar los datos de la actividad
    required_fields = ['agent', 'action', 'task', 'status']
    activity = data['activity']
    for field in required_fields:
        if field not in activity:
            return jsonify({"status": "error", "message": f"Campo '{field}' requerido en la actividad"}), 400

    # Añadir timestamp si no está presente
    if 'timestamp' not in activity:
        activity['timestamp'] = datetime.now().isoformat()

    # Crear mensaje de notificación
    notification_message = {
        "type": "swarm_activity",
        "activity": activity
    }

    # Notificar a través de WebSocket
    socketio.emit('swarm_activity', notification_message, namespace=NOTIFICATION_CONFIG.notification_namespace)

    # También notificar a través del namespace regular para compatibilidad
    socketio.emit('swarm_activity', notification_message)

    print(f"🔔 Actividad del enjambre simulada enviada para {activity.get('agent', 'desconocido')}: {activity.get('action', '')}")

    return jsonify({
        "status": "ok",
        "message": "Actividad del enjambre simulada enviada correctamente",
        "data": notification_message
    })

def start_models_in_background():
    """Iniciar modelos en segundo plano."""
    for model_name in MODELS_CONFIG:
        if not MODEL_STATUS[model_name]["available"] and MODELS_CONFIG[model_name].get("offline_capable", False):
            threading.Thread(target=start_model, args=(model_name,), daemon=True).start()

# WebSocket para visualización del enjambre
@socketio.on('connect', namespace='/visualizer')
def handle_visualizer_connect():
    """Manejar conexión de un cliente al visualizador."""
    print(f"🔌 Cliente conectado al visualizador: {request.sid}")
    join_room('visualizer_room')

    # Enviar estado actual del enjambre
    emit('agent_status_update', {
        "agents": MODEL_STATUS,
        "swarm_status": SWARM_STATUS["swarm_status"],
        "last_updated": SWARM_STATUS["last_updated"]
    }, room=request.sid)

    # Enviar log de actividad
    emit('activity_log_update', SWARM_STATUS.get("activity_log", []), room=request.sid)

@socketio.on('disconnect', namespace='/visualizer')
def handle_visualizer_disconnect():
    """Manejar desconexión de un cliente del visualizador."""
    print(f"🔌 Cliente desconectado del visualizador: {request.sid}")
    leave_room('visualizer_room')

# WebSocket para notificaciones proactivas
@socketio.on('connect', namespace=NOTIFICATION_CONFIG.notification_namespace)
def handle_notification_connect():
    """Manejar conexión de un cliente a las notificaciones."""
    print(f"🔔 Cliente conectado a notificaciones: {request.sid}")
    join_room('notification_room')

    # Incrementar contador de clientes conectados
    NOTIFICATION_STATE["connected_clients"] += 1
    print(f"🔔 Clientes conectados a notificaciones: {NOTIFICATION_STATE['connected_clients']}")

    # Enviar estado actual del enjambre
    emit('agent_status_update', {
        "agents": MODEL_STATUS,
        "swarm_status": SWARM_STATUS["swarm_status"],
        "last_updated": SWARM_STATUS["last_updated"]
    }, room=request.sid)

    # Enviar log de actividad reciente
    recent_activity = SWARM_STATUS.get("activity_log", [])[:10]
    emit('activity_log_update', recent_activity, room=request.sid)

    # Procesar cola de notificaciones pendientes
    if NOTIFICATION_STATE["notification_queue"]:
        for notification in NOTIFICATION_STATE["notification_queue"]:
            emit(notification["type"], notification["data"], room=request.sid)
        NOTIFICATION_STATE["notification_queue"] = []

@socketio.on('disconnect', namespace=NOTIFICATION_CONFIG.notification_namespace)
def handle_notification_disconnect():
    """Manejar desconexión de un cliente de las notificaciones."""
    print(f"🔔 Cliente desconectado de notificaciones: {request.sid}")
    leave_room('notification_room')

    # Decrementar contador de clientes conectados
    NOTIFICATION_STATE["connected_clients"] = max(0, NOTIFICATION_STATE["connected_clients"] - 1)
    print(f"🔔 Clientes conectados a notificaciones: {NOTIFICATION_STATE['connected_clients']}")

@socketio.on('subscribe', namespace=NOTIFICATION_CONFIG.notification_namespace)
def handle_subscription(data):
    """Manejar suscripción a canales de notificación."""
    print(f"🔔 Cliente {request.sid} se suscribió a: {data.get('channel', 'desconocido')}")

    if data.get('channel') == 'task_completed':
        # El cliente está suscrito a notificaciones de tareas completadas
        print(f"🔔 Cliente {request.sid} suscrito a tareas completadas")

    # Enviar confirmación de suscripción
    emit('subscription_confirmation', {
        "status": "ok",
        "channel": data.get('channel'),
        "timestamp": datetime.now().isoformat()
    }, room=request.sid)

# Evento para notificar tareas completadas
@socketio.on('task_completed', namespace=NOTIFICATION_CONFIG.notification_namespace)
def handle_task_completed_notification(data):
    """Manejar notificación de tarea completada."""
    print(f"🔔 Notificación de tarea completada recibida: {data.get('agent', 'desconocido')}")

    # Enviar la notificación a todos los clientes suscritos
    socketio.emit('task_completed', data, namespace=NOTIFICATION_CONFIG.notification_namespace, room='notification_room')

    # También notificar a través del namespace regular para compatibilidad
    socketio.emit('task_completed', data)

# Evento para notificar actividad del enjambre
@socketio.on('swarm_activity', namespace=NOTIFICATION_CONFIG.notification_namespace)
def handle_swarm_activity_notification(data):
    """Manejar notificación de actividad del enjambre."""
    print(f"🔔 Notificación de actividad del enjambre recibida: {data.get('activity', {}).get('agent', 'desconocido')}")

    # Enviar la notificación a todos los clientes suscritos
    socketio.emit('swarm_activity', data, namespace=NOTIFICATION_CONFIG.notification_namespace, room='notification_room')

    # También enviar a través del namespace regular para compatibilidad
    socketio.emit('swarm_activity', data)

# Evento para notificar cambios en el estado del agente
@socketio.on('agent_status_update', namespace=NOTIFICATION_CONFIG.notification_namespace)
def handle_agent_status_update(data):
    """Manejar notificación de cambios en el estado del agente."""
    print(f"🔔 Notificación de estado del agente recibida: {data.get('agents', {}).get('researcher', {}).get('status', 'desconocido')}")

    # Enviar la notificación a todos los clientes suscritos
    socketio.emit('agent_status_update', data, namespace=NOTIFICATION_CONFIG.notification_namespace, room='notification_room')

    # También enviar a través del namespace regular para compatibilidad
    socketio.emit('agent_status_update', data)

if __name__ == "__main__":
    # Cargar configuración
    if not load_config():
        print("❌ No se pudo cargar la configuración de modelos. Usando configuración por defecto.")
        # Configuración por defecto si no se puede cargar el archivo
        TASK_TYPES = {
            "CODE_TASK": {"model": "deepseek-coder-v2"},
            "RESEARCH_TASK": {"model": "dolphin-llama3"},
            "CREATIVE_TASK": {"model": "mistral-nemo-uncensored"},
            "GENERAL_TASK": {"model": "llama3"}
        }
        DEFAULT_TASK_TYPE = "GENERAL_TASK"
        MODEL_FALLBACK = "llama3"

    # Inicializar modelos
    initialize_models()

    # Iniciar modelos en segundo plano
    start_models_in_background()

    # Verificar carga de modelos
    check_model_load()

    # Iniciar el servidor
    socketio.run(app, host='0.0.0.0', port=5011, debug=False)