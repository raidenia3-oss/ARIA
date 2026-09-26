#!/usr/bin/env python3
"""
Verify Models para AURA.
Verifica que los modelos estén correctamente instalados y configurados.
"""

import os
import subprocess
import json
import requests
from datetime import datetime

# Configuración global
MODELS_CONFIG_FILE = "Shadow-Core/config_models.json"
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_LIST_ENDPOINT = f"{OLLAMA_HOST}/api/tags"
OLLAMA_TEST_QUERIES = {
    "deepseek-coder-v2": "Escribe una función en Python que calcule el factorial de un número usando recursión.",
    "dolphin-llama3": "Explica el algoritmo de backpropagation en redes neuronales y su importancia en el aprendizaje profundo.",
    "mistral-nemo-uncensored": "Genera 3 nombres creativos para una startup de inteligencia artificial y describe su significado."
}

def run_command(command, timeout=None, capture_output=True, text=True):
    """Ejecutar un comando en la terminal y devolver el resultado."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            timeout=timeout,
            capture_output=capture_output,
            text=text
        )
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"Timeout de {timeout} segundos excedido"
        }
    except Exception as e:
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"Error al ejecutar comando: {str(e)}"
        }

def check_ollama_running():
    """Verificar si Ollama está en ejecución."""
    try:
        response = requests.get(OLLAMA_LIST_ENDPOINT, timeout=30)
        if response.status_code == 200:
            return True
        else:
            print(f"⚠️ Ollama no está respondiendo (código de estado: {response.status_code})")
            return False
    except Exception as e:
        print(f"⚠️ No se pudo conectar a Ollama: {str(e)}")
        return False

def list_installed_models():
    """Listar los modelos instalados en Ollama."""
    print("\n📋 Listando modelos instalados en Ollama...")

    result = run_command("ollama list", timeout=30)
    if result["success"]:
        models_list = result["stdout"].strip().split('\n')
        installed_models = []
        for model_line in models_list:
            if model_line.strip():
                parts = model_line.strip().split()
                if len(parts) > 0:
                    installed_models.append(parts[0])

        print(f"✅ Modelos instalados ({len(installed_models)}):")
        for model in installed_models:
            print(f"   - {model}")

        return installed_models
    else:
        print(f"❌ Error al listar modelos: {result['stderr']}")
        return []

def get_model_info_from_api():
    """Obtener información detallada de los modelos usando la API de Ollama."""
    try:
        response = requests.get(OLLAMA_LIST_ENDPOINT, timeout=30)
        if response.status_code == 200:
            models_data = response.json().get("models", [])
            print(f"\n📊 Información detallada de {len(models_data)} modelos:")
            for model in models_data:
                model_name = model.get("name", "desconocido")
                size = model.get("size", "desconocido")
                print(f"   - {model_name}: {size} bytes")
            return models_data
        else:
            print(f"⚠️ No se pudo obtener información detallada de los modelos (código: {response.status_code})")
            return []
    except Exception as e:
        print(f"⚠️ Error al obtener información detallada: {str(e)}")
        return []

def load_config_file():
    """Cargar el archivo de configuración de modelos."""
    try:
        with open(MODELS_CONFIG_FILE, 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        print(f"❌ Error al cargar archivo de configuración: {str(e)}")
        return None

def verify_config_models():
    """Verificar que los modelos en la configuración existan en Ollama."""
    config = load_config_file()
    if not config:
        return False

    installed_models = list_installed_models()
    if not installed_models:
        return False

    print(f"\n🔍 Verificando configuración de modelos...")

    issues_found = False
    for task_type, task_config in config.get("task_types", {}).items():
        model_name = task_config.get("model")
        if model_name and model_name not in installed_models:
            print(f"❌ Modelo '{model_name}' configurado en '{task_type}' NO está instalado")
            issues_found = True
        else:
            print(f"✅ Modelo '{model_name}' configurado en '{task_type}' está instalado")

    if not issues_found:
        print("✅ Todos los modelos configurados están instalados correctamente")

    return not issues_found

def test_model(model_name, query):
    """Probar un modelo con una consulta de ejemplo."""
    print(f"\n🧪 Probando modelo {model_name}...")

    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": model_name,
                "prompt": query,
                "stream": False
            },
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            if "response" in result and result["response"]:
                print(f"✅ {model_name} respondió correctamente:")
                print(f"   Primeras 100 palabras: {result['response'][:100]}...")
                return True
            else:
                print(f"❌ {model_name} no devolvió una respuesta válida")
                return False
        else:
            print(f"❌ Error al probar {model_name} (código: {response.status_code}): {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error al probar {model_name}: {str(e)}")
        return False

def test_all_models():
    """Probar todos los modelos con consultas de ejemplo."""
    print("\n🧪 Probando todos los modelos instalados...")

    installed_models = list_installed_models()
    if not installed_models:
        return False

    success_count = 0
    for model_name in installed_models:
        if model_name in OLLAMA_TEST_QUERIES:
            query = OLLAMA_TEST_QUERIES[model_name]
            if test_model(model_name, query):
                success_count += 1
        else:
            # Intento con una consulta genérica si no hay consulta específica
            generic_query = f"Explica brevemente qué es {model_name} y para qué sirve."
            if test_model(model_name, generic_query):
                success_count += 1

    print(f"\n📊 Resultados de las pruebas:")
    print(f"   Modelos probados: {len(installed_models)}")
    print(f"   Modelos exitosos: {success_count}")
    print(f"   Modelos fallidos: {len(installed_models) - success_count}")

    return success_count == len(installed_models)

def verify_model_sizes():
    """Verificar que los modelos tengan tamaños razonables."""
    models_data = get_model_info_from_api()
    if not models_data:
        return False

    print(f"\n📏 Verificando tamaños de los modelos...")

    issues_found = False
    for model in models_data:
        model_name = model.get("name", "desconocido")
        size = model.get("size", 0)

        # Convertir tamaño a GB para comparación
        size_gb = size / (1024 ** 3)

        if size_gb < 1:  # Modelos demasiado pequeños (probablemente corruptos)
            print(f"⚠️ Modelo {model_name} tiene un tamaño inusualmente pequeño: {size_gb:.2f} GB")
            issues_found = True
        elif size_gb > 50:  # Modelos demasiado grandes (posible error en la descarga)
            print(f"⚠️ Modelo {model_name} tiene un tamaño inusualmente grande: {size_gb:.2f} GB")
            issues_found = True
        else:
            print(f"✅ Modelo {model_name}: {size_gb:.2f} GB (tamaño razonable)")

    if not issues_found:
        print("✅ Todos los modelos tienen tamaños razonables")

    return not issues_found

def main():
    """Función principal para verificar los modelos."""
    print("=" * 80)
    print("🔍 VERIFICACIÓN DE MODELOS PARA AURA")
    print("=" * 80)
    print("Este script verifica que los modelos estén correctamente instalados y configurados.")
    print("=" * 80)

    # Verificar que Ollama esté en ejecución
    if not check_ollama_running():
        print("\n❌ Ollama no está en ejecución. Por favor, inicia Ollama antes de continuar.")
        print("   Comando: ollama serve")
        return False

    # Listar modelos instalados
    installed_models = list_installed_models()
    if not installed_models:
        print("\n❌ No se encontraron modelos instalados.")
        return False

    # Obtener información detallada de los modelos
    get_model_info_from_api()

    # Verificar la configuración de modelos
    config_ok = verify_config_models()

    # Probar los modelos
    test_ok = test_all_models()

    # Verificar tamaños de los modelos
    size_ok = verify_model_sizes()

    # Resumen final
    print("\n" + "=" * 80)
    print("📊 RESUMEN DE LA VERIFICACIÓN")
    print("=" * 80)
    print(f"✅ Ollama en ejecución: {'Sí' if check_ollama_running() else 'No'}")
    print(f"✅ Modelos instalados: {len(installed_models)}")
    print(f"✅ Configuración válida: {'Sí' if config_ok else 'No'}")
    print(f"✅ Pruebas de modelos: {'Sí' if test_ok else 'No'}")
    print(f"✅ Tamaños razonables: {'Sí' if size_ok else 'No'}")

    all_ok = check_ollama_running() and len(installed_models) > 0 and config_ok and test_ok and size_ok

    if all_ok:
        print("\n🎉 ¡TODOS LOS MODELOS ESTÁN CORRECTAMENTE INSTALADOS Y CONFIGURADOS!")
        print("\n🔧 Estado actual:")
        for model in installed_models:
            print(f"   • {model}: ✅ Listo para uso")

        print("\n🚀 AURA está completamente preparada para operar con:")
        print("   • Modelos especializados instalados")
        print("   • Configuración correcta")
        print("   • Modelos funcionando correctamente")
        print("   • Tamaños de modelos razonables")
    else:
        print("\n⚠️ Algunos problemas fueron detectados. Revisa los mensajes anteriores.")
        print("\n🔧 Recomendaciones:")
        if not check_ollama_running():
            print("   1. Inicia Ollama: ollama serve")
        if not config_ok:
            print("   2. Verifica la configuración: python Shadow-Core/setup_models.py")
        if not test_ok:
            print("   3. Prueba manualmente los modelos:")
            for model in installed_models:
                print(f"      ollama run {model}")
        if not size_ok:
            print("   4. Verifica los tamaños de los modelos:")
            print("      ollama list")

    print("\n" + "=" * 80)
    print("💡 Para reiniciar el sistema después de solucionar problemas:")
    print("   start_all.bat")
    print("=" * 80)

    return all_ok

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)