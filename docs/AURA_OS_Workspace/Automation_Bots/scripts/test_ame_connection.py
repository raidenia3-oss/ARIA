#!/usr/bin/env python3
"""
test_ame_connection.py — Verifica conexión de AME a AURA Core
Para ejecutar en Termux (Android) desde /sdcard/
"""

import os
import sys
import json
import time
import asyncio
import requests
from pathlib import Path
from datetime import datetime

# Configuración
AME_CONFIG_PATH = Path("/sdcard/ame_config.json")
CHECK_TIMEOUT = 10  # segundos
LOCAL_FALLBACK = "ws://192.168.1.100:8765"

def test_internet():
    """Verifica conexión a internet"""
    try:
        response = requests.get("https://1.1.1.1", timeout=5)
        return response.status_code == 200
    except Exception:
        return False

async def test_websocket(url):
    """Verifica conexión WebSocket"""
    try:
        import websockets
        async with websockets.connect(url, timeout=CHECK_TIMEOUT) as ws:
            # Enviar ping
            await ws.send(json.dumps({"node": "AME_TEST", "data": "ping"}))
            # Esperar respuesta
            response = await asyncio.wait_for(ws.recv(), timeout=CHECK_TIMEOUT)
            return True, response
    except Exception as e:
        return False, str(e)

def load_ame_config():
    """Carga la configuración de AME"""
    if not AME_CONFIG_PATH.exists():
        print("❌ Error: ame_config.json no encontrado en /sdcard/")
        return None

    try:
        with open(AME_CONFIG_PATH) as f:
            config = json.load(f)
        return config
    except Exception as e:
        print(f"❌ Error cargando config: {e}")
        return None

def print_connection_status(success, url, response=None):
    """Imprime el estado de conexión"""
    print("\n" + "="*50)
    print("  📱 CONEXIÓN AURA/AME")
    print("="*50)

    if success:
        print(f"  ✅ Conectado a AURA Core")
        print(f"  🔗 URL: {url}")
        if response:
            print(f"  📜 Respuesta: {response[:100]}...")
        print(f"  ⏱️  Latencia: {time.time() - start_time:.2f}s")
    else:
        print(f"  ❌ No se puede conectar a {url}")
        print(f"  🔍 Error: {response}")

    print("="*50)

def main():
    global start_time
    start_time = time.time()

    print("🔍 Iniciando prueba de conexión AME → AURA Core")
    print(f"📱 Ruta de config: {AME_CONFIG_PATH}")

    # Verificar internet
    if not test_internet():
        print("❌ Error: Sin conexión a internet")
        return

    # Cargar configuración
    config = load_ame_config()
    if not config:
        return

    # Obtener URL del EventBus
    eventbus_url = config.get("network", {}).get("eventbus_url", LOCAL_FALLBACK)
    print(f"🔗 URL de EventBus: {eventbus_url}")

    # Verificar conexión WebSocket
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    success, response = loop.run_until_complete(test_websocket(eventbus_url))
    loop.close()

    # Imprimir resultados
    print_connection_status(success, eventbus_url, response)

    # Guardar resultados en JSON
    results = {
        "timestamp": datetime.now().isoformat(),
        "internet": test_internet(),
        "config_path": str(AME_CONFIG_PATH),
        "eventbus_url": eventbus_url,
        "success": success,
        "response": response if isinstance(response, str) else str(response),
        "latency": time.time() - start_time
    }

    results_file = Path("/sdcard/ame_connection_test.json")
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n📄 Resultados guardados en: {results_file}")

    # Mensaje final
    if success:
        print("\n🎉 ¡Conexión exitosa! AME puede comunicarse con AURA Core")
        print("   Verifica que start_aura.py esté corriendo en la PC")
    else:
        print("\n⚠️  Conexión fallida. Revisa:")
        print("   1. Que start_aura.py esté corriendo en la PC")
        print("   2. Que el túnel Cloudflare esté activo")
        print("   3. Que no haya firewall bloqueando la conexión")

if __name__ == "__main__":
    main()