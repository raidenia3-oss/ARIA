#!/usr/bin/env python3
"""
Script de prueba para el Parallel Agent Swarm.
Demuestra cómo el enjambre de agentes puede trabajar en paralelo para resolver tareas complejas.
"""

import requests
import time
import json
from datetime import datetime

# Configuración global
LLM_ANALYZER_URL = "http://localhost:5014"
SWARM_ORCHESTRATOR_URL = "http://localhost:5016"
CONTEXT_BUS_URL = "http://localhost:5015"
AUTH_KEY = "SECRET_AUTH_KEY_12345"

def call_llm_analyzer(endpoint, data=None):
    """Llamar al LLM Analyzer."""
    try:
        url = f"{LLM_ANALYZER_URL}/{endpoint}"
        if data:
            response = requests.post(url, json=data, timeout=30)
        else:
            response = requests.get(url, timeout=10)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error al llamar a LLM Analyzer ({endpoint}): {response.text}")
            return None
    except Exception as e:
        print(f"Error al llamar a LLM Analyzer ({endpoint}): {e}")
        return None

def call_swarm_orchestrator(endpoint, data=None):
    """Llamar al Swarm Orchestrator."""
    try:
        url = f"{SWARM_ORCHESTRATOR_URL}/{endpoint}"
        if data:
            response = requests.post(url, json=data, timeout=60)  # Tiempo más largo para tareas complejas
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

def call_context_bus(endpoint, data=None):
    """Llamar al Shared Context Bus."""
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

def test_simple_task():
    """Probar una tarea simple con el LLM Analyzer (sin enjambre)."""
    print("\n🧪 Probando tarea simple con LLM Analyzer...")

    prompt = "Escribe un script en Python para analizar datos de tráfico de red."
    system_prompt = "Eres un experto en programación y análisis de datos."

    result = call_llm_analyzer("api/llm/analyze", {
        "auth_key": AUTH_KEY,
        "prompt": prompt,
        "system_prompt": system_prompt
    })

    if result and result.get("status") == "ok":
        print("✅ Tarea simple completada con éxito:")
        print(f"   - Modelo usado: {result.get('model')}")
        print(f"   - Tipo de tarea: {result.get('task_type')}")
        print(f"   - Longitud de respuesta: {len(result.get('response', ''))} caracteres")
        return True
    else:
        print("❌ Error en tarea simple:")
        print(f"   - Error: {result.get('message', 'Desconocido')}")
        return False

def test_complex_task():
    """Probar una tarea compleja con el Swarm Orchestrator."""
    print("\n🧬 Probando tarea compleja con Swarm Orchestrator...")

    # Tarea compleja que debería ser procesada por el enjambre
    prompt = """
    Explica cómo implementar un sistema completo de monitoreo de servidores usando Prometheus y Grafana,
    incluyendo:
    1. Arquitectura del sistema y componentes principales
    2. Configuración de Prometheus para recolectar métricas de CPU, memoria, disco y red
    3. Implementación de alertas personalizadas para umbrales críticos
    4. Configuración de Grafana para visualizar dashboards interactivos
    5. Ejemplos de código para configuración y despliegue
    6. Mejores prácticas para optimización y escalabilidad
    7. Consideraciones de seguridad y privacidad
    8. Estrategias de backup y recuperación ante fallos
    """

    system_prompt = """
    Eres un experto en sistemas de monitoreo y arquitectura de software.
    Proporciona una respuesta completa y bien estructurada que cubra todos los aspectos mencionados.
    """

    print("📤 Enviando tarea compleja al Swarm Orchestrator...")
    result = call_swarm_orchestrator("api/swarm/execute", {
        "auth_key": AUTH_KEY,
        "prompt": prompt,
        "system_prompt": system_prompt
    })

    if result and result.get("status") == "ok":
        print("✅ Tarea compleja completada con éxito por el enjambre:")
        print(f"   - Síntesis generada: {len(result.get('synthesis', ''))} caracteres")
        print(f"   - Agentes exitosos: {len([r for r in result.get('original_results', []) if r.get('status') == 'ok'])}")
        print(f"   - Agentes fallidos: {len([r for r in result.get('original_results', []) if r.get('status') != 'ok'])}")

        # Mostrar un resumen de los resultados
        print("\n📋 Resumen de resultados del enjambre:")
        for i, subtask_result in enumerate(result.get("original_results", []), 1):
            status = "✅" if subtask_result.get("status") == "ok" else "❌"
            print(f"   {status} Agente {i}: {subtask_result.get('agent', 'desconocido')}")
            if subtask_result.get("status") == "ok":
                print(f"      - Especialización: {subtask_result.get('specialization', 'general')}")
                print(f"      - Longitud: {len(subtask_result.get('response', ''))} caracteres")
            else:
                print(f"      - Error: {subtask_result.get('error', 'Desconocido')}")

        # Mostrar parte de la síntesis
        synthesis = result.get("synthesis", "")
        print("\n📝 Primeras 300 líneas de la síntesis final:")
        print("-" * 80)
        print(synthesis[:3000] + "..." if len(synthesis) > 3000 else synthesis)
        print("-" * 80)

        return True
    else:
        print("❌ Error en tarea compleja:")
        print(f"   - Error: {result.get('message', 'Desconocido')}")
        return False

