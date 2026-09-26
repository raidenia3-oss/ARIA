#!/usr/bin/env python3
"""
Shared Context Bus para AURA.
Gestiona el intercambio de contexto entre agentes usando Redis como bus de mensajes.
Permite que los resultados de investigación sean compartidos automáticamente con otros agentes.
"""

import os
import json
import time
import uuid
import redis
from datetime import datetime
from flask import Flask, request, jsonify
import threading

app = Flask(__name__)

# Configuración global
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_PASSWORD = None
REDIS_DB = 1  # Usar una base de datos diferente para el Context Bus
CONTEXT_EXPIRATION_SECONDS = 86400  # 24 horas de expiración para el contexto
GLOBAL_KNOWLEDGE_FILE = "global_knowledge.md"

# Inicializar Redis
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    db=REDIS_DB,
    decode_responses=True
)

# Configuración de canales
CONTEXT_CHANNEL = "aura_context_bus"
AGENT_TYPES = {
    "research_agent": {
        "name": "Research Agent",
        "description": "Agente especializado en investigación y análisis profundo.",
        "produces": ["research_results", "analysis", "insights"],
        "consumes": ["general_queries", "technical_questions"]
    },
    "code_agent": {
        "name": "Code Agent",
        "description": "Agente especializado en programación y generación de código.",
        "produces": ["code_snippets", "scripts", "implementations"],
        "consumes": ["research_results", "requirements", "specifications"]
    },
    "creative_agent": {
        "name": "Creative Agent",
        "description": "Agente especializado en generación de ideas y contenido creativo.",
        "produces": ["ideas", "concepts", "brainstorming_results"],
        "consumes": ["general_queries", "creative_requests"]
    },
    "general_agent": {
        "name": "General Agent",
        "description": "Agente generalista para consultas diversas.",
        "produces": ["general_responses"],
        "consumes": ["general_queries"]
    }
}

# Estado del Context Bus
CONTEXT_BUS_STATUS = {
    "last_updated": None,
    "total_context_items": 0,
    "last_error": None
}

def initialize_global_knowledge_file():
    """Inicializar el archivo de conocimiento global si no existe."""
    if not os.path.exists(GLOBAL_KNOWLEDGE_FILE):
        with open(GLOBAL_KNOWLEDGE_FILE, 'w') as f:
            f.write("# 🌍 Conocimiento Global de AURA\n\n")
            f.write("Este archivo contiene un resumen de los conocimientos adquiridos por los agentes de AURA.\n")
            f.write("Cada vez que un agente aprende algo nuevo, se añade un resumen aquí para que el resto del sistema esté al tanto.\n\n")
            f.write("## 📅 Última actualización: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n\n")
            f.write("## 🔍 Índice\n")
            f.write("- [Investigaciones](#investigaciones)\n")
            f.write("- [Implementaciones](#implementaciones)\n")
            f.write("- [Ideas Creativas](#ideas-creativas)\n")
            f.write("- [Conocimiento General](#conocimiento-general)\n\n")
        print(f"✅ Creado archivo de conocimiento global: {GLOBAL_KNOWLEDGE_FILE}")
    else:
        print(f"✅ Archivo de conocimiento global ya existe: {GLOBAL_KNOWLEDGE_FILE}")

def update_global_knowledge_file(context_item):
    """Actualizar el archivo de conocimiento global con un nuevo elemento."""
    try:
        # Leer el archivo actual
        with open(GLOBAL_KNOWLEDGE_FILE, 'r') as f:
            content = f.read()

        # Generar el contenido del nuevo elemento
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        context_id = context_item.get("id", str(uuid.uuid4()))
        agent_type = context_item.get("agent_type", "desconocido")
        context_type = context_item.get("type", "conocimiento")

        # Determinar la sección adecuada
        section_mapping = {
            "research_results": "Investigaciones",
            "analysis": "Investigaciones",
            "insights": "Investigaciones",
            "code_snippets": "Implementaciones",
            "scripts": "Implementaciones",
            "implementations": "Implementaciones",
            "ideas": "Ideas Creativas",
            "concepts": "Ideas Creativas",
            "brainstorming_results": "Ideas Creativas",
            "general_responses": "Conocimiento General"
        }

        section_title = section_mapping.get(context_type, "Conocimiento General")
        section_header = f"## {section_title}\n"

        # Buscar la sección en el contenido
        if section_header in content:
            # Insertar el nuevo elemento antes del siguiente encabezado
            lines = content.split('\n')
            insert_pos = -1
            for i, line in enumerate(lines):
                if section_header in line:
                    insert_pos = i + 1
                    break

            if insert_pos > 0 and insert_pos < len(lines):
                # Insertar el nuevo elemento
                new_content = lines[:insert_pos] + [
                    "",
                    f"### {timestamp} - {agent_type} ({context_id})",
                    f"**Tipo:** {context_type}",
                    f"**Resumen:** {context_item.get('summary', 'Sin resumen')}",
                    f"**Detalles:** {context_item.get('content', 'Sin detalles')}",
                    "",
                    f"```{context_item.get('format', 'text')}",
                    context_item.get('content', ''),
                    "```",
                    ""
                ] + lines[insert_pos:]
                content = '\n'.join(new_content)
        else:
            # Si la sección no existe, añadirla al final
            content += f"\n{section_header}\n"
            content += f"### {timestamp} - {agent_type} ({context_id})\n"
            content += f"**Tipo:** {context_type}\n"
            content += f"**Resumen:** {context_item.get('summary', 'Sin resumen')}\n"
            content += f"**Detalles:** {context_item.get('content', 'Sin detalles')}\n"
            content += "\n```" + context_item.get('format', 'text') + "\n"
            content += context_item.get('content', '') + "\n"
            content += "```\n\n"

        # Actualizar la fecha de última actualización
        content = content.replace("## 📅 Última actualización:", f"## 📅 Última actualización: {timestamp}")

        # Guardar el contenido actualizado
        with open(GLOBAL_KNOWLEDGE_FILE, 'w') as f:
            f.write(content)

        print(f"✅ Actualizado conocimiento global con nuevo elemento ({context_id})")
        return True
    except Exception as e:
        print(f"❌ Error al actualizar conocimiento global: {e}")
        return False

