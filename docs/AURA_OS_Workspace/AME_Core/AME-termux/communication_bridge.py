"""
communication_bridge.py - Gestor de Heartbeat entre Main Core y Shadow-Core (Puerto 5001)
Cada 5 segundos hace ping al Shadow-Core. Expone estado asíncrono para el Dashboard.
"""

import threading
import time
import requests
import logging
from typing import Dict, Any

logger = logging.getLogger('ame_server')

# Estado global del heartbeat (accesible desde cualquier hilo)
_last_heartbeat = {
    "timestamp": 0,
    "status": "offline",
    "threat_status": "UNKNOWN",
    "error": None
}

_lock = threading.Lock()
_HEARTBEAT_INTERVAL = 5  # segundos
_SHADOW_URL = "http://127.0.0.1:5001/health"

def get_shadow_status() -> Dict[str, Any]:
    """
    Retorna el estado actual del Shadow-Core (hilo seguro).
    """
    with _lock:
        return dict(_last_heartbeat)

def _heartbeat_worker():
    """
    Worker interno: ejecuta ping al Shadow-Core cada N segundos.
    Corre en un hilo daemon.
    """
    global _last_heartbeat
    while True:
        try:
            # Ping al Shadow-Core vía endpoint /health
            resp = requests.get(
                _SHADOW_URL,
                timeout=3
            )

            if resp.status_code == 200:
                threat_status = "CLEAN"
                try:
                    data = resp.json()
                    threat_status = data.get("threat_status", "CLEAN")
                except Exception:
                    pass

                with _lock:
                    _last_heartbeat = {
                        "timestamp": time.time(),
                        "status": "online",
                        "threat_status": threat_status,
                        "error": None
                    }
            else:
                with _lock:
                    _last_heartbeat = {
                        "timestamp": time.time(),
                        "status": "degraded",
                        "threat_status": "UNKNOWN",
                        "error": f"HTTP {resp.status_code}"
                    }

        except requests.exceptions.ConnectionError:
            with _lock:
                _last_heartbeat = {
                    "timestamp": time.time(),
                    "status": "offline",
                    "threat_status": "UNKNOWN",
                    "error": "conexión rechazada"
                }
        except requests.exceptions.Timeout:
            with _lock:
                _last_heartbeat = {
                    "timestamp": time.time(),
                    "status": "offline",
                    "threat_status": "UNKNOWN",
                    "error": "timeout"
                }
        except Exception as e:
            with _lock:
                _last_heartbeat = {
                    "timestamp": time.time(),
                    "status": "offline",
                    "threat_status": "UNKNOWN",
                    "error": str(e)
                }

        time.sleep(_HEARTBEAT_INTERVAL)

def start_heartbeat():
    """
    Inicia el heartbeat en un hilo daemon.
    Llámala una vez al arrancar el servidor.
    """
    thread = threading.Thread(target=_heartbeat_worker, daemon=True, name="ShadowHeartbeat")
    thread.start()
    logger.info("💓 Heartbeat Shadow-Core iniciado (intervalo %ds)", _HEARTBEAT_INTERVAL)

def is_shadow_online() -> bool:
    """Retorna True si el Shadow-Core respondió en el último heartbeat."""
    with _lock:
        return _last_heartbeat.get("status") == "online"