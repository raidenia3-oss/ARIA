#!/usr/bin/env python3
"""
Hermes WebSocket Bridge
Expone Hermes Agent como WS en localhost:7777
La app AME se conecta y usa Hermes directamente
"""

import asyncio
import json
import subprocess
import sys

try:
    import websockets
except ImportError:
    print("Instalando websockets...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets"])
    import websockets

CLIENTS = set()
HERMES_AVAILABLE = True


def check_hermes():
    """Verifica si Hermes CLI está instalado"""
    global HERMES_AVAILABLE
    try:
        result = subprocess.run(["hermes", "--version"], capture_output=True, timeout=5)
        if result.returncode == 0:
            HERMES_AVAILABLE = True
            print(f"[Bridge] Hermes encontrado: {result.stdout.decode().strip()}")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Intentar con ollama como alternativa
    try:
        result = subprocess.run(["ollama", "--version"], capture_output=True, timeout=5)
        if result.returncode == 0:
            HERMES_AVAILABLE = True
            print("[Bridge] Usando Ollama como alternativa a Hermes")
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    HERMES_AVAILABLE = False
    print("[Bridge] Hermes no encontrado, usando respuestas de ejemplo")
    return False


async def handle_client(ws):
    """Maneja conexiones de la app AME"""
    CLIENTS.add(ws)
    print(f"[Bridge] App AME conectada ({len(CLIENTS)} clientes)")
    try:
        async for msg in ws:
            data = json.loads(msg)
            if data.get("type") == "message":
                response = await query_model(data["content"], data.get("model", "default"))
                await ws.send(json.dumps({
                    "type": "response",
                    "content": response,
                    "model": data.get("model", "hermes-local"),
                    "ts": asyncio.get_event_loop().time()
                }))
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        CLIENTS.discard(ws)
        print(f"[Bridge] App AME desconectada ({len(CLIENTS)} clientes)")


async def query_model(prompt, model="default"):
    """Consulta el modelo LLM local"""
    # Intentar con Hermes CLI
    if HERMES_AVAILABLE:
        try:
            proc = await asyncio.create_subprocess_exec(
                "hermes", "--once", prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            return stdout.decode().strip()
        except (asyncio.TimeoutError, FileNotFoundError):
            pass

        # Intentar con ollama
        try:
            proc = await asyncio.create_subprocess_exec(
                "ollama", "run", "hermes3", prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
            return stdout.decode().strip()
        except (asyncio.TimeoutError, FileNotFoundError):
            pass

    # Respuesta de ejemplo cuando Hermes no está disponible
    return (
        "Soy AME Agent (modo offline). Hermes no está disponible en este momento. "
        "Para usar el chat completo, instala Hermes o conecta OpenRouter desde la configuración.\n\n"
        f"Tu consulta fue: {prompt[:100]}..."
    )


async def main():
    print("╔══════════════════════════════════════════╗")
    print("║    Hermes WebSocket Bridge v1.0          ║")
    print("╚══════════════════════════════════════════╝")
    print("[Bridge] Iniciando en ws://localhost:7777")

    check_hermes()

    async with websockets.serve(handle_client, "localhost", 7777):
        print("[Bridge] Listo - esperando conexiones de AME app")
        print("[Bridge] Presiona Ctrl+C para detener")
        try:
            await asyncio.Future()  # Esperar indefinidamente
        except asyncio.CancelledError:
            print("[Bridge] Deteniendo...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Bridge] Detenido por el usuario")