def publish_context(context_item):
    """Publicar un elemento de contexto en el bus."""
    try:
        context_id = context_item.get("id", str(uuid.uuid4()))
        context_item["id"] = context_id
        context_item["timestamp"] = datetime.now().isoformat()
        context_item["ttl"] = CONTEXT_EXPIRATION_SECONDS

        # Guardar en Redis con expiración
        redis_client.hset(f"context:{context_id}", mapping=context_item)
        redis_client.expire(f"context:{context_id}", CONTEXT_EXPIRATION_SECONDS)

        # Publicar en el canal de contexto
        redis_client.publish(CONTEXT_CHANNEL, json.dumps({
            "action": "new_context",
            "context_id": context_id,
            "agent_type": context_item.get("agent_type"),
            "type": context_item.get("type"),
            "summary": context_item.get("summary", "")
        }))

        # Actualizar el archivo de conocimiento global
        update_global_knowledge_file(context_item)

        # Actualizar estado del Context Bus
        CONTEXT_BUS_STATUS["last_updated"] = datetime.now().isoformat()
        CONTEXT_BUS_STATUS["total_context_items"] = int(redis_client.dbsize())
        CONTEXT_BUS_STATUS["last_error"] = None

        print(f"📤 Publicado contexto {context_id} en el bus")
        return context_id
    except Exception as e:
        print(f"❌ Error al publicar contexto: {e}")
        CONTEXT_BUS_STATUS["last_error"] = str(e)
        return None

def get_context_by_id(context_id):
    """Obtener un elemento de contexto por su ID."""
    try:
        context_data = redis_client.hgetall(f"context:{context_id}")
        if context_data:
            return {
                "status": "ok",
                "context_id": context_id,
                "context": context_data
            }
        else:
            return {
                "status": "error",
                "message": "Contexto no encontrado"
            }
    except Exception as e:
        print(f"❌ Error al obtener contexto {context_id}: {e}")
        return {
            "status": "error",
            "message": f"Error al obtener contexto: {str(e)}"
        }

def get_context_by_type(context_type, limit=5):
    """Obtener elementos de contexto por su tipo."""
    try:
        context_items = []
        for key in redis_client.scan_iter(f"context:*"):
            context_data = redis_client.hgetall(key)
            if context_data.get("type") == context_type:
                context_items.append({
                    "context_id": key.decode().split(":")[1],
                    "agent_type": context_data.get("agent_type"),
                    "timestamp": context_data.get("timestamp"),
                    "summary": context_data.get("summary", ""),
                    "type": context_data.get("type")
                })

        return {
            "status": "ok",
            "type": context_type,
            "contexts": context_items[:limit]
        }
    except Exception as e:
        print(f"❌ Error al obtener contexto por tipo {context_type}: {e}")
        return {
            "status": "error",
            "message": f"Error al obtener contexto: {str(e)}"
        }

def get_context_by_agent(agent_type, limit=5):
    """Obtener elementos de contexto generados por un agente específico."""
    try:
        context_items = []
        for key in redis_client.scan_iter(f"context:*"):
            context_data = redis_client.hgetall(key)
            if context_data.get("agent_type") == agent_type:
                context_items.append({
                    "context_id": key.decode().split(":")[1],
                    "type": context_data.get("type"),
                    "timestamp": context_data.get("timestamp"),
                    "summary": context_data.get("summary", ""),
                    "agent_type": context_data.get("agent_type")
                })

        return {
            "status": "ok",
            "agent_type": agent_type,
            "contexts": context_items[:limit]
        }
    except Exception as e:
        print(f"❌ Error al obtener contexto por agente {agent_type}: {e}")
        return {
            "status": "error",
            "message": f"Error al obtener contexto: {str(e)}"
        }

