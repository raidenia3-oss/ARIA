"""
Test — Puente de Inferencia Local (Ollama)
Verifica que la API de Ollama responda en 127.0.0.1:11434
=======================================================
Ejecutar: python tests/test_local_router.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from neural.local_router import test_ollama_connection, LocalRouter


async def main():
    print("=" * 60)
    print("🧪 AURA — Test de Conexion Local (Ollama + FreeBuff)")
    print("=" * 60)

    # Test 1: Estado de conexion
    print("\n[1/3] Verificando conectividad con Ollama...")
    status = await test_ollama_connection()
    print(f"   Ollama disponible:  {'✅ SI' if status['ollama_available'] else '❌ NO'}")
    print(f"   FreeBuff en PATH:   {'✅ SI' if status['freebuff_available'] else '⚠️ NO'}")
    print(f"   Endpoint:           {status['ollama_endpoint']}")
    print(f"   Modelo por defecto: {status['model']}")

    if not status["ollama_available"]:
        print("\n   ⚠️  Ollama no esta corriendo. Inicia Ollama con:")
        print("      ollama serve")
        print("   Y luego descarga el modelo:")
        print("      ollama pull qwen2.5-coder:7b")
        return

    # Test 2: Chat basico
    print("\n[2/3] Enviando ping a Ollama...")
    router = LocalRouter()
    response = await router.chat("Responde solo con 'OK' en una palabra.")
    if response:
        print(f"   Respuesta: {response[:60]}...")
        print(f"   ✅ Chat funcionando")
    else:
        print("   ❌ No se recibio respuesta")

    # Test 3: Deteccion de refactorizacion
    print("\n[3/3] Probando deteccion de keywords de refactorizacion...")
    test_prompts = [
        ("refactoriza el modulo de autenticacion", True),
        ("Hola, como estas?", False),
        ("reescribe completamente el sistema de archivos", True),
        ("cual es el clima de hoy?", False),
    ]
    for prompt, expected in test_prompts:
        result = router._detect_refactor_keywords(prompt)
        icon = "✅" if result == expected else "❌"
        print(f"   {icon} '{prompt[:35]}...' -> refactor={result} (esperado={expected})")

    print("\n" + "=" * 60)
    print("✅ Test completado")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
