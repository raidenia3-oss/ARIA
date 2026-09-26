#!/usr/bin/env python3
"""
Hugging Face Connection Test Script
Prueba básica de conexión a la API de Hugging Face

Este script verifica que:
1. Las variables de entorno están configuradas correctamente
2. La API key es válida
3. Se puede establecer conexión con el endpoint configurado

Uso:
1. Configura tu API key en .env
2. Ejecuta: python test_hf_connection.py
"""

import os
import requests
import json
from dotenv import load_dotenv
from pathlib import Path

# Cargar variables de entorno
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

def test_huggingface_connection():
    """Prueba la conexión con Hugging Face API"""

    # Verificar variables de entorno
    api_key = os.getenv('HUGGINGFACE_API_KEY')
    space_url = os.getenv('HF_SPACE_URL')

    if not api_key or api_key == 'your_api_key_here':
        print("❌ ERROR: HUGGINGFACE_API_KEY no configurada o tiene valor por defecto")
        print(f"   Configura tu API key en {env_path}")
        return False

    if not space_url or space_url == 'https://your-space.hf.space':
        print("⚠️  ADVERTENCIA: HF_SPACE_URL no configurada o tiene valor por defecto")
        print("   Usando endpoint de prueba: https://api-inference.huggingface.co")
        space_url = "https://api-inference.huggingface.co"

    print(f"🔑 API Key: {'*' * len(api_key[:5]) + api_key[5:]}")
    print(f"🌐 Endpoint: {space_url}")

    # Configurar headers
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        # Probar con un modelo público de prueba
        test_model = "sentence-transformers/all-MiniLM-L6-v2"
        test_url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{test_model}"

        print(f"\n🧪 Probando conexión con modelo: {test_model}")

        # Datos de prueba
        test_data = {
            "inputs": "This is a test sentence",
            "options": {"wait_for_model": True}
        }

        # Hacer la petición
        response = requests.post(
            test_url,
            headers=headers,
            json=test_data,
            timeout=30
        )

        # Verificar respuesta
        if response.status_code == 200:
            print("✅ Conexión exitosa con Hugging Face API!")
            print(f"📦 Tamaño de respuesta: {len(response.content)} bytes")
            return True
        elif response.status_code == 503:
            print("⏳ Modelo en carga, esto es normal la primera vez")
            print("   Intenta nuevamente en 30 segundos")
            return False
        else:
            print(f"❌ Error {response.status_code}: {response.text[:200]}...")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Error de conexión: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {str(e)}")
        return False

def test_space_connection():
    """Prueba conexión con un Space específico de Hugging Face"""
    space_url = os.getenv('HF_SPACE_URL')

    if not space_url or space_url == 'https://your-space.hf.space':
        print("⚠️  No se puede probar Space URL sin configuración personalizada")
        return None

    print(f"\n🔗 Probando conexión con Space: {space_url}")

    try:
        # Intentar conexión básica (HEAD request para evitar procesamiento)
        response = requests.head(space_url, timeout=10)

        if response.status_code < 400:
            print(f"✅ Space accesible (código {response.status_code})")
            return True
        else:
            print(f"❌ Space no accesible (código {response.status_code})")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ No se pudo conectar con el Space: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 Iniciando prueba de conexión con Hugging Face")
    print("=" * 50)

    # Instalar dependencias si es necesario
    try:
        import requests
        from dotenv import load_dotenv
    except ImportError:
        print("⚠️  Instalando dependencias...")
        import subprocess
        subprocess.run(["pip", "install", "requests", "python-dotenv"], check=True)
        print("✅ Dependencias instaladas")

    # Ejecutar pruebas
    api_success = test_huggingface_connection()
    space_success = test_space_connection()

    print("\n" + "=" * 50)
    print("📋 Resumen de pruebas:")
    print(f"   API Connection: {'✅ PASSED' if api_success else '❌ FAILED'}")
    print(f"   Space Connection: {'✅ PASSED' if space_success else '⚠️  SKIPPED' if space_success is None else '❌ FAILED'}")

    if api_success:
        print("\n🎉 Configuración válida! Puedes usar Hugging Face API")
    else:
        print("\n🔧 Revisa tu configuración y intenta nuevamente")