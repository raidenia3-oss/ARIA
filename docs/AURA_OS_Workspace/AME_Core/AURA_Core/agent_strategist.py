#!/usr/bin/env python3
"""
Agent Strategist para AURA.
Decide qué agente debe manejar una tarea específica y coordina la comunicación entre agentes.
"""

import os
import json
import time
import uuid
import redis
from datetime import datetime
from flask import Flask, request, jsonify
import jsonpickle
import subprocess

app = Flask(__name__)

# Configuración global
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_PASSWORD = None
REDIS_DB = 0

# Inicializar Redis
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    db=REDIS_DB,
    decode_responses=True
)

# Agentes disponibles
AGENTS = {
    "analytic_agent": {
        "name": "Analytic Agent",
        "description": "Agente especializado en análisis de datos, preguntas complejas y procesamiento de información.",
        "capabilities": ["analyze", "question", "research", "data_processing"],
        "endpoint": "http://localhost:5003"
    },
    "executor_agent": {
        "name": "Executor Agent",
        "description": "Agente especializado en ejecución de tareas, automatización y control de sistemas.",
        "capabilities": ["execute", "automate", "control", "task_management"],
        "endpoint": "http://localhost:5002"
    },
    "vision_agent": {
        "name": "Vision Agent",
        "description": "Agente especializado en procesamiento de imágenes y análisis visual.",
        "capabilities": ["image_processing", "vision_analysis", "screen_capture", "visual_diagnosis"],
        "endpoint": "http://localhost:5009"
    },
    "memory_agent": {
        "name": "Memory Agent",
        "description": "Agente especializado en gestión de conocimiento y memoria a largo plazo.",
        "capabilities": ["memory", "knowledge", "retrieval", "storage"],
        "endpoint": "http://localhost:5007"
    }
}

# Base de datos de conocimiento compartido
KNOWLEDGE_DB = "knowledge_db.json"
os.makedirs("AURA_Core", exist_ok=True)

def load_knowledge_db():
    """Cargar la base de datos de conocimiento compartido."""
    if os.path.exists(KNOWLEDGE_DB):
        with open(KNOWLEDGE_DB, 'r') as f:
            return json.load(f)
    return {"entries": []}

def save_knowledge_db(knowledge_db):
    """Guardar la base de datos de conocimiento compartido."""
    with open(KNOWLEDGE_DB, 'w') as f:
        json.dump(knowledge_db, f, indent=2)

def add_to_knowledge_db(entry):
    """Añadir una entrada a la base de datos de conocimiento compartido."""
    knowledge_db = load_knowledge_db()
    entry["timestamp"] = datetime.now().isoformat()
    entry["id"] = str(uuid.uuid4())
    knowledge_db.setdefault("entries", []).append(entry)
    save_knowledge_db(knowledge_db)
    return entry["id"]

def get_from_knowledge_db(query):
    """Obtener entradas de la base de datos de conocimiento compartido."""
    knowledge_db = load_knowledge_db()
    results = []
    for entry in knowledge_db.get("entries", []):
        if query.lower() in entry.get("content", "").lower() or query.lower() in entry.get("tags", []):
            results.append(entry)
    return results

def determine_agent(task_description):
    """Determinar qué agente debe manejar una tarea específica."""
    task_lower = task_description.lower()

    # Analizar el tipo de tarea
    if any(keyword in task_lower for keyword in ["analizar", "pregunta", "investigar", "procesar datos", "explicar"]):
        return "analytic_agent"
    elif any(keyword in task_lower for keyword in ["ejecutar", "automatizar", "controlar", "tarea", "comando"]):
        return "executor_agent"
    elif any(keyword in task_lower for keyword in ["imagen", "pantalla", "gráfico", "terminal", "visual", "captura"]):
        return "vision_agent"
    elif any(keyword in task_lower for keyword in ["memoria", "conocimiento", "guardar", "recuperar", "aprender"]):
        return "memory_agent"
    else:
        # Si no está claro, usar el agente analítico por defecto
        return "analytic_agent"

def send_task_to_agent(agent_name, task_data):
    """Enviar una tarea a un agente específico."""
    agent = AGENTS.get(agent_name)
    if not agent:
        return {"status": "error", "message": f"Agente {agent_name} no encontrado"}

    try:
        # Usar Redis para enviar la tarea
        task_id = str(uuid.uuid4())
        task_data["task_id"] = task_id
        task_data["agent"] = agent_name
        task_data["timestamp"] = datetime.now().isoformat()

        # Guardar la tarea en Redis
        redis_client.publish(f"task_queue:{agent_name}", jsonpickle.encode(task_data))
        redis_client.hset(f"task:{task_id}", mapping={
            "status": "pending",
            "agent": agent_name,
            "timestamp": task_data["timestamp"]
        })

        return {"status": "ok", "task_id": task_id, "agent": agent_name}
    except Exception as e:
        return {"status": "error", "message": f"Error al enviar tarea a {agent_name}: {str(e)}"}

