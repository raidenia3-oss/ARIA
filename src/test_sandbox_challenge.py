#!/usr/bin/env python3
"""Test script: Sandbox Challenge Live Execution.

Simula la inyección del desafío !libre y captura el flujo completo del
Sandbox con logging DEBUG en code_sandbox y agents_pool.
"""

import asyncio
import logging
import os
import sys
import time
from io import StringIO

# Fix Windows console encoding for emoji output.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# 1) Configurar logging DEBUG antes de importar módulos de AURA.
log_capture = StringIO()
handler = logging.StreamHandler(log_capture)
handler.setLevel(logging.DEBUG)
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

root = logging.getLogger()
root.setLevel(logging.DEBUG)
root.addHandler(handler)

# Forzar DEBUG en módulos críticos.
for mod_name in [
    "ame_backend.src.tools.code_sandbox",
    "ame_backend.src.tools.agents_pool",
    "ame_backend.src.tools.rocket_bridge",
    "ame_backend.src.tools.cron_scheduler",
]:
    logging.getLogger(mod_name).setLevel(logging.DEBUG)

# 2) Variables de entorno mínimas para cargar main.py sin errores.
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("GEMINI_MODEL", "gemini-2.0-flash-exp")
os.environ.setdefault("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
os.environ.setdefault("AI_PROVIDER_PREFERENCE", "auto")
os.environ.setdefault("ROCKET_CHAT_URL", "http://localhost:3000")
os.environ.setdefault("ROCKET_USER", "AuraBot")
os.environ.setdefault("ROCKET_PASSWORD", "test")
os.environ.setdefault("ROCKET_CHANNEL", "aura-core")
os.environ.setdefault("ROCKET_BOT_USERNAME", "aura.bot")
os.environ.setdefault("DISCORD_TOKEN", "test-discord-token")
os.environ.setdefault("DISCORD_ALERT_CHANNEL_ID", "123456")
os.environ.setdefault("MESH_KEY", "aura-mesh-secret")
os.environ.setdefault("SWARM_TOKEN", "aura-swarm-secret")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("JWT_SECRET_ADMIN", "test-jwt-admin-secret")
os.environ.setdefault("BRIDGE_SECRET", "test-bridge-secret")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ame_backend", "src"))

# 3) Importar módulos de AURA.
from ame_backend.src.services.ai_engine import AIEngine
from ame_backend.src.tools.multi_model_router import MultiModelRouter
from ame_backend.src.tools.rocket_bridge import RocketChatBridge


async def main() -> None:
    print("=" * 70)
    print("IGNICIÓN DEL SANDBOX EN VIVO — DESAFÍO MATEMÁTICO COMPLEJO")
    print("=" * 70)
    print()

    ai = AIEngine()
    router = MultiModelRouter(ai)
    bridge = RocketChatBridge(ai, router)

    challenge = (
        "!libre Escribe un script eficiente para calcular la suma de los "
        "primeros 500 números primos y dime exactamente cuál es el número "
        "primo número 500 en la secuencia."
    )

    print(f"[INPUT] Mensaje interceptado en #aura-core:\n  {challenge}\n")
    print("-" * 70)

    # Limpiar captura de logs previa.
    log_capture.truncate(0)
    log_capture.seek(0)

    start = time.perf_counter()
    result = await bridge._handle_computation_challenge(challenge)
    elapsed = time.perf_counter() - start

    print("-" * 70)
    print(f"[TIEMPO] Ejecución Sandbox: {elapsed:.3f}s\n")

    if result:
        print("[RESULTADO SANDBOX]:")
        print(result)
    else:
        print("[RESULTADO SANDBOX]: None (no detectado como reto computacional)")

    print()
    print("=" * 70)
    print("DUMP DE LOGS (DEBUG — code_sandbox + agents_pool + rocket_bridge)")
    print("=" * 70)
    logs = log_capture.getvalue()
    if logs:
        # Filtrar solo líneas relevantes para no saturar.
        relevant = []
        for line in logs.splitlines():
            low = line.lower()
            if any(k in low for k in [
                "sandbox", "execute_code", "subproceso", "detectada tool",
                "script python temporal", "success", "stdout", "computation",
                "agents_pool", "code_sandbox", "rocket_bridge", "cron",
            ]):
                relevant.append(line)
        if relevant:
            print("\n".join(relevant))
        else:
            print(logs)
    else:
        print("(sin logs capturados)")


if __name__ == "__main__":
    asyncio.run(main())
