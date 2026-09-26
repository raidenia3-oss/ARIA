#!/usr/bin/env python3
"""
LLM Analyzer para AURA.
Analiza consultas usando el Model Router para seleccionar el modelo más adecuado
según el tipo de tarea (CODE_TASK, RESEARCH_TASK, CREATIVE_TASK, GENERAL_TASK).
Integra el Shared Context Bus y el Parallel Agent Swarm para tareas complejas.
"""

import os
import json
import requests
from flask import Flask, request, jsonify
import time

app = Flask(__name__)

# Configuración global
MODEL_ROUTER_URL = "http://localhost:5011"
KNOWLEDGE_RAG_URL = "http://localhost:5012"
CONTEXT_BUS_URL = "http://localhost:5015"
SWARM_ORCHESTRATOR_URL = "http://localhost:5016"
AUTH_KEY = "SECRET_AUTH_KEY_12345"

def call_model_router(endpoint, data=None):
    """Llamar al Model Router para obtener una respuesta."""
    try:
        url = f"{MODEL_ROUTER_URL}/{endpoint}"
        if data:
            response = requests.post(url, json=data, timeout=10)
        else:
            response = requests.get(url, timeout=10)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error al llamar a Model Router ({endpoint}): {response.text}")
            return None
    except Exception as e:
        print(f"Error al llamar a Model Router ({endpoint}): {e}")
        return None

def call_context_bus(endpoint, data=None):
    """Llamar al Shared Context Bus para obtener contexto relevante."""
    try:
        url = f"{CONTEXT_BUS_URL}/{endpoint}"
        if data:
            response = requests.post(url, json=data, timeout=10)
        else:
            response = requests.get(url, timeout=10)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error al llamar a Context Bus ({endpoint}): {response.text}")
            return None
    except Exception as e:
        print(f"Error al llamar a Context Bus ({endpoint}): {e}")
        return None

def call_swarm_orchestrator(endpoint, data=None):
    """Llamar al Swarm Orchestrator para tareas complejas."""
    try:
        url = f"{SWARM_ORCHESTRATOR_URL}/{endpoint}"
        if data:
            response = requests.post(url, json=data, timeout=30)  # Tiempo más largo para tareas complejas
        else:
            response = requests.get(url, timeout=10)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error al llamar a Swarm Orchestrator ({endpoint}): {response.text}")
            return None
    except Exception as e:
        print(f"Error al llamar a Swarm Orchestrator ({endpoint}): {e}")
        return None

def is_complex_task(prompt, system_prompt=None):
    """Determinar si una tarea es lo suficientemente compleja para ser procesada por el enjambre."""
    try:
        prompt_lower = prompt.lower()
        system_prompt_lower = system_prompt.lower() if system_prompt else ""

        # Palabras clave que indican una tarea compleja
        complex_keywords = [
            "implementar", "desarrollar", "diseñar", "crear", "construir",
            "optimizar", "mejores prácticas", "comparar", "analizar en profundidad",
            "investigar a fondo", "estrategia", "roadmap", "hoja de ruta",
            "sistema completo", "arquitectura", "patrones de diseño",
            "librerías y frameworks", "herramientas y tecnologías",
            "casos de uso", "beneficios y limitaciones", "recomendaciones prácticas",
            "solución integral", "enfoque multidisciplinario", "desafíos y soluciones",
            "evaluación crítica", "análisis comparativo", "implicaciones",
            "impacto", "consideraciones", "mejoras", "innovaciones",
            "proceso completo", "etapas", "pasos", "metodología",
            "desde cero", "paso a paso", "guía completa", "tutorial detallado",
            "explicación técnica", "detalles técnicos", "implementación técnica",
            "configuración", "despliegue", "monitoreo", "mantenimiento",
            "escalabilidad", "rendimiento", "seguridad", "privacidad",
            "desafíos comunes", "soluciones comunes", "errores comunes",
            "mejores soluciones", "alternativas", "tradeoffs", "ventajas y desventajas"
        ]

        # Contar cuántas palabras clave complejas hay en el prompt
        complex_count = sum(1 for keyword in complex_keywords if keyword in prompt_lower or keyword in system_prompt_lower)

        # Si hay muchas palabras clave complejas, es probable que sea una tarea compleja
        if complex_count >= 3:
            return True

        # También considerar la longitud del prompt
        if len(prompt) > 200 or (system_prompt and len(system_prompt) > 150):
            return True

        # Si el prompt contiene múltiples aspectos que requieren diferentes especializaciones
        if any(keyword in prompt_lower for keyword in [
            "y", "así como", "además", "también", "incluyendo", "así como también",
            "por un lado... por otro lado", "por una parte... por otra parte"
        ]):
            return True

        return False
    except Exception as e:
        print(f"Error al determinar si es una tarea compleja: {e}")
        return False

def get_relevant_context(prompt, task_type, limit=3):
    """Obtener contexto relevante del Shared Context Bus."""
    try:
        # Obtener contexto por tipo de tarea
        context_result = call_context_bus(f"api/context_bus/get/type/{task_type}", {"limit": limit})
        if context_result and context_result.get("status") == "ok":
            return context_result.get("contexts", [])

        # Si no hay contexto específico, obtener contexto general
        general_result = call_context_bus(f"api/context_bus/get/type/GENERAL_TASK", {"limit": limit})
        if general_result and general_result.get("status") == "ok":
            return general_result.get("contexts", [])

        return []
    except Exception as e:
        print(f"Error al obtener contexto relevante: {e}")
        return []

def enrich_prompt_with_context(prompt, system_prompt=None, task_type=None):
    """Enriquecer un prompt con contexto relevante del Shared Context Bus."""
    try:
        # Obtener contexto relevante
        relevant_context = get_relevant_context(prompt, task_type or "GENERAL_TASK")

        if relevant_context:
            # Construir contexto para el prompt
            context_lines = []
            for context_item in relevant_context:
                if context_item.get("summary"):
                    context_lines.append(f"📌 Contexto relevante de {context_item.get('agent_type')}:")
                    context_lines.append(f"   **Resumen:** {context_item['summary']}")
                    context_lines.append(f"   **Fuente:** {context_item.get('context_id', 'desconocido')}")
                    context_lines.append("")

            context = "\n".join(context_lines)

            # Crear prompt mejorado
            enhanced_prompt = f"""
            {system_prompt or ""}

            🔍 CONTEXTO RELEVANTE DEL SISTEMA:
            {context}

            📝 PREGUNTA:
            {prompt}
            """

            return enhanced_prompt
        else:
            return prompt
    except Exception as e:
        print(f"Error al enriquecer prompt con contexto: {e}")
        return prompt

def analyze_with_model_router(prompt, system_prompt=None, options=None):
    """Analizar una consulta usando el Model Router."""
    try:
        # Verificar si es una tarea compleja que debe ser procesada por el enjambre
        if is_complex_task(prompt, system_prompt):
            print("🧬 Detección de tarea compleja: redirigiendo al Swarm Orchestrator")

            # Redirigir al Swarm Orchestrator
            result = call_swarm_orchestrator("api/swarm/execute", {
                "auth_key": AUTH_KEY,
                "prompt": prompt,
                "system_prompt": system_prompt
            })

            if result and result.get("status") == "ok":
                return {
                    "status": "ok",
                    "swarm_result": True,
                    "model": "swarm_orchestrator",
                    "response": result.get("synthesis"),
                    "task_type": "swarm_results",
                    "model_load": 0,
                    "knowledge_sources": [],
                    "context_sources": [],
                    "swarm_details": {
                        "original_results": result.get("original_results", []),
                        "failed_results": result.get("failed_results", []),
                        "context_id": result.get("context_id")
                    }
                }
            else:
                return {
                    "status": "error",
                    "message": result.get("message", "Error en el Swarm Orchestrator"),
                    "swarm_error": True
                }
        else:
            # Clasificar la tarea para obtener el tipo
            classify_result = call_model_router("api/models/classify", {
                "auth_key": AUTH_KEY,
                "prompt": prompt,
                "system_prompt": system_prompt
            })

            if classify_result and classify_result.get("status") == "ok":
                task_type = classify_result.get("task_type")
                selected_model = classify_result.get("selected_model")

                # Enriquecer el prompt con contexto relevante
                enriched_prompt = enrich_prompt_with_context(prompt, system_prompt, task_type)

                # Analizar con el Model Router
                data = {
                    "auth_key": AUTH_KEY,
                    "prompt": enriched_prompt
                }
                if system_prompt:
                    data["system_prompt"] = system_prompt
                if options:
                    data["options"] = options

                result = call_model_router("api/models/route", data)
                if result and result.get("status") == "ok":
                    return {
                        "status": "ok",
                        "model": result.get("model"),
                        "response": result.get("response"),
                        "task_type": task_type,
                        "model_load": result.get("model_load"),
                        "knowledge_sources": result.get("knowledge_sources", []),
                        "context_sources": relevant_context  # Añadir fuentes de contexto
                    }
                else:
                    return {
                        "status": "error",
                        "message": result.get("message", "Error desconocido"),
                        "selected_model": result.get("selected_model")
                    }
            else:
                return {
                    "status": "error",
                    "message": classify_result.get("message", "Error al clasificar tarea")
                }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error al analizar con Model Router: {str(e)}"
        }

def classify_task(prompt, system_prompt=None):
    """Clasificar una tarea usando el Model Router."""
    try:
        data = {
            "auth_key": AUTH_KEY,
            "prompt": prompt
        }
        if system_prompt:
            data["system_prompt"] = system_prompt

        result = call_model_router("api/models/classify", data)
        if result and result.get("status") == "ok":
            return {
                "status": "ok",
                "task_type": result.get("task_type"),
                "selected_model": result.get("selected_model"),
                "model_config": result.get("model_config"),
                "task_config": result.get("task_config")
            }
        else:
            return {
                "status": "error",
                "message": result.get("message", "Error desconocido")
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error al clasificar tarea: {str(e)}"
        }

