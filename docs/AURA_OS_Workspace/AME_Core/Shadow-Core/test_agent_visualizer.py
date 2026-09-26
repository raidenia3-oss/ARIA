#!/usr/bin/env python3
"""
Script de prueba para el Agent Swarm Visualizer.
Simula actividades en el enjambre para probar la visualización en tiempo real.
"""

import requests
import time
import random
from datetime import datetime

# Configuración global
MODEL_ROUTER_URL = "http://localhost:5011"
AUTH_KEY = "SECRET_AUTH_KEY_12345"

def call_model_router(endpoint, data=None):
    """Llamar al Model Router."""
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

def simulate_agent_activity():
    """Simular actividades de los agentes para probar la visualización."""
    print("🧪 Simulando actividades del enjambre para probar la visualización...")
    print("Abre el visualizador en: http://localhost:5017")
    print("Presiona Enter para continuar con la simulación...")

    input()  # Esperar a que el usuario abra el visualizador

    # Tareas de ejemplo para simular
    tasks = [
        "Implementar un sistema de autenticación con JWT en Flask",
        "Investigar las mejores prácticas para optimizar consultas SQL en PostgreSQL",
        "Generar 5 nombres creativos para una startup de inteligencia artificial",
        "Analizar el rendimiento de un algoritmo de machine learning",
        "Crear un dashboard interactivo con Grafana para monitoreo de servidores",
        "Refactorizar un código legado en Python para mejorar su legibilidad",
        "Diseñar una arquitectura de microservicios para una aplicación web",
        "Escribir un script de backup automatizado para bases de datos",
        "Investigar técnicas avanzadas de caching en aplicaciones web",
        "Generar un plan de migración de una aplicación monolítica a microservicios"
    ]

    # Simular actividades de los agentes
    for i in range(5):  # 5 rondas de simulación
        print(f"\n🔄 Ronda {i+1}/5")

        # Elegir un agente aleatorio
        agents = ["coder", "researcher", "generalist"]
        agent = random.choice(agents)

        # Elegir una tarea aleatoria
        task = random.choice(tasks)

        # Simular consulta al Model Router
        print(f"🤖 {agent.capitalize()} está procesando: {task[:50]}...")

        # Enviar consulta al Model Router (simulando actividad)
        result = call_model_router("api/models/query", {
            "auth_key": AUTH_KEY,
            "prompt": task,
            "model": agent  # Esto no es correcto, pero simula la actividad
        })

        # Esperar un tiempo aleatorio (simulando procesamiento)
        processing_time = random.uniform(1, 3)
        print(f"   🕒 Procesando durante {processing_time:.1f} segundos...")
        time.sleep(processing_time)

        # Simular actividad en el enjambre
        print(f"   ✅ {agent.capitalize()} completó la tarea: {task[:30]}...")

        # Esperar antes de la siguiente ronda
        time.sleep(random.uniform(0.5, 2))

    print("\n🎉 Simulación completada!")
    print("El visualizador debería mostrar:")
    print("• Nodos de agentes cambiando de color según su estado")
    print("• Feed de actividad con las tareas procesadas")
    print("• Estado del enjambre actualizado en tiempo real")

def test_swarm_with_visualizer():
    """Probar el Swarm Orchestrator mientras el visualizador está en ejecución."""
    print("\n🧬 Probando Swarm Orchestrator con visualización en tiempo real...")
    print("Abre el visualizador en: http://localhost:5017")
    print("Presiona Enter para continuar con la prueba del Swarm...")

    input()  # Esperar a que el usuario abra el visualizador

    # Tarea compleja para probar el Swarm
    complex_task = """
    Explica cómo implementar un sistema completo de gestión de usuarios con autenticación,
    roles y permisos usando Django y PostgreSQL, incluyendo:
    1. Arquitectura del sistema y componentes principales
    2. Configuración de Django para manejo de usuarios y autenticación
    3. Implementación de roles y permisos con Django's permission system
    4. Ejemplos de código para modelos, vistas y plantillas
    5. Configuración de seguridad (HTTPS, CSRF, CORS)
    6. Integración con PostgreSQL para almacenamiento de usuarios
    7. Pruebas de seguridad y buenas prácticas
    """

    system_prompt = """
    Eres un experto en desarrollo web y seguridad de aplicaciones.
    Proporciona una respuesta completa y bien estructurada que cubra todos los aspectos mencionados.
    """

    print(f"📤 Enviando tarea compleja al Swarm Orchestrator...")
    print(f"   Tarea: {complex_task[:80]}...")

    # Enviar consulta al Swarm Orchestrator
    result = call_model_router("api/models/route", {
        "auth_key": AUTH_KEY,
        "prompt": complex_task,
        "system_prompt": system_prompt
    })

    # Esperar un tiempo para que el visualizador muestre la actividad
    print("   🕒 Esperando 10 segundos para que el visualizador muestre la actividad...")
    time.sleep(10)

    if result and result.get("status") == "ok":
        print("✅ Tarea compleja procesada por el Swarm:")
        print(f"   Síntesis generada: {len(result.get('response', ''))} caracteres")
        print(f"   Modelo usado: {result.get('model', 'desconocido')}")
    else:
        print("❌ Error al procesar la tarea compleja:")
        print(f"   Error: {result.get('message', 'Desconocido')}")

    print("\n🎉 Prueba del Swarm con visualización completada!")
    print("El visualizador debería mostrar:")
    print("• Los agentes trabajando en paralelo")
    print("• Cambios de estado (activo, orquestando)")
    print("• Registros de actividad detallados")

def main():
    """Función principal para probar el Agent Swarm Visualizer."""
    print("=" * 100)
    print("🖥️ PRUEBA DEL AGENT SWARM VISUALIZER")
    print("=" * 100)
    print("Este script simula actividades en el enjambre para probar la visualización en tiempo real.")
    print("=" * 100)

    # Opción 1: Simular actividades individuales
    print("1. Simular actividades individuales de los agentes")
    print("2. Probar el Swarm Orchestrator con visualización")
    print("3. Ambas opciones")
    choice = input("Elige una opción (1-3): ").strip()

    if choice == "1" or choice == "3":
        simulate_agent_activity()

    if choice == "2" or choice == "3":
        test_swarm_with_visualizer()

    print("\n" + "=" * 100)
    print("💡 INSTRUCCIONES:")
    print("1. Abre el visualizador en: http://localhost:5017")
    print("2. Observa cómo los nodos de agentes cambian de color según su estado:")
    print("   - Verde: Inactivo")
    print("   - Azul: Procesando tarea")
    print("   - Amarillo: Orquestando")
    print("3. Revisa el feed de actividad para ver qué tareas están siendo procesadas")
    print("4. Verifica el estado del enjambre en la parte inferior")
    print("=" * 100)

if __name__ == "__main__":
    main()