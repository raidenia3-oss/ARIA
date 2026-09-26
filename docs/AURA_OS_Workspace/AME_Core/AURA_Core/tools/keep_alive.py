"""
AURA_Core/tools/keep_alive.py
Script de heartbeat automático para evitar que servidores gratuitos o locales entren en
modo de suspensión (anti-sleep). Basado en la técnica de ping rápido cada 5 minutos.

Envía pings a:
  - Instancia de N8N (local o remota)
  - Servicios esenciales de AURA Core (HF Space, API propia)

USO:
  python -m AURA_Core.tools.keep_alive        # Un solo ciclo
  python -m AURA_Core.tools.keep_alive --loop  # Loop infinito cada 5 min
"""

import os
import sys
import time
import json
import logging
import argparse
from typing import Dict, Any
from datetime import datetime

try:
    import requests

    _HAVE_REQUESTS = True
except ImportError:
    _HAVE_REQUESTS = False

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("keep_alive.log"),
    ],
)
logger = logging.getLogger("KeepAlive")

# Intervalo por defecto: 5 minutos
DEFAULT_INTERVAL = 300  # segundos


class KeepAliveService:
    """
    Servicio de heartbeat que mantiene activos los endpoints críticos de AURA.
    """

    def __init__(self, interval: int = DEFAULT_INTERVAL):
        self.interval = interval
        self.services = self._build_service_list()
        self.stats: Dict[str, Dict[str, Any]] = {}

    def _build_service_list(self) -> list:
        """Construye la lista de servicios a monitorear desde variables de entorno."""
        services = []

        # 1. N8N
        n8n_url = os.environ.get("N8N_BASE_URL", "http://localhost:5678")
        services.append(
            {
                "name": "n8n",
                "url": f"{n8n_url.rstrip('/')}/healthz",
                "timeout": 5,
            }
        )

        # 2. HF Space
        hf_url = os.environ.get("HF_SPACE_URL", "https://raiden456-slut.hf.space/v1")
        services.append(
            {
                "name": "hf_space",
                "url": f"{hf_url.rstrip('/')}/models",
                "timeout": 10,
            }
        )

        # 3. OpenRouter (solo health check básico)
        or_key = os.environ.get("OPENROUTER_API_KEY", "")
        if or_key:
            services.append(
                {
                    "name": "openrouter",
                    "url": "https://openrouter.ai/api/v1/models",
                    "timeout": 10,
                    "headers": {"Authorization": f"Bearer {or_key}"},
                }
            )

        # 4. LM Studio
        lm_url = os.environ.get("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")
        services.append(
            {
                "name": "lm_studio",
                "url": f"{lm_url.rstrip('/')}/models",
                "timeout": 5,
            }
        )

        # 5. API propia de AURA Core
        aura_api = os.environ.get("AURA_API_URL", "http://localhost:8000")
        services.append(
            {
                "name": "aura_api",
                "url": f"{aura_api.rstrip('/')}/health",
                "timeout": 5,
            }
        )

        # 6. FastAPI Docs / Root (fallback si no hay /health)
        services.append(
            {
                "name": "aura_api_root",
                "url": f"{os.environ.get('AURA_API_URL', 'http://localhost:8000').rstrip('/')}/",
                "timeout": 5,
            }
        )

        return services

    def ping_all(self) -> Dict[str, Any]:
        """Ejecuta ping a todos los servicios registrados."""
        if not _HAVE_REQUESTS:
            logger.error("requests no está instalado. No se puede ejecutar keep_alive.")
            return {"status": "error", "message": "requests not available"}

        results = {}
        for svc in self.services:
            name = svc["name"]
            url = svc["url"]
            timeout = svc.get("timeout", 5)
            headers = svc.get("headers", {})
            headers.setdefault("User-Agent", "AURA-KeepAlive/1.0")

            start = time.time()
            try:
                r = requests.get(url, headers=headers, timeout=timeout)
                elapsed = round(time.time() - start, 3)
                status = "alive" if r.status_code < 500 else "degraded"
                results[name] = {
                    "status": status,
                    "http_code": r.status_code,
                    "latency_ms": elapsed,
                }
                if status == "alive":
                    logger.debug(f"[{name}] OK ({elapsed}s) HTTP {r.status_code}")
                else:
                    logger.warning(f"[{name}] DEGRADED HTTP {r.status_code} ({elapsed}s)")
            except requests.ConnectionError:
                elapsed = round(time.time() - start, 3)
                results[name] = {"status": "unreachable", "latency_ms": elapsed}
                logger.warning(f"[{name}] UNREACHABLE ({elapsed}s)")
            except requests.Timeout:
                elapsed = round(time.time() - start, 3)
                results[name] = {"status": "timeout", "latency_ms": elapsed}
                logger.warning(f"[{name}] TIMEOUT after {timeout}s")
            except Exception as e:
                elapsed = round(time.time() - start, 3)
                results[name] = {"status": "error", "message": str(e), "latency_ms": elapsed}
                logger.error(f"[{name}] ERROR: {e}")

        # Resumen general
        alive_count = sum(1 for v in results.values() if v.get("status") == "alive")
        total = len(results)
        summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_services": total,
            "alive": alive_count,
            "degraded_or_dead": total - alive_count,
            "details": results,
        }

        logger.info(
            f"Heartbeat completo: {alive_count}/{total} servicios operativos. "
            f"{total - alive_count} con problemas."
        )

        return summary

    def run_once(self) -> Dict[str, Any]:
        """Ejecuta un único ciclo de heartbeat y retorna resultados."""
        logger.info("=" * 50)
        logger.info("Iniciando ciclo de KeepAlive...")
        return self.ping_all()

    def run_loop(self):
        """Ejecuta el heartbeat en bucle infinito."""
        logger.info(f"Iniciando loop KeepAlive cada {self.interval}s")
        cycle = 0
        while True:
            cycle += 1
            logger.info(f"Ciclo #{cycle}")
            results = self.run_once()

            # Loggear resultados a archivo JSON para diagnóstico
            try:
                log_file = "keep_alive_history.json"
                history = []
                if os.path.exists(log_file):
                    with open(log_file) as f:
                        history = json.load(f)
                history.append(results)
                # Mantener solo los últimos 100 registros
                if len(history) > 100:
                    history = history[-100:]
                with open(log_file, "w") as f:
                    json.dump(history, f, indent=2)
            except Exception as e:
                logger.error(f"Error guardando historial: {e}")

            # Notificar a N8N sobre el estado si está disponible
            self._notify_n8n(results)

            time.sleep(self.interval)

    def _notify_n8n(self, results: Dict[str, Any]):
        """Opcional: reporta el estado del heartbeat a N8N."""
        try:
            n8n_url = os.environ.get("N8N_BASE_URL", "http://localhost:5678")
            if not n8n_url:
                return
            url = f"{n8n_url.rstrip('/')}/webhook/heartbeat"
            payload = {
                "event": "keep_alive_report",
                "source": "AURA_Core_KeepAlive",
                "timestamp": results.get("timestamp"),
                "summary": {
                    "total": results.get("total_services"),
                    "alive": results.get("alive"),
                    "dead": results.get("degraded_or_dead"),
                },
                "services": results.get("details", {}),
            }
            requests.post(url, json=payload, timeout=3)
        except Exception:
            pass  # No crítico


def main():
    parser = argparse.ArgumentParser(
        description="AURA KeepAlive - Anti-sleep para servicios gratuitos/locales"
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Ejecutar en bucle infinito cada N segundos",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL,
        help=f"Intervalo en segundos (default: {DEFAULT_INTERVAL})",
    )
    args = parser.parse_args()

    service = KeepAliveService(interval=args.interval)

    if args.loop:
        service.run_loop()
    else:
        results = service.run_once()
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
