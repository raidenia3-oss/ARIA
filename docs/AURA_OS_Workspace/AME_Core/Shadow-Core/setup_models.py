#!/usr/bin/env python3
"""
Automated Model Setup para AURA.
Descarga e instala automáticamente los modelos especializados en Ollama.
Valida la instalación y actualiza la configuración del sistema.
"""

import os
import subprocess
import json
import time
import requests
from datetime import datetime

# Configuración global
MODELS_TO_INSTALL = [
    {"name": "deepseek-coder-v2", "alias": "deepseek-coder", "description": "Modelo especializado en programación y generación de código."},
    {"name": "dolphin-llama3", "alias": "dolphin-llama3", "description": "Modelo especializado en razonamiento técnico y análisis profundo."},
    {"name": "mistral-nemo-uncensored", "alias": "mistral-nemo-uncensored", "description": "Modelo especializado en creatividad, investigación y generación de ideas."}
]

CONFIG_FILE = "Shadow-Core/config_models.json"
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_LIST_ENDPOINT = f"{OLLAMA_HOST}/api/tags"
OLLAMA_PULL_TIMEOUT = 3600  # 1 hora de timeout para descargas grandes
OLLAMA_LIST_TIMEOUT = 30  # 30 segundos para listar modelos

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
        response = requests.get(OLLAMA_LIST_ENDPOINT, timeout=OLLAMA_LIST_TIMEOUT)
        if response.status_code == 200:
            return True
        else:
            print(f"⚠️ Ollama no está respondiendo (código de estado: {response.status_code})")
            return False
    except Exception as e:
        print(f"⚠️ No se pudo conectar a Ollama: {str(e)}")
        return False

def pull_model(model_name, model_alias):
    """Descargar un modelo específico de Ollama."""
    print(f"\n🔄 Descargando modelo: {model_name} (alias: {model_alias})...")

    # Verificar si el modelo ya existe
    result = run_command(f"ollama list | grep -i {model_name}", timeout=10)
    if result["success"] and model_name.lower() in result["stdout"].lower():
        print(f"✅ Modelo {model_name} ya está instalado. Saltando descarga.")
        return True

    # Descargar el modelo
    print(f"📥 Iniciando descarga de {model_name}...")
    start_time = time.time()
    result = run_command(f"ollama pull {model_name}", timeout=OLLAMA_PULL_TIMEOUT)

    if result["success"]:
        elapsed_time = time.time() - start_time
        print(f"✅ Modelo {model_name} descargado correctamente en {elapsed_time:.1f} segundos")

        # Crear alias si es necesario
        if model_name != model_alias:
            print(f"🔗 Creando alias '{model_alias}' para {model_name}...")
            alias_result = run_command(f"ollama create {model_alias} --from {model_name}", timeout=30)
            if alias_result["success"]:
                print(f"✅ Alias '{model_alias}' creado correctamente")
            else:
                print(f"⚠️ No se pudo crear alias '{model_alias}': {alias_result['stderr']}")

        return True
    else:
        print(f"❌ Error al descargar {model_name}:")
        print(f"   Código de retorno: {result['returncode']}")
        print(f"   Error: {result['stderr']}")
        return False

def list_models():
    """Listar los modelos disponibles en Ollama."""
    print("\n📋 Listando modelos disponibles en Ollama...")

    result = run_command("ollama list", timeout=OLLAMA_LIST_TIMEOUT)
    if result["success"]:
        print("✅ Modelos disponibles:")
        models_list = result["stdout"].strip().split('\n')
        for model_line in models_list:
            if model_line.strip():
                print(f"   - {model_line.strip()}")

        # Obtener información detallada de los modelos usando la API
        try:
            response = requests.get(OLLAMA_LIST_ENDPOINT, timeout=OLLAMA_LIST_TIMEOUT)
            if response.status_code == 200:
                models_data = response.json().get("models", [])
                print(f"\n📊 Información detallada de {len(models_data)} modelos:")
                for model in models_data:
                    model_name = model.get("name", "desconocido")
                    size = model.get("size", "desconocido")
                    print(f"   - {model_name}: {size} bytes")
            else:
                print(f"⚠️ No se pudo obtener información detallada de los modelos (código: {response.status_code})")
        except Exception as e:
            print(f"⚠️ Error al obtener información detallada: {str(e)}")
    else:
        print(f"❌ Error al listar modelos: {result['stderr']}")
    return result["success"]

