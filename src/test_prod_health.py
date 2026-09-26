"""
test_prod_health.py — Ping rápido al backend de AURA en producción (Render).

Uso:
    python test_prod_health.py
    python test_prod_health.py https://tu-instancia.onrender.com

Sirve como "ping" para despertar la instancia gratuita de Render
cuando se va a dormir por inactividad, e imprime el estado HTTP y la
latencia de respuesta. No requiere dependencias externas (stdlib).
"""

from __future__ import annotations

import sys
import time
import urllib.error
import urllib.request

DEFAULT_URL = "https://aura-backend-qwhl.onrender.com"
HEALTH_PATH = "/health"
TIMEOUT = 60
LOOP_INTERVAL_SECONDS = 14 * 60  # 14 minutos: evita el cold-sleep del plan free


def ping(base_url: str) -> None:
    url = base_url.rstrip("/") + HEALTH_PATH
    print(f">>> Ping a AURA en: {url}")

    req = urllib.request.Request(url, headers={"User-Agent": "aura-health-ping/1.0"})
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            elapsed_ms = (time.perf_counter() - start) * 1000
            body = resp.read(4096).decode("utf-8", errors="replace")
            status = resp.getcode()
            print(f">>> HTTP {status}  |  {elapsed_ms:.0f} ms")
            if status == 200:
                print(f">>> OK: backend responde. Body: {body[:200]}")
            else:
                print(f">>> WARN: respuesta inesperada (no 200).")
    except urllib.error.HTTPError as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        print(f">>> HTTP {exc.code}  |  {elapsed_ms:.0f} ms  |  Error HTTP: {exc}")
    except Exception as exc:  # noqa: BLE001 - ping debe reportar sin crashear
        elapsed_ms = (time.perf_counter() - start) * 1000
        print(f">>> FAIL: no se pudo conectar ({elapsed_ms:.0f} ms): {exc}")


def loop(base_url: str) -> None:
    print(f">>> MODO BUCLE (keep-alive): ping cada 14 min a {base_url}")
    print(f">>> Ctrl+C para detener.")
    while True:
        ping(base_url)
        print(f">>> Próximo ping en {LOOP_INTERVAL_SECONDS // 60} min...")
        time.sleep(LOOP_INTERVAL_SECONDS)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--loop"]
    loop_mode = "--loop" in sys.argv[1:]
    target = args[0] if args else DEFAULT_URL
    if loop_mode:
        loop(target)
    else:
        ping(target)
