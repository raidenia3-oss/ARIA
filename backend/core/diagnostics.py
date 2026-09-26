"""AURA Master System Integration — BLOQUE 61.

Diagnostico maestro del ecosistema AURA: consolida telemetria local (Bloque 48),
sondas de despliegue (Bloque 30) y flujos de integracion E2E en un solo modulo
de diagnostico soberano. Todo es local-first: sin dependencias cloud, sin
tokens expuestos, sin infraestructura externa.
"""

from __future__ import annotations

import os
import time
import socket
import threading
import logging
from typing import Any, Dict, List, Optional

from backend.diagnostics.health import (
    get_health_daemon,
    get_system_resources,
    probe_service_status,
)

logger = logging.getLogger("AURA.Diagnostics.Master")

# Puertos criticos del ecosistema AURA
ECOSYSTEM_PORTS: Dict[str, int] = {
    "backend": int(os.getenv("AURA_BACKEND_PORT", "8000")),
    "jan": int(os.getenv("AURA_JAN_PORT", "1337")),
    "ollama": int(os.getenv("AURA_OLLAMA_PORT", "11434")),
    "frontend": int(os.getenv("AURA_FRONTEND_PORT", "3000")),
    "discord": int(os.getenv("AURA_DISCORD_PORT", "8080")),
}


def _port_alive(host: str, port: int, timeout: float = 0.3) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _env_status() -> Dict[str, Any]:
    """Revisa variables de entorno criticas (solo presencia, nunca valores)."""
    keys = [
        "AURA_API_KEY", "DATABASE_URL", "REDIS_URL", "HF_TOKEN",
        "GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY",
        "DISCORD_WEBHOOK_URL", "SECRET_KEY", "ENVIRONMENT",
    ]
    out: Dict[str, Any] = {}
    for k in keys:
        out[k] = "set" if os.getenv(k) else "missing"
    return out


def _module_importable(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


def _ecosystem_modules() -> Dict[str, Any]:
    """Verifica que los modulos clave del backend sean importables."""
    modules = [
        "backend.main", "backend.diagnostics.health", "backend.production_routes",
        "backend.core.diagnostics", "backend.core.routes",
        "backend.brain_orchestrator", "backend.orchestrator", "backend.database",
        "backend.models", "backend.narrative_engine", "backend.update_manager",
        "backend.mobile_automation_manager", "backend.self_learning_manager",
        "backend.agents.orchestrator_routes", "backend.agent.evolution_routes",
        "backend.agent.sandbox_routes", "backend.ai_router", "backend.omniroute",
        "backend.diagnostics.routes", "backend.production_routes",
        "backend.sync_engine", "backend.websocket_manager",
    ]
    out: Dict[str, Any] = {}
    for m in modules:
        out[m] = "ok" if _module_importable(m) else "error"
    return out


def _e2e_readiness() -> Dict[str, Any]:
    """Indicador de preparacion para flujos E2E."""
    checks: Dict[str, Any] = {}
    checks["backend_port"] = "ok" if _port_alive("127.0.0.1", ECOSYSTEM_PORTS["backend"]) else "down"
    checks["jan_port"] = "ok" if _port_alive("127.0.0.1", ECOSYSTEM_PORTS["jan"]) else "down"
    checks["ollama_port"] = "ok" if _port_alive("127.0.0.1", ECOSYSTEM_PORTS["ollama"]) else "down"
    checks["frontend_port"] = "ok" if _port_alive("127.0.0.1", ECOSYSTEM_PORTS["frontend"]) else "down"
    checks["discord_port"] = "ok" if _port_alive("127.0.0.1", ECOSYSTEM_PORTS["discord"]) else "down"
    checks["env_vars"] = _env_status()
    checks["modules"] = _ecosystem_modules()
    checks["timestamp"] = time.time()
    return checks


def _aggregate_status(readiness: Dict[str, Any]) -> str:
    """Indicador agregado: healthy | degraded | unhealthy."""
    ports = {k: v for k, v in readiness.items() if k.endswith("_port")}
    port_states = [v for v in ports.values() if isinstance(v, str)]
    if not port_states:
        return "degraded"
    up = sum(1 for v in port_states if v == "ok")
    if up == len(port_states):
        return "healthy"
    if up >= len(port_states) // 2:
        return "degraded"
    return "unhealthy"


class MasterDiagnostics:
    """Diagnostico maestro: consolida health daemon + probes de despliegue + E2E."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last: Optional[Dict[str, Any]] = None

    def snapshot(self, force: bool = False) -> Dict[str, Any]:
        with self._lock:
            if self._last is None or force:
                ts = time.time()
                readiness = _e2e_readiness()
                self._last = {
                    "status": _aggregate_status(readiness),
                    "timestamp": ts,
                    "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts)),
                    "readiness": readiness,
                    "health_daemon": get_health_daemon().snapshot(),
                }
            return self._last

    def health(self) -> Dict[str, Any]:
        snap = self.snapshot()
        out = dict(snap)
        out["healthy"] = snap.get("status") == "healthy"
        return out

    def readiness(self) -> Dict[str, Any]:
        return self.snapshot()["readiness"]


# Singleton
_master: Optional[MasterDiagnostics] = None
_master_lock = threading.Lock()


def get_master_diagnostics() -> MasterDiagnostics:
    global _master
    if _master is None:
        with _master_lock:
            if _master is None:
                _master = MasterDiagnostics()
    return _master


def master_snapshot() -> Dict[str, Any]:
    return get_master_diagnostics().snapshot()


def master_health() -> Dict[str, Any]:
    return get_master_diagnostics().health()


def master_readiness() -> Dict[str, Any]:
    return get_master_diagnostics().readiness()