def test_swarm_directly():
    """Probar directamente el Swarm Orchestrator con una tarea de ejemplo."""
    print("\n🧪 Probando Swarm Orchestrator directamente...")

    result = call_swarm_orchestrator("api/swarm/test", {"auth_key": AUTH_KEY})

    if result and result.get("status") == "ok":
        print("✅ Prueba del Swarm Orchestrator completada con éxito:")
        print(f"   - Tarea de ejemplo: {result.get('example_task', '')[:100]}...")
        print(f"   - Síntesis generada: {len(result.get('result', {}).get('synthesis', ''))} caracteres")

        # Mostrar parte de la síntesis
        synthesis = result.get("result", {}).get("synthesis", "")
        print("\n📝 Primeras 300 líneas de la síntesis:")
        print("-" * 80)
        print(synthesis[:3000] + "..." if len(synthesis) > 3000 else synthesis)
        print("-" * 80)

        return True
    else:
        print("❌ Error en prueba del Swarm Orchestrator:")
        print(f"   - Error: {result.get('message', 'Desconocido')}")
        return False

def get_swarm_status():
    """Obtener el estado actual del Swarm Orchestrator."""
    print("\n📊 Obteniendo estado del Swarm Orchestrator...")

    result = call_swarm_orchestrator("api/swarm/status")
    if result and result.get("status") == "ok":
        status = result.get("status", {})
        print(f"✅ Estado del Swarm Orchestrator:")
        print(f"   - Última actualización: {status.get('last_updated', 'Nunca')}")
        print(f"   - Tareas activas: {status.get('active_tasks', 0)}")
        print(f"   - Tareas completadas: {status.get('completed_tasks', 0)}")
        print(f"   - Tareas fallidas: {status.get('failed_tasks', 0)}")
        print(f"   - Error actual: {status.get('last_error', 'Ninguno')}")
        return True
    else:
        print("❌ Error al obtener estado del Swarm Orchestrator:")
        print(f"   - Error: {result.get('message', 'Desconocido')}")
        return False

def get_global_knowledge_after_swarm():
    """Obtener el conocimiento global después de ejecutar el enjambre."""
    print("\n📚 Obteniendo conocimiento global después del enjambre...")

    result = call_context_bus("api/context_bus/global_knowledge")
    if result and result.get("status") == "ok":
        content = result.get("content", "")
        print(f"✅ Conocimiento global obtenido (tamaño: {len(content)} caracteres)")
        print(f"Última actualización: {result.get('last_modified')}")

        # Buscar secciones relacionadas con el enjambre
        if "swarm_results" in content.lower():
            print("\n🔍 Se encontraron resultados del enjambre en el conocimiento global:")
            lines = content.split('\n')
            in_swarm_section = False
            for line in lines:
                if "swarm_results" in line.lower():
                    in_swarm_section = True
                    print(f"\n--- {line.strip()} ---")
                elif in_swarm_section and line.strip() and not line.startswith("##"):
                    if len(line) > 100:
                        print(f"   {line[:100]}...")
                    else:
                        print(f"   {line}")
                elif in_swarm_section and line.startswith("##"):
                    break
        else:
            print("⚠️ No se encontraron resultados específicos del enjambre en el conocimiento global.")
            print("   (Esto es normal si no se ejecutó ninguna tarea compleja)")

        return True
    else:
        print("❌ Error al obtener conocimiento global:")
        print(f"   - Error: {result.get('message', 'Desconocido')}")
        return False

