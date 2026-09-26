#!/usr/bin/env python3
"""
Script de prueba para el motor de decisión inteligente
Prueba la lógica de delegación de tareas entre local y Hugging Face
"""

import os
import sys
import json
import time
import requests
from pathlib import Path

# Añadir el directorio padre al path para importar el servidor
sys.path.insert(0, str(Path(__file__).parent))

# Importar el motor de decisión
from servidor_ame import decision_engine

def test_analisis_tareas():
    """Prueba el análisis de diferentes tipos de tareas"""
    print("🔍 Probando análisis de tareas...\n")

    # Tarea 1: Script rápido (debe ser local)
    tarea_script = {
        "id": "task_script_001",
        "type": "script",
        "estimated_memory": 500 * 1024 * 1024,  # 500 MB
        "estimated_time": 10,  # 10 segundos
        "requires_gpu": False
    }

    # Tarea 2: Modelo grande (debe ser Hugging Face)
    tarea_modelo = {
        "id": "task_llm_001",
        "type": "llm",
        "estimated_memory": 8 * 1024 * 1024 * 1024,  # 8 GB
        "estimated_time": 120,  # 2 minutos
        "requires_gpu": True,
        "model": "meta-llama/Llama-3-8b"
    }

    # Tarea 3: Automatización (debe ser local)
    tarea_automation = {
        "id": "task_auto_001",
        "type": "automation",
        "estimated_memory": 200 * 1024 * 1024,  # 200 MB
        "estimated_time": 5,  # 5 segundos
        "requires_gpu": False
    }

    # Tarea 4: Inference (debe ser Hugging Face)
    tarea_inference = {
        "id": "task_inf_001",
        "type": "inference",
        "estimated_memory": 5 * 1024 * 1024 * 1024,  # 5 GB
        "estimated_time": 60,  # 1 minuto
        "requires_gpu": True
    }

    tareas = [
        ("Script Python", tarea_script),
        ("Modelo LLM", tarea_modelo),
        ("Automatización", tarea_automation),
        ("Inference", tarea_inference)
    ]

    resultados = []

    for nombre, tarea in tareas:
        print(f"Analizando: {nombre}")
        analysis = decision_engine.analizar_tarea(tarea)

        print(f"  Tipo: {analysis['tipo']}")
        print(f"  Memoria: {analysis['memoria_estimada'] / (1024**3):.2f} GB")
        print(f"  Tiempo estimado: {analysis['tiempo_estimado']} segundos")
        print(f"  Requiere GPU: {analysis['requiere_gpu']}")
        print(f"  Es grande: {analysis['es_grande']}")
        print(f"  Es rápida: {analysis['es_rapida']}")
        print(f"  → Recomendación: {'Hugging Face' if analysis['es_grande'] else 'Local'}")
        print()

        resultados.append({
            "nombre": nombre,
            "tipo": analysis['tipo'],
            "localizacion": "huggingface" if analysis['es_grande'] else "local",
            "razon": "Tarea compleja" if analysis['es_grande'] else "Tarea rápida"
        })

    return resultados

def test_decision_execution():
    """Prueba la ejecución de decisiones"""
    print("⚖️  Probando ejecución de decisiones...\n")

    # Tarea local
    tarea_local = {
        "id": "test_local",
        "type": "script",
        "estimated_memory": 100 * 1024 * 1024
    }

    # Tarea Hugging Face
    tarea_hf = {
        "id": "test_hf",
        "type": "llm",
        "estimated_memory": 6 * 1024 * 1024 * 1024,
        "requires_gpu": True
    }

    # Decidir sin ejecutar
    decision_local = decision_engine.decidir_procesamiento(tarea_local)
    decision_hf = decision_engine.decidir_procesamiento(tarea_hf)

    print("Decisión para tarea local:")
    print(f"  ID: {decision_local['tarea_id']}")
    print(f"  Localización: {decision_local['location']}")
    print(f"  Razón: {decision_local['reason']}")
    print(f"  Endpoint: {decision_local['endpoint']}")
    print()

    print("Decisión para tarea Hugging Face:")
    print(f"  ID: {decision_hf['tarea_id']}")
    print(f"  Localización: {decision_hf['location']}")
    print(f"  Razón: {decision_hf['reason']}")
    print(f"  Endpoint: {decision_hf['endpoint']}")
    print()

    return decision_local, decision_hf

def test_api_endpoints():
    """Prueba los endpoints de la API"""
    print("🌐 Probando endpoints de la API...\n")

    # Configurar URL base
    base_url = "http://localhost:5000"

    # Tarea de prueba
    test_task = {
        "task": {
            "id": "api_test_001",
            "type": "llm",
            "estimated_memory": 7 * 1024 * 1024 * 1024,
            "estimated_time": 90,
            "requires_gpu": True,
            "model": "mistral-7b"
        }
    }

    try:
        # Probar endpoint de análisis
        print("Probando /api/decision/analyze...")
        response = requests.post(
            f"{base_url}/api/decision/analyze",
            json=test_task,
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            print(f"  ✅ Éxito: {result['recommendation']}")
            print(f"  Tipo: {result['analysis']['tipo']}")
            print(f"  Es grande: {result['analysis']['es_grande']}")
        else:
            print(f"  ❌ Error {response.status_code}: {response.text}")

        print()

        # Probar endpoint de decisión
        print("Probando /api/decision/decide...")
        response = requests.post(
            f"{base_url}/api/decision/decide",
            json=test_task,
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            print(f"  ✅ Éxito: {result['decision']['location']}")
            print(f"  Razón: {result['decision']['reason']}")
        else:
            print(f"  ❌ Error {response.status_code}: {response.text}")

    except requests.RequestException as e:
        print(f"  ⚠️  No se pudo conectar al servidor: {str(e)}")
        print("  Asegúrate de que el servidor esté en ejecución")

    print()

def main():
    """Función principal de prueba"""
    print("🚀 Iniciando pruebas del motor de decisión inteligente")
    print("=" * 60)
    print()

    # Configurar variables de entorno
    from dotenv import load_dotenv
    load_dotenv()

    # Test 1: Análisis de tareas
    analysis_results = test_analisis_tareas()

    # Test 2: Decisión de ejecución
    decision_local, decision_hf = test_decision_execution()

    # Test 3: API endpoints
    test_api_endpoints()

    # Resumen
    print("📊 Resumen de pruebas:")
    print("=" * 60)

    local_count = sum(1 for r in analysis_results if r['localizacion'] == 'local')
    hf_count = len(analysis_results) - local_count

    print(f"Tareas analizadas: {len(analysis_results)}")
    print(f"  → Locales: {local_count}")
    print(f"  → Hugging Face: {hf_count}")
    print()
    print("Tipos de tareas detectados:")
    for r in analysis_results:
        print(f"  - {r['nombre']}: {r['localizacion']} ({r['razon']})")
    print()
    print("✅ Pruebas completadas")

if __name__ == "__main__":
    main()