def subscribe_to_context_bus(callback):
    """Suscribirse al canal de contexto para recibir notificaciones en tiempo real."""
    try:
        pubsub = redis_client.pubsub()
        pubsub.subscribe(CONTEXT_CHANNEL)

        def listener():
            for message in pubsub.listen():
                if message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        callback(data)
                    except Exception as e:
                        print(f"❌ Error al procesar mensaje del Context Bus: {e}")

        # Iniciar el hilo del listener
        threading.Thread(target=listener, daemon=True).start()
        print("✅ Suscripción al Context Bus activada")
    except Exception as e:
        print(f"❌ Error al suscribirse al Context Bus: {e}")

def get_context_status():
    """Obtener el estado actual del Context Bus."""
    return CONTEXT_BUS_STATUS

def initialize_context_bus():
    """Inicializar el Context Bus."""
    try:
        # Verificar conexión a Redis
        if not redis_client.ping():
            raise Exception("No se pudo conectar a Redis")

        # Inicializar el archivo de conocimiento global
        initialize_global_knowledge_file()

        # Limpiar contexto expirado (opcional, puede hacerse periódicamente)
        # redis_client.flushdb()  # Descomentar para limpiar la base de datos (¡cuidado!)

        print("✅ Context Bus inicializado correctamente")
        return True
    except Exception as e:
        print(f"❌ Error al inicializar Context Bus: {e}")
        CONTEXT_BUS_STATUS["last_error"] = str(e)
        return False

# Endpoints para gestionar el Context Bus
@app.route('/api/context_bus/publish', methods=['POST'])
def publish_context_endpoint():
    """Endpoint para publicar un elemento de contexto."""
    data = request.get_json()
    if not data or 'auth_key' not in data or 'context' not in data:
        return jsonify({"status": "error", "message": "Llave de autorización y contexto requeridos"}), 400

    auth_key = data.get('auth_key')
    if auth_key != "SECRET_AUTH_KEY_12345":
        return jsonify({"status": "error", "message": "Llave de autorización inválida"}), 403

    context_item = data['context']
    context_id = publish_context(context_item)

    if context_id:
        return jsonify({
            "status": "ok",
            "message": "Contexto publicado correctamente",
            "context_id": context_id
        })
    else:
        return jsonify({
            "status": "error",
            "message": "Error al publicar contexto",
            "error": CONTEXT_BUS_STATUS.get("last_error", "Error desconocido")
        })

@app.route('/api/context_bus/get/<context_id>', methods=['GET'])
def get_context_endpoint(context_id):
    """Endpoint para obtener un elemento de contexto por su ID."""
    result = get_context_by_id(context_id)
    return jsonify(result)

@app.route('/api/context_bus/get/type/<context_type>', methods=['GET'])
def get_context_by_type_endpoint(context_type):
    """Endpoint para obtener elementos de contexto por su tipo."""
    limit = request.args.get('limit', 5, type=int)
    result = get_context_by_type(context_type, limit)
    return jsonify(result)

@app.route('/api/context_bus/get/agent/<agent_type>', methods=['GET'])
def get_context_by_agent_endpoint(agent_type):
    """Endpoint para obtener elementos de contexto por agente."""
    limit = request.args.get('limit', 5, type=int)
    result = get_context_by_agent(agent_type, limit)
    return jsonify(result)

@app.route('/api/context_bus/status', methods=['GET'])
def get_context_bus_status_endpoint():
    """Endpoint para obtener el estado del Context Bus."""
    return jsonify(get_context_status())

@app.route('/api/context_bus/global_knowledge', methods=['GET'])
def get_global_knowledge_endpoint():
    """Endpoint para obtener el conocimiento global."""
    try:
        if os.path.exists(GLOBAL_KNOWLEDGE_FILE):
            with open(GLOBAL_KNOWLEDGE_FILE, 'r') as f:
                content = f.read()
            return jsonify({
                "status": "ok",
                "file": GLOBAL_KNOWLEDGE_FILE,
                "content": content,
                "last_modified": datetime.fromtimestamp(os.path.getmtime(GLOBAL_KNOWLEDGE_FILE)).isoformat()
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Archivo de conocimiento global no encontrado"
            })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error al leer conocimiento global: {str(e)}"
        })

def context_bus_listener():
    """Listener para el Context Bus que actualiza el conocimiento global."""
    def handle_new_context(data):
        if data.get("action") == "new_context":
            context_id = data.get("context_id")
            if context_id:
                # Obtener el contexto completo
                context_item = get_context_by_id(context_id)
                if context_item.get("status") == "ok":
                    update_global_knowledge_file(context_item.get("context"))

    # Suscribirse al canal de contexto
    subscribe_to_context_bus(handle_new_context)

if __name__ == "__main__":
    # Inicializar el Context Bus
    if not initialize_context_bus():
        print("⚠️ No se pudo inicializar el Context Bus. Continuando sin funcionalidad completa...")

    # Iniciar el listener para actualizar el conocimiento global
    context_bus_listener()

    # Iniciar el servidor
    app.run(host='0.0.0.0', port=5015, debug=False)