def main():
    """Función principal para demostrar el Parallel Agent Swarm."""
    print("=" * 100)
    print("🧬 DEMOSTRACIÓN DEL PARALLEL AGENT SWARM")
    print("=" * 100)
    print("Este script demuestra cómo el enjambre de agentes de AURA puede trabajar en paralelo:")
    print("1. Detección automática de tareas complejas")
    print("2. División en subtareas especializadas")
    print("3. Ejecución en paralelo por diferentes agentes")
    print("4. Síntesis inteligente de resultados")
    print("5. Publicación en el conocimiento global")
    print("=" * 100)

    # Paso 1: Probar tarea simple (sin enjambre)
    simple_success = test_simple_task()
    time.sleep(2)

    # Paso 2: Probar tarea compleja (con enjambre)
    complex_success = test_complex_task()
    time.sleep(3)

    # Paso 3: Probar directamente el Swarm Orchestrator
    swarm_success = test_swarm_directly()
    time.sleep(2)

    # Paso 4: Obtener estado del enjambre
    status_success = get_swarm_status()
    time.sleep(1)

    # Paso 5: Obtener conocimiento global después del enjambre
    knowledge_success = get_global_knowledge_after_swarm()

    # Resumen de resultados
    print("\n" + "=" * 100)
    print("📊 RESUMEN DE LA DEMOSTRACIÓN")
    print("=" * 100)
    print(f"✅ Tarea simple: {'Completada' if simple_success else 'Fallida'}")
    print(f"✅ Tarea compleja (enjambre): {'Completada' if complex_success else 'Fallida'}")
    print(f"✅ Prueba directa del Swarm: {'Completada' if swarm_success else 'Fallida'}")
    print(f"✅ Estado del enjambre: {'Obtenido' if status_success else 'Fallido'}")
    print(f"✅ Conocimiento global: {'Obtenido' if knowledge_success else 'Fallido'}")

    if all([simple_success, complex_success, swarm_success, status_success, knowledge_success]):
        print("\n🎉 ¡TODAS LAS PRUEBAS SE COMPLETARON CON ÉXITO!")
        print("\n🔄 Flujo de trabajo demostrado:")
        print("1. Tarea simple → Procesada por un solo agente")
        print("2. Tarea compleja → Dividida en 3 subtareas → Procesada en paralelo por 3 agentes")
        print("3. Resultados sintetizados → Publicados en conocimiento global")
        print("4. Sistema escalable → Puede manejar cualquier número de subtareas")
        print("5. Tolerancia a fallos → Si un agente falla, los otros continúan")
    else:
        print("\n⚠️ Algunas pruebas fallaron. Revisa los mensajes de error anteriores.")

    print("\n" + "=" * 100)
    print("💡 BENEFICIOS DEL PARALLEL AGENT SWARM:")
    print("• Mayor profundidad en las respuestas (múltiples perspectivas)")
    print("• Especialización (cada agente aporta su área de expertise)")
    print("• Paralelismo (tareas complejas se resuelven más rápido)")
    print("• Tolerancia a fallos (el sistema sigue funcionando si un agente falla)")
    print("• Conocimiento acumulado (todos los resultados se guardan para futuro uso)")
    print("• Escalabilidad (puede manejar tareas cada vez más complejas)")
    print("=" * 100)

if __name__ == "__main__":
    main()