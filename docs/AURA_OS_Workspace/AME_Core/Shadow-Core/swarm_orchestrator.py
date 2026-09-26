#!/usr/bin/env python3
"""
Swarm Orchestrator para AURA.
Gestiona un enjambre de agentes que trabajan en paralelo para resolver tareas complejas.
Divide tareas en subtareas, ejecuta agentes en paralelo y sintetiza los resultados.
"""

import os
import json
import time
import uuid
import threading
import concurrent.futures
from datetime import datetime
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# Configuración global
LLM_ANALYZER_URL = "http://localhost:5014"
CONTEXT_BUS_URL = "http://localhost:5015"
AUTH_KEY = "SECRET_AUTH_KEY_12345"
MAX_WORKERS = 3  # Número máximo de agentes trabajando en paralelo
TIMEOUT_SECONDS = 30  # Tiempo máximo para completar una subtarea

# Configuración de agentes
AGENT_CONFIG = {
    "research_agent": {
        "name": "Research Agent",
        "description": "Agente especializado en investigación y análisis profundo.",
        "model": "dolphin-llama3",
        "system_prompt": """
        Eres un experto en investigación y análisis técnico. Proporciona respuestas detalladas,
        bien fundamentadas y con contexto relevante. Cuando se solicite investigación,
        asegúrate de incluir fuentes de información, ejemplos concretos y análisis profundos.
        """,
        "specialization": "investigación, análisis, teorías, conceptos, metodologías"
    },
    "code_agent": {
        "name": "Code Agent",
        "description": "Agente especializado en programación y generación de código.",
        "model": "deepseek-coder",
        "system_prompt": """
        Eres un experto en programación y desarrollo de software. Proporciona respuestas técnicas,
        ejemplos de código claros y soluciones optimizadas. Si se solicita código,
        asegúrate de que sea funcional, bien estructurado y comentado adecuadamente.
        """,
        "specialization": "programación, algoritmos, código, implementaciones, depuración"
    },
    "creative_agent": {
        "name": "Creative Agent",
        "description": "Agente especializado en generación de ideas y contenido creativo.",
        "model": "mistral-nemo-uncensored",
        "system_prompt": """
        Eres un experto en creatividad y generación de ideas. Proporciona respuestas innovadoras,
        originales y con enfoque en la generación de contenido libre y sin restricciones.
        Cuando se solicite creatividad, asegúrate de incluir múltiples perspectivas,
        ejemplos concretos y soluciones innovadoras.
        """,
        "specialization": "ideas, creatividad, brainstorming, conceptos, innovación"
    },
    "general_agent": {
        "name": "General Agent",
        "description": "Agente generalista para consultas diversas.",
        "model": "llama3",
        "system_prompt": """
        Eres un asistente generalista con conocimientos amplios en diversos temas.
        Proporciona respuestas claras, concisas y bien estructuradas para consultas de propósito general.
        """,
        "specialization": "general, diversidad, respuestas amplias"
    }
}

# Estado del enjambre
SWARM_STATUS = {
    "last_updated": None,
    "active_tasks": 0,
    "completed_tasks": 0,
    "failed_tasks": 0,
    "last_error": None
}

def call_llm_analyzer(endpoint, data=None):
    """Llamar al LLM Analyzer para obtener respuestas de los agentes."""
    try:
        url = f"{LLM_ANALYZER_URL}/{endpoint}"
        if data:
            response = requests.post(url, json=data, timeout=TIMEOUT_SECONDS)
        else:
            response = requests.get(url, timeout=TIMEOUT_SECONDS)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error al llamar a LLM Analyzer ({endpoint}): {response.text}")
            return None
    except Exception as e:
        print(f"Error al llamar a LLM Analyzer ({endpoint}): {e}")
        return None