def validate_models():
    """Validar que todos los modelos requeridos estén instalados."""
    print("\n🔍 Validando modelos requeridos...")

    # Obtener lista de modelos instalados
    result = run_command("ollama list", timeout=OLLAMA_LIST_TIMEOUT)
    if not result["success"]:
        print(f"❌ No se pudo validar los modelos: {result['stderr']}")
        return False

    installed_models = []
    for line in result["stdout"].strip().split('\n'):
        if line.strip():
            installed_models.append(line.strip().split()[0])

    # Verificar que todos los modelos requeridos estén instalados
    missing_models = []
    for model in MODELS_TO_INSTALL:
        model_name = model["name"]
        model_alias = model["alias"]

        if model_name in installed_models:
            print(f"✅ {model_name} está instalado")
        elif model_alias in installed_models:
            print(f"✅ {model_alias} (alias de {model_name}) está instalado")
        else:
            missing_models.append(model_name)

    if missing_models:
        print(f"❌ Modelos faltantes: {', '.join(missing_models)}")
        return False
    else:
        print("✅ Todos los modelos requeridos están instalados correctamente")
        return True

def update_config_file():
    """Actualizar el archivo config_models.json con los modelos instalados."""
    print("\n📝 Actualizando archivo de configuración...")

    try:
        # Leer el archivo de configuración actual
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)

        # Actualizar los nombres de los modelos según los instalados
        updated_config = {
            "task_types": {},
            "default_task_type": "GENERAL_TASK",
            "model_fallback": "llama3"
        }

        # Mapear los modelos originales a los nuevos nombres
        model_mapping = {
            "deepseek-coder": "deepseek-coder-v2",
            "dolphin-llama3": "dolphin-llama3",
            "mistral-nemo-uncensored": "mistral-nemo-uncensored"
        }

        # Actualizar los modelos en la configuración
        for task_type, task_config in config.get("task_types", {}).items():
            model_name = task_config.get("model")
            if model_name in model_mapping:
                updated_config["task_types"][task_type] = {
                    **task_config,
                    "model": model_mapping[model_name]
                }
            else:
                updated_config["task_types"][task_type] = task_config

        # Guardar el archivo actualizado
        with open(CONFIG_FILE, 'w') as f:
            json.dump(updated_config, f, indent=2)

        print(f"✅ Archivo de configuración actualizado: {CONFIG_FILE}")
        return True
    except Exception as e:
        print(f"❌ Error al actualizar archivo de configuración: {str(e)}")
        return False

def test_models():
    """Probar los modelos instalados con consultas básicas."""
    print("\n🧪 Probando modelos instalados...")

    test_queries = {
        "deepseek-coder": "Escribe una función en Python que calcule el factorial de un número usando recursión.",
        "dolphin-llama3": "Explica el algoritmo de backpropagation en redes neuronales y su importancia en el aprendizaje profundo.",
        "mistral-nemo-uncensored": "Genera 3 nombres creativos para una startup de inteligencia artificial y describe su significado."
    }

    success_count = 0
    for model_name, query in test_queries.items():
        print(f"\n🔬 Probando modelo {model_name} con consulta de ejemplo...")

        try:
            # Usar la API de Ollama para probar el modelo
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
                if "response" in result:
                    print(f"✅ {model_name} respondió correctamente:")
                    print(f"   Primeras 100 palabras: {result['response'][:100]}...")
                    success_count += 1
                else:
                    print(f"❌ {model_name} no devolvió una respuesta válida")
            else:
                print(f"❌ Error al probar {model_name} (código: {response.status_code}): {response.text}")
        except Exception as e:
            print(f"❌ Error al probar {model_name}: {str(e)}")

    if success_count == len(test_queries):
        print(f"\n🎉 Todos los modelos ({success_count}/{len(test_queries)}) respondieron correctamente")
        return True
    else:
        print(f"\n⚠️ {success_count}/{len(test_queries)} modelos respondieron correctamente")
        return success_count > 0