def get_task_result(task_id, timeout=30):
    """Obtener el resultado de una tarea usando su ID."""
    try:
        # Esperar a que la tarea se complete
        start_time = time.time()
        while time.time() - start_time < timeout:
            task_status = redis_client.hgetall(f"task:{task_id}")
            if task_status and task_status.get("status") != "pending":
                return {
                    "status": "ok",
                    "result": jsonpickle.decode(task_status.get("result", "{}")),
                    "task_id": task_id
                }
            time.sleep(1)

        return {"status": "error", "message": f"Tiempo de espera agotado para tarea {task_id}"}
    except Exception as e:
        return {"status": "error", "message": f"Error al obtener resultado de tarea: {str(e)}"}

def handle_task(task_description, context=None):
    """Manejar una tarea determinando qué agente debe procesarla."""
    try:
        # Determinar el agente adecuado
        agent_name = determine_agent(task_description)

        # Preparar los datos de la tarea
        task_data = {
            "description": task_description,
            "context": context or {},
            "timestamp": datetime.now().isoformat()
        }

        # Enviar la tarea al agente seleccionado
        response = send_task_to_agent(agent_name, task_data)
        if response["status"] != "ok":
            return response

        task_id = response["task_id"]

        # Esperar y obtener el resultado
        result = get_task_result(task_id)
        return result
    except Exception as e:
        return {"status": "error", "message": f"Error al manejar tarea: {str(e)}"}

def register_agent(agent_name, endpoint):
    """Registrar un nuevo agente en el sistema."""
    if agent_name in AGENTS:
        AGENTS[agent_name]["endpoint"] = endpoint
    else:
        AGENTS[agent_name] = {
            "name": agent_name.replace("_", " ").title(),
            "description": f"Agente {agent_name} no especificado",
            "capabilities": [],
            "endpoint": endpoint
        }
    return AGENTS[agent_name]

def list_agents():
    """Listar todos los agentes disponibles."""
    return list(AGENTS.keys())

@app.route('/api/agents', methods=['GET'])
def list_available_agents():
    """Endpoint para listar agentes disponibles."""
    return jsonify({"status": "ok", "agents": list_agents()})

@app.route('/api/agents/register', methods=['POST'])
def register_new_agent():
    """Endpoint para registrar un nuevo agente."""
    data = request.get_json()
    if not data or 'name' not in data or 'endpoint' not in data:
        return jsonify({"status": "error", "message": "Nombre y endpoint del agente requeridos"}), 400

    agent_name = data['name']
    endpoint = data['endpoint']
    agent = register_agent(agent_name, endpoint)
    return jsonify({"status": "ok", "agent": agent})

@app.route('/api/strategist/task', methods=['POST'])
def handle_task_endpoint():
    """Endpoint para manejar tareas usando el Agent Strategist."""
    data = request.get_json()
    if not data or 'description' not in data:
        return jsonify({"status": "error", "message": "Descripción de tarea requerida"}), 400

    task_description = data['description']
    context = data.get('context', {})

    result = handle_task(task_description, context)
    return jsonify(result)

@app.route('/api/strategist/task/<task_id>', methods=['GET'])
def get_task_result_endpoint(task_id):
    """Endpoint para obtener el resultado de una tarea."""
    result = get_task_result(task_id)
    return jsonify(result)

@app.route('/api/strategist/knowledge', methods=['POST'])
def add_knowledge_entry():
    """Endpoint para añadir una entrada a la base de datos de conocimiento compartido."""
    data = request.get_json()
    if not data or 'content' not in data:
        return jsonify({"status": "error", "message": "Contenido requerido"}), 400

    content = data['content']
    tags = data.get('tags', [])
    entry = {
        "content": content,
        "tags": tags,
        "source": data.get('source', 'unknown')
    }

    entry_id = add_to_knowledge_db(entry)
    return jsonify({"status": "ok", "entry_id": entry_id, "entry": entry})

@app.route('/api/strategist/knowledge/search', methods=['POST'])
def search_knowledge():
    """Endpoint para buscar en la base de datos de conocimiento compartido."""
    data = request.get_json()
    if not data or 'query' not in data:
        return jsonify({"status": "error", "message": "Consulta requerida"}), 400

    query = data['query']
    results = get_from_knowledge_db(query)
    return jsonify({"status": "ok", "results": results})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5010, debug=False)