def call_context_bus(endpoint, data=None):
    """Llamar al Shared Context Bus para gestionar el contexto."""
    try:
        url = f"{CONTEXT_BUS_URL}/{endpoint}"
        if data:
            response = requests.post(url, json=data, timeout=TIMEOUT_SECONDS)
        else:
            response = requests.get(url, timeout=TIMEOUT_SECONDS)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error al llamar a Context Bus ({endpoint}): {response.text}")
            return None
    except Exception as e:
        print(f"Error al llamar a Context Bus ({endpoint}): {e}")
        return None

def split_complex_task(task_description, system_prompt=None):
    """
    Dividir una tarea compleja en 3 subtareas para ser procesadas en paralelo.
    Cada subtarea se asigna a un agente diferente según su especialización.
    """
    try:
        # Analizar la tarea para determinar qué aspectos abordar
        task_lower = task_description.lower()
        system_prompt_lower = system_prompt.lower() if system_prompt else ""

        # Determinar el tipo de tarea principal
        task_type = "general"
        if any(keyword in task_lower for keyword in [
            "investigar", "analizar", "teoría", "concepto", "metodología",
            "prácticas", "mejores", "herramientas", "recomendaciones"
        ]):
            task_type = "research"
        elif any(keyword in task_lower for keyword in [
            "código", "script", "función", "algoritmo", "implementar",
            "programar", "depurar", "optimizar", "librería", "paquete"
        ]):
            task_type = "code"
        elif any(keyword in task_lower for keyword in [
            "ideas", "crear", "generar", "conceptos", "innovador",
            "brainstorming", "propuestas", "diseñar", "nombres", "campaña"
        ]):
            task_type = "creative"

        # Definir las 3 subtareas según el tipo de tarea
        if task_type == "research":
            subtasks = [
                {
                    "agent": "research_agent",
                    "description": f"Analiza en profundidad los fundamentos teóricos y conceptos clave relacionados con: '{task_description}'. Incluye definiciones, principios y ejemplos concretos.",
                    "system_prompt": AGENT_CONFIG["research_agent"]["system_prompt"],
                    "specialization": "fundamentos teóricos"
                },
                {
                    "agent": "research_agent",
                    "description": f"Investiga las mejores prácticas, metodologías y herramientas recomendadas para: '{task_description}'. Incluye casos de uso, beneficios y limitaciones.",
                    "system_prompt": AGENT_CONFIG["research_agent"]["system_prompt"],
                    "specialization": "mejores prácticas"
                },
                {
                    "agent": "general_agent",
                    "description": f"Proporciona una visión general y conclusiones prácticas sobre: '{task_description}'. Sintetiza la información y ofrece recomendaciones de implementación.",
                    "system_prompt": AGENT_CONFIG["general_agent"]["system_prompt"],
                    "specialization": "visión general"
                }
            ]
        elif task_type == "code":
            subtasks = [
                {
                    "agent": "code_agent",
                    "description": f"Implementa un ejemplo básico de código que demuestre el concepto principal de: '{task_description}'. Usa Python y asegúrate de que el código sea funcional y bien comentado.",
                    "system_prompt": AGENT_CONFIG["code_agent"]["system_prompt"],
                    "specialization": "implementación básica"
                },
                {
                    "agent": "code_agent",
                    "description": f"Proporciona un análisis de complejidad y optimizaciones para: '{task_description}'. Incluye consideraciones de rendimiento, patrones de diseño y buenas prácticas.",
                    "system_prompt": AGENT_CONFIG["code_agent"]["system_prompt"],
                    "specialization": "análisis y optimización"
                },
                {
                    "agent": "research_agent",
                    "description": f"Investiga librerías, frameworks y herramientas relacionadas con: '{task_description}'. Incluye comparativas, ventajas y casos de uso prácticos.",
                    "system_prompt": AGENT_CONFIG["research_agent"]["system_prompt"],
                    "specialization": "herramientas y librerías"
                }
            ]
        elif task_type == "creative":
            subtasks = [
                {
                    "agent": "creative_agent",
                    "description": f"Genera 3 ideas innovadoras y originales para abordar: '{task_description}'. Incluye descripciones detalladas y justificaciones de cada propuesta.",
                    "system_prompt": AGENT_CONFIG["creative_agent"]["system_prompt"],
                    "specialization": "generación de ideas"
                },
                {
                    "agent": "creative_agent",
                    "description": f"Diseña un plan de acción o roadmap para implementar una solución creativa a: '{task_description}'. Incluye pasos, recursos y cronograma estimado.",
                    "system_prompt": AGENT_CONFIG["creative_agent"]["system_prompt"],
                    "specialization": "planificación creativa"
                },
                {
                    "agent": "general_agent",
                    "description": f"Proporciona una evaluación crítica de las ideas generadas para: '{task_description}'. Analiza viabilidad, impacto y posibles desafíos.",
                    "system_prompt": AGENT_CONFIG["general_agent"]["system_prompt"],
                    "specialization": "evaluación crítica"
                }
            ]
        else:  # Tarea general
            subtasks = [
                {
                    "agent": "research_agent",
                    "description": f"Investiga y proporciona información detallada sobre: '{task_description}'. Incluye fuentes, ejemplos y contexto relevante.",
                    "system_prompt": AGENT_CONFIG["research_agent"]["system_prompt"],
                    "specialization": "información detallada"
                },
                {
                    "agent": "creative_agent",
                    "description": f"Genera perspectivas creativas e innovadoras sobre: '{task_description}'. Incluye ideas, enfoques alternativos y soluciones originales.",
                    "system_prompt": AGENT_CONFIG["creative_agent"]["system_prompt"],
                    "specialization": "perspectivas creativas"
                },
                {
                    "agent": "general_agent",
                    "description": f"Proporciona una respuesta equilibrada y práctica sobre: '{task_description}'. Sintetiza la información y ofrece recomendaciones claras.",
                    "system_prompt": AGENT_CONFIG["general_agent"]["system_prompt"],
                    "specialization": "respuesta equilibrada"
                }
            ]

        return {
            "status": "ok",
            "original_task": task_description,
            "task_type": task_type,
            "subtasks": subtasks
        }
    except Exception as e:
        print(f"Error al dividir tarea compleja: {e}")
        return {
            "status": "error",
            "message": f"Error al dividir tarea: {str(e)}",
            "original_task": task_description
        }

