"""
Puente entre RollerCoin y N8N para login automatico via Gmail.

Flujo:
  1. RollerCoin detecta sesion expirada
  2. Notifica a N8N via webhook
  3. N8N lee el codigo de Gmail y lo envia de vuelta
  4. RollerCoin recibe el codigo via WebSocket/EventBus
"""

import asyncio
import json
import os
import requests

# Webhook de N8N para solicitar lectura de codigo Gmail
N8N_WEBHOOK = os.environ.get(
    "N8N_ROLLERCOIN_WEBHOOK", "https://n8n-onme.onrender.com/webhook/rollercoin-login"
)

# URL del EventBus de AURA para recibir respuestas
AURA_WS = os.environ.get("AURA_WS_URL", "ws://localhost:8765")


async def notify_n8n_session_expired() -> bool:
    """
    Avisa a N8N que la sesion de RollerCoin expiro.
    N8N leera el correo de Gmail y extraera el codigo.
    """
    try:
        payload = {
            "event": "SESSION_EXPIRED",
            "email": os.environ.get("ROLLERCOIN_EMAIL", ""),
            "timestamp": asyncio.get_event_loop().time(),
        }
        respuesta = requests.post(N8N_WEBHOOK, json=payload, timeout=10)
        print(f"[N8N Bridge] Notificado: {respuesta.status_code}")
        return respuesta.status_code == 200
    except Exception as e:
        print(f"[N8N Bridge] Error notificando: {e}")
        return False


async def wait_for_code_from_aura(timeout: int = 120) -> str | None:
    """
    Espera que AURA EventBus reciba el codigo de Gmail
    que N8N extrajo y envio de vuelta.
    """
    import websockets

    try:
        async with websockets.connect(AURA_WS) as ws:
            # Avisar que estamos esperando codigo
            await ws.send(json.dumps({"node": "ROLLERCOIN_BOT", "event": "WAITING_LOGIN_CODE"}))

            inicio = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - inicio < timeout:
                try:
                    mensaje = await asyncio.wait_for(ws.recv(), timeout=5)
                    datos = json.loads(mensaje)
                    if datos.get("event") == "RC_LOGIN_CODE":
                        codigo = datos.get("payload", {}).get("code")
                        if codigo:
                            print(f"[N8N Bridge] Codigo recibido: {codigo}")
                            return codigo
                except asyncio.TimeoutError:
                    continue  # Timeout normal del wait_for
    except Exception as e:
        print(f"[N8N Bridge] Error esperando codigo: {e}")

    return None
