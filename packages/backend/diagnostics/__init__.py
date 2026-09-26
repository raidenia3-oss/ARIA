"""AURA Local Diagnostics & System Health.

Paquete del motor de diagnósticos y salud del sistema soberano. Recopila
métricas del host y el estado de los daemons locales (FastAPI, Jan, WebSocket
Gateway, mDNS y sync móvil) de forma pasiva y 100% local, sin telemetría
externa ni exposición de secretos.
"""

from __future__ import annotations

from backend.diagnostics.health import (
    HealthDaemon,
    JanWatchdog,
    LocalTelemetry,
    ServiceWatchdog,
    get_health_daemon,
    get_system_resources,
    probe_service_status,
    start_health_daemon,
    stop_health_daemon,
)
from backend.diagnostics.routes import router as health_router

__all__ = [
    "HealthDaemon",
    "JanWatchdog",
    "LocalTelemetry",
    "ServiceWatchdog",
    "get_health_daemon",
    "get_system_resources",
    "probe_service_status",
    "start_health_daemon",
    "stop_health_daemon",
    "health_router",
]

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
