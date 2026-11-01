# -*- coding: utf-8 -*-
"""Puente de control remoto por Discord para ARIA (proceso aparte, sin GUI).

Uso: define ARIA_DISCORD_TOKEN y ARIA_DISCORD_USERS, luego:
    python aria_discord.py
ARIA responde a tus mensajes de Discord usando su cerebro local.
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
    res, _ = iniciar(_brain_responder())
    print("[ARIA-Discord]", res, flush=True)
    if not res.get("ok"):
        return
    print("Control remoto activo. Ctrl+C para salir.", flush=True)
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