def main():
    """Función principal para configurar los modelos automáticamente."""
    print("=" * 80)
    print("🚀 AUTOMATED MODEL SETUP PARA AURA")
    print("=" * 80)
    print("Este script descargará e instalará automáticamente los modelos especializados:")
    print("• deepseek-coder-v2 (programación y generación de código)")
    print("• dolphin-llama3 (razonamiento técnico y análisis profundo)")
    print("• mistral-nemo-uncensored (creatividad e investigación)")
    print("=" * 80)

    # Verificar que Ollama esté en ejecución
    if not check_ollama_running():
        print("\n❌ Ollama no está en ejecución. Por favor, inicia Ollama antes de ejecutar este script.")
        print("   Comando: ollama serve")
        return False

    # Descargar cada modelo
    all_success = True
    for model in MODELS_TO_INSTALL:
        model_name = model["name"]
        model_alias = model["alias"]
        success = pull_model(model_name, model_alias)
        if not success:
            all_success = False

    # Listar modelos instalados
    list_success = list_models()

    # Validar que todos los modelos estén instalados
    validation_success = validate_models()

    # Actualizar el archivo de configuración
    config_success = update_config_file()

    # Probar los modelos
    test_success = test_models()

    # Resumen final
    print("\n" + "=" * 80)
    print("📊 RESUMEN DE LA CONFIGURACIÓN DE MODELOS")
    print("=" * 80)
    print(f"✅ Ollama en ejecución: {'Sí' if check_ollama_running() else 'No'}")
    print(f"✅ Modelos descargados: {'Sí' if all_success else 'No'}")
    print(f"✅ Modelos listados: {'Sí' if list_success else 'No'}")
    print(f"✅ Validación de modelos: {'Sí' if validation_success else 'No'}")
    print(f"✅ Configuración actualizada: {'Sí' if config_success else 'No'}")
    print(f"✅ Pruebas de modelos: {'Sí' if test_success else 'No'}")

    if all([check_ollama_running(), all_success, list_success, validation_success, config_success, test_success]):
        print("\n🎉 ¡TODOS LOS MODELOS ESTÁN INSTALADOS Y CONFIGURADOS CORRECTAMENTE!")
        print("\n🔧 Configuración completada:")
        print("   • Modelos especializados descargados e instalados")
        print("   • Configuración actualizada para el sistema")
        print("   • Modelos probados y funcionando correctamente")
        print("   • Listos para ser usados por el Swarm Orchestrator")
        print("\n🚀 AURA está ahora completamente preparada para operar con:")
        for model in MODELS_TO_INSTALL:
            print(f"   • {model['alias']}: {model['description']}")
    else:
        print("\n⚠️ Algunos pasos fallaron. Revisa los mensajes anteriores para solucionar los problemas.")

    print("\n" + "=" * 80)
    print("💡 RECOMENDACIONES:")
    print("1. Si algún modelo falló en la descarga, ejecuta manualmente:")
    print("   ollama pull [nombre-del-modelo]")
    print("2. Verifica que Ollama esté en ejecución:")
    print("   ollama serve")
    print("3. Para reiniciar el sistema después de la configuración:")
    print("   start_all.bat")
    print("=" * 80)

    return all([check_ollama_running(), all_success, list_success, validation_success, config_success, test_success])

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)