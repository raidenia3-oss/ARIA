# -*- coding: utf-8 -*-
"""Puente de control remoto por Discord para ARIA (proceso aparte, sin GUI).

Responde solo a mensajes que empiecen con "aria ", usa el mismo canal que
ASAGI y aplica el mismo anti-bucle (maximo 1 respuesta por minuto y 6 por
hora). Discord nunca ejecuta herramientas de ARIA.

Uso: define ARIA_DISCORD_TOKEN y ARIA_DISCORD_USERS (y opcional
ARIA_DISCORD_CHANNEL_ID), luego:
    python aria_discord.py
"""
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

from remote_discord import iniciar  # noqa: E402


def _brain_responder():
    import aria_va_core
    brain = aria_va_core.LocalAIBrain()

    def responder(texto):
        try:
            return brain.chat(texto).get("response", "...")
        except Exception as exc:
            return "error: %s" % exc
    return responder


def main():
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(AQUI, ".env"))
    except Exception:
        pass
    prefijo = os.environ.get("ARIA_DISCORD_PREFIX", "aria").strip()
    canal_id = os.environ.get("ARIA_DISCORD_CHANNEL_ID", "").strip() or None
    res, _ = iniciar(_brain_responder(), prefijo=prefijo, canal_id=canal_id)
    print("[ARIA-Discord]", res, flush=True)
    if not res.get("ok"):
        return
    print("Control remoto activo. Ctrl+C para salir.", flush=True)
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