def execute_subtask(subtask):
    """Ejecutar una subtarea usando el agente correspondiente."""
    try:
        task_id = str(uuid.uuid4())
        agent_name = subtask["agent"]
        description = subtask["description"]
        system_prompt = subtask["system_prompt"]

        # Preparar los datos para el LLM Analyzer
        data = {
            "auth_key": AUTH_KEY,
            "prompt": description,
            "system_prompt": system_prompt
        }

        # Ejecutar la subtarea
        result = call_llm_analyzer("api/llm/analyze", data)

        if result and result.get("status") == "ok":
            return {
                "status": "ok",
                "task_id": task_id,
                "agent": agent_name,
                "description": description,
                "response": result.get("response"),
                "model": result.get("model"),
                "task_type": result.get("task_type"),
                "specialization": subtask.get("specialization", "general"),
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "error",
                "task_id": task_id,
                "agent": agent_name,
                "description": description,
                "error": result.get("message", "Error desconocido"),
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        return {
            "status": "error",
            "task_id": str(uuid.uuid4()),
            "agent": subtask.get("agent", "desconocido"),
            "description": subtask.get("description", ""),
            "error": f"Error al ejecutar subtarea: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

def execute_parallel_subtasks(subtasks):
    """Ejecutar subtareas en paralelo usando un pool de trabajadores."""
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Enviar todas las subtareas al pool
            future_to_subtask = {
                executor.submit(execute_subtask, subtask): subtask
                for subtask in subtasks
            }

            results = []
            for future in concurrent.futures.as_completed(future_to_subtask):
                subtask = future_to_subtask[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append({
                        "status": "error",
                        "task_id": str(uuid.uuid4()),
                        "agent": subtask.get("agent", "desconocido"),
                        "description": subtask.get("description", ""),
                        "error": f"Excepción al ejecutar subtarea: {str(e)}",
                        "timestamp": datetime.now().isoformat()
                    })

        return results
    except Exception as e:
        print(f"Error al ejecutar subtareas en paralelo: {e}")
        return [{
            "status": "error",
            "task_id": str(uuid.uuid4()),
            "agent": "swarm_orchestrator",
            "description": "Tarea compleja",
            "error": f"Error en el enjambre: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }]

def synthesize_results(subtask_results):
    """Sintetizar los resultados de las subtareas en una respuesta coherente."""
    try:
        if not subtask_results:
            return {
                "status": "error",
                "message": "No hay resultados para sintetizar",
                "synthesis": "No se pudieron obtener resultados de los agentes."
            }

        # Filtrar resultados exitosos
        successful_results = [r for r in subtask_results if r.get("status") == "ok"]
        failed_results = [r for r in subtask_results if r.get("status") != "ok"]

        if not successful_results:
            error_messages = [r.get("error", "Error desconocido") for r in failed_results]
            return {
                "status": "error",
                "message": "Todos los agentes fallaron",
                "errors": error_messages,
                "synthesis": f"Todos los agentes fallaron. Errores: {', '.join(error_messages)}"
            }

        # Crear un prompt para sintetizar los resultados
        synthesis_prompt = """
        Eres un experto en síntesis de información y generación de respuestas coherentes.
        Tienes los siguientes resultados de diferentes agentes que trabajaron en paralelo
        para responder a una pregunta compleja. Tu tarea es sintetizar toda esta información
        en una respuesta final coherente, bien estructurada y fácil de entender.

        Resultados de los agentes:
        """

        # Añadir cada resultado al prompt
        for i, result in enumerate(successful_results, 1):
            agent_name = result.get("agent", "Agente desconocido")
            specialization = result.get("specialization", "general")
            response = result.get("response", "")

            synthesis_prompt += f"""
        --- AGENTE {i}: {agent_name} (Especialización: {specialization}) ---
        {response}
        """

        synthesis_prompt += """
        ---
        Basado en toda esta información, genera una respuesta final que:
        1. Sintetice los puntos clave de cada agente
        2. Proporcione una visión integral y coherente
        3. Incluya conclusiones prácticas y recomendaciones
        4. Esté bien estructurada y sea fácil de entender
        5. Mencione cualquier discrepancia o punto de vista diferente entre los agentes
        """

        # Llamar al LLM Analyzer para sintetizar
        synthesis_result = call_llm_analyzer("api/llm/analyze", {
            "auth_key": AUTH_KEY,
            "prompt": synthesis_prompt,
            "system_prompt": """
            Eres un experto en síntesis de información con capacidad para integrar múltiples perspectivas
            en una respuesta coherente y bien estructurada. Proporciona respuestas claras, concisas
            y con valor agregado basado en la información proporcionada.
            """
        })

        if synthesis_result and synthesis_result.get("status") == "ok":
            return {
                "status": "ok",
                "synthesis": synthesis_result.get("response"),
                "original_results": successful_results,
                "failed_results": failed_results,
                "timestamp": datetime.now().isoformat()
            }
        else:
            # Si falla la síntesis, crear una respuesta manual
            manual_synthesis = []
            manual_synthesis.append("## Síntesis Manual de Resultados del Enjambre")
            manual_synthesis.append(f"Se recibieron respuestas de {len(successful_results)} agentes (de {len(subtask_results)} subtareas).")

            for i, result in enumerate(successful_results, 1):
                agent_name = result.get("agent", "Agente desconocido")
                specialization = result.get("specialization", "general")
                response = result.get("response", "")

                manual_synthesis.append(f"\n### Agente {i}: {agent_name} ({specialization})")
                manual_synthesis.append(f"**Respuesta:**")
                manual_synthesis.append(f"{response}")

            if failed_results:
                manual_synthesis.append("\n## Agentes que fallaron:")
                for i, result in enumerate(failed_results, 1):
                    manual_synthesis.append(f"\n### Agente {i} (fallido)")
                    manual_synthesis.append(f"**Error:** {result.get('error', 'Error desconocido')}")

            return {
                "status": "partial",
                "synthesis": "\n".join(manual_synthesis),
                "original_results": successful_results,
                "failed_results": failed_results,
                "timestamp": datetime.now().isoformat(),
                "note": "La síntesis automática falló. Se proporcionó una síntesis manual basada en los resultados disponibles."
            }
    except Exception as e:
        print(f"Error al sintetizar resultados: {e}")
        return {
            "status": "error",
            "message": f"Error al sintetizar resultados: {str(e)}",
            "original_results": subtask_results,
            "timestamp": datetime.now().isoformat()
        }

def publish_swarm_results(synthesis_result, original_task):
    """Publicar los resultados del enjambre en el Shared Context Bus."""
    try:
        if synthesis_result.get("status") == "ok":
            context_item = {
                "agent_type": "swarm_orchestrator",
                "type": "swarm_results",
                "summary": f"Resultado sintetizado de enjambre para: {original_task[:50]}...",
                "content": synthesis_result.get("synthesis"),
                "format": "markdown",
                "original_task": original_task,
                "successful_agents": len([r for r in synthesis_result.get("original_results", []) if r.get("status") == "ok"]),
                "total_agents": len(synthesis_result.get("original_results", [])),
                "timestamp": synthesis_result.get("timestamp")
            }

            result = call_context_bus("api/context_bus/publish", {
                "auth_key": AUTH_KEY,
                "context": context_item
            })

            if result and result.get("status") == "ok":
                synthesis_result["context_id"] = result.get("context_id")
                return synthesis_result
            else:
                synthesis_result["context_publication_error"] = "No se pudo publicar en el Context Bus"
                return synthesis_result
        else:
            return synthesis_result
    except Exception as e:
        synthesis_result["context_publication_error"] = f"Error al publicar resultados: {str(e)}"
        return synthesis_result

def execute_swarm_task(task_description, system_prompt=None):
    """Ejecutar una tarea compleja usando el enjambre de agentes."""
    try:
        # 1. Dividir la tarea en subtareas
        split_result = split_complex_task(task_description, system_prompt)
        if split_result.get("status") != "ok":
            return split_result

        subtasks = split_result.get("subtasks", [])
        if not subtasks:
            return {
                "status": "error",
                "message": "No se pudieron generar subtareas",
                "original_task": task_description
            }

        # 2. Ejecutar subtareas en paralelo
        print(f"🚀 Ejecutando {len(subtasks)} subtareas en paralelo...")
        subtask_results = execute_parallel_subtasks(subtasks)

        # 3. Sintetizar los resultados
        print("🔄 Sintetizando resultados...")
        synthesis_result = synthesize_results(subtask_results)

        # 4. Publicar resultados en el Context Bus
        print("📤 Publicando resultados en el Context Bus...")
        final_result = publish_swarm_results(synthesis_result, task_description)

        # 5. Actualizar estado del enjambre
        SWARM_STATUS["last_updated"] = datetime.now().isoformat()
        SWARM_STATUS["completed_tasks"] += 1
        SWARM_STATUS["active_tasks"] = 0
        SWARM_STATUS["failed_tasks"] = len([r for r in subtask_results if r.get("status") != "ok"])
        SWARM_STATUS["last_error"] = None

        return final_result
    except Exception as e:
        SWARM_STATUS["last_error"] = str(e)
        return {
            "status": "error",
            "message": f"Error al ejecutar tarea en el enjambre: {str(e)}",
            "original_task": task_description
        }

def get_swarm_status():
    """Obtener el estado actual del enjambre."""
    return SWARM_STATUS

def initialize_swarm():
    """Inicializar el enjambre de agentes."""
    try:
        print("✅ Swarm Orchestrator inicializado correctamente")
        SWARM_STATUS["last_updated"] = datetime.now().isoformat()
        SWARM_STATUS["active_tasks"] = 0
        SWARM_STATUS["completed_tasks"] = 0
        SWARM_STATUS["failed_tasks"] = 0
        SWARM_STATUS["last_error"] = None
        return True
    except Exception as e:
        print(f"❌ Error al inicializar Swarm Orchestrator: {e}")
        SWARM_STATUS["last_error"] = str(e)
        return False

# Endpoints para gestionar el enjambre
@app.route('/api/swarm/execute', methods=['POST'])
def execute_swarm_task_endpoint():
    """Endpoint para ejecutar una tarea compleja usando el enjambre."""
    data = request.get_json()
    if not data or 'auth_key' not in data or 'prompt' not in data:
        return jsonify({"status": "error", "message": "Llave de autorización y prompt requeridos"}), 400

    auth_key = data.get('auth_key')
    if auth_key != AUTH_KEY:
        return jsonify({"status": "error", "message": "Llave de autorización inválida"}), 403

    prompt = data['prompt']
    system_prompt = data.get('system_prompt')

    try:
        # Incrementar contador de tareas activas
        SWARM_STATUS["active_tasks"] += 1

        # Ejecutar la tarea en el enjambre
        result = execute_swarm_task(prompt, system_prompt)

        return jsonify(result)
    except Exception as e:
        SWARM_STATUS["last_error"] = str(e)
        return jsonify({
            "status": "error",
            "message": f"Error al ejecutar tarea en el enjambre: {str(e)}"
        }), 500
    finally:
        # Decrementar contador de tareas activas (en caso de error)
        SWARM_STATUS["active_tasks"] = max(0, SWARM_STATUS["active_tasks"] - 1)

@app.route('/api/swarm/status', methods=['GET'])
def get_swarm_status_endpoint():
    """Endpoint para obtener el estado del enjambre."""
    return jsonify(get_swarm_status())

@app.route('/api/swarm/agents', methods=['GET'])
def list_agents_endpoint():
    """Endpoint para listar los agentes disponibles en el enjambre."""
    return jsonify({
        "status": "ok",
        "agents": AGENT_CONFIG,
        "total_agents": len(AGENT_CONFIG)
    })

@app.route('/api/swarm/test', methods=['POST'])
def test_swarm_endpoint():
    """Endpoint para probar el enjambre con una tarea de ejemplo."""
    data = request.get_json()
    if not data or 'auth_key' not in data:
        return jsonify({"status": "error", "message": "Llave de autorización requerida"}), 400

    auth_key = data.get('auth_key')
    if auth_key != AUTH_KEY:
        return jsonify({"status": "error", "message": "Llave de autorización inválida"}), 403

    # Tarea de ejemplo para probar el enjambre
    example_task = "Explica cómo implementar un sistema de monitoreo de servidores con Prometheus y Grafana, incluyendo ejemplos de código, configuración, despliegue, monitoreo y mejores prácticas de optimización."

    try:
        result = execute_swarm_task(example_task)
        return jsonify({
            "status": "ok",
            "message": "Prueba del enjambre completada con éxito",
            "result": result,
            "example_task": example_task
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error al probar el enjambre: {str(e)}"
        }), 500

if __name__ == "__main__":
    # Inicializar el enjambre
    if not initialize_swarm():
        print("⚠️ No se pudo inicializar el Swarm Orchestrator. Continuando sin funcionalidad completa...")

    # Iniciar el servidor
    app.run(host='0.0.0.0', port=5016, debug=False)