"""
AURA Health Checker — check_health.py
Verifica que Ollama esté respondiendo en localhost:11434.
Reintenta cada 10 segundos hasta que la API responda OK.
Útil como rutina de 'wait-for-service' en scripts de arranque.
"""
import urllib.request
import urllib.error
import json
import sys
import time
import socket

OLLAMA_URL = "http://localhost:11434/api/tags"  # GET ligero
RETRY_DELAY = 10  # segundos
MAX_RETRIES = 60  # ~10 minutos máximo de espera


def check_ollama():
    """
    Intenta conectar con Ollama.
    Returns: True si responde, False si falla.
    """
    try:
        req = urllib.request.Request(
            OLLAMA_URL,
            method="GET",
            headers={"User-Agent": "AURA-HealthCheck/1.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                return True
            return False
    except (urllib.error.URLError, urllib.error.HTTPError,
            ConnectionRefusedError, socket.timeout, OSError):
        return False


def wait_for_ollama():
    """
    Bucle de reintento. Sale con código 0 si OK, 1 si timeout.
    """
    print(f"🔍 [AURA Health] Verificando Ollama en {OLLAMA_URL}...")
    print(f"⏱  Reintentando cada {RETRY_DELAY}s (máx {MAX_RETRIES} intentos)")
    print()

    for attempt in range(1, MAX_RETRIES + 1):
        if check_ollama():
            print(f"✅ [AURA Health] Ollama RESPONDE correctamente (intento {attempt})")
            return True

        print(f"  ⏳ Intento {attempt}/{MAX_RETRIES} — Ollama no disponible, reintentando en {RETRY_DELAY}s...")
        time.sleep(RETRY_DELAY)

    print(f"❌ [AURA Health] TIMEOUT: Ollama no respondió tras {MAX_RETRIES * RETRY_DELAY}s")
    return False


if __name__ == "__main__":
    success = wait_for_ollama()
    sys.exit(0 if success else 1)