@app.route('/api/llm/analyze', methods=['POST'])
def analyze_endpoint():
    """Endpoint para analizar una consulta."""
    data = request.get_json()
    if not data or 'auth_key' not in data or 'prompt' not in data:
        return jsonify({"status": "error", "message": "Llave de autorización y prompt requeridos"}), 400

    auth_key = data.get('auth_key')
    if auth_key != AUTH_KEY:
        return jsonify({"status": "error", "message": "Llave de autorización inválida"}), 403

    prompt = data['prompt']
    system_prompt = data.get('system_prompt')
    options = data.get('options', {})

    result = analyze_with_model_router(prompt, system_prompt, options)
    return jsonify(result)

@app.route('/api/llm/classify', methods=['POST'])
def classify_endpoint():
    """Endpoint para clasificar una tarea."""
    data = request.get_json()
    if not data or 'auth_key' not in data or 'prompt' not in data:
        return jsonify({"status": "error", "message": "Llave de autorización y prompt requeridos"}), 400

    auth_key = data.get('auth_key')
    if auth_key != AUTH_KEY:
        return jsonify({"status": "error", "message": "Llave de autorización inválida"}), 403

    prompt = data['prompt']
    system_prompt = data.get('system_prompt')

    result = classify_task(prompt, system_prompt)
    return jsonify(result)

@app.route('/api/llm/status', methods=['GET'])
def status_endpoint():
    """Endpoint para obtener el estado del LLM Analyzer."""
    try:
        # Verificar estado del Model Router
        model_router_status = call_model_router("api/models")
        if not model_router_status or model_router_status.get("status") != "ok":
            return jsonify({
                "status": "error",
                "message": "No se pudo obtener estado del Model Router"
            }), 500

        # Verificar estado del Knowledge RAG
        knowledge_rag_status = call_model_router(f"{KNOWLEDGE_RAG_URL}/api/knowledge/status")
        if not knowledge_rag_status or knowledge_rag_status.get("status") != "ok":
            knowledge_rag_status = {"status": "unknown"}

        # Verificar estado del Context Bus
        context_bus_status = call_context_bus("api/context_bus/status")
        if not context_bus_status or context_bus_status.get("status") != "ok":
            context_bus_status = {"status": "unknown"}

        # Verificar estado del Swarm Orchestrator
        swarm_status = call_swarm_orchestrator("api/swarm/status")
        if not swarm_status or swarm_status.get("status") != "ok":
            swarm_status = {"status": "unknown"}

        return jsonify({
            "status": "ok",
            "model_router": model_router_status,
            "knowledge_rag": knowledge_rag_status,
            "context_bus": context_bus_status,
            "swarm_orchestrator": swarm_status,
            "offline_mode": model_router_status.get("offline_mode", False),
            "available_models": [
                m for m, status in model_router_status.get("status", {}).items()
                if status.get("available", False)
            ]
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error al obtener estado: {str(e)}"
        }), 500

@app.route('/api/llm/context', methods=['GET'])
def get_context_endpoint():
    """Endpoint para obtener contexto relevante del Shared Context Bus."""
    try:
        # Obtener todos los tipos de contexto disponibles
        context_types = ["RESEARCH_TASK", "CODE_TASK", "CREATIVE_TASK", "GENERAL_TASK", "swarm_results"]

        all_context = []
        for context_type in context_types:
            result = call_context_bus(f"api/context_bus/get/type/{context_type}", {"limit": 5})
            if result and result.get("status") == "ok":
                all_context.extend(result.get("contexts", []))

        return jsonify({
            "status": "ok",
            "total_context_items": len(all_context),
            "contexts": all_context[:20]  # Limitar a 20 elementos para no saturar
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error al obtener contexto: {str(e)}"
        }), 500

@app.route('/api/llm/swarm/test', methods=['POST'])
def test_swarm_endpoint():
    """Endpoint para probar el Swarm Orchestrator."""
    data = request.get_json()
    if not data or 'auth_key' not in data:
        return jsonify({"status": "error", "message": "Llave de autorización requerida"}), 400

    auth_key = data.get('auth_key')
    if auth_key != AUTH_KEY:
        return jsonify({"status": "error", "message": "Llave de autorización inválida"}), 403

    # Tarea de ejemplo para probar el enjambre
    example_task = "Explica cómo implementar un sistema de monitoreo de servidores con Prometheus y Grafana, incluyendo ejemplos de código, configuración, despliegue, monitoreo y mejores prácticas de optimización."

    try:
        result = call_swarm_orchestrator("api/swarm/test", {"auth_key": AUTH_KEY})
        if result and result.get("status") == "ok":
            return jsonify({
                "status": "ok",
                "message": "Prueba del enjambre completada con éxito",
                "result": result.get("result"),
                "example_task": example_task
            })
        else:
            return jsonify({
                "status": "error",
                "message": result.get("message", "Error al probar el enjambre")
            })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error al probar el enjambre: {str(e)}"
        }), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5014, debug=False)