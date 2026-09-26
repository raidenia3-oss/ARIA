"""AURA Local Diagnostics & System Health - motor soberano de telemetria local.

BLOQUE 48: subsistema de metricas de salud y diagnosticos del ecosistema AURA
en la PC. Recopila de forma pasiva y 100% local:

- Metricas del host: CPU, RAM, disco, red, uptime y datos de plataforma.
- Estado de los daemons locales: backend FastAPI, motor local Jan, pasarela
  WebSocket, descubrimiento mDNS y sync con la tarjeta SD del movil.

Diseno:
- ``LocalTelemetry``: recursos del host (psutil o stdlib). Nunca toca la red.
- ``ServiceWatchdog``: verifica puertos/daemons y registra transiciones up/down.
- ``JanWatchdog``: subrutina del motor local Jan/Ollama-compatible.
- ``HealthDaemon``: agrega telemetria + watchdogs en un hilo pasivo y expone
  ``snapshot()`` con la estructura JSON lista para REST.

Restricciones:
- Operacion offline: sin Sentry, Datadog ni telemetria cloud.
- No expone tokens ni claves: solo estado + metricas.
"""

from __future__ import annotations

import logging
import os
import platform
import socket
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURA.Diagnostics.Health")

DEFAULT_JAN_PORTS: List[int] = [int(p) for p in os.getenv("AURA_JAN_PORTS", "1337,11434").split(",") if p.strip().isdigit()]
BACKEND_HOST: str = os.getenv("AURA_BACKEND_HOST", "127.0.0.1")
BACKEND_PORT: int = int(os.getenv("AURA_BACKEND_PORT", "8000"))


def _now() -> float:
    return time.time()


def _iso(ts: Optional[float] = None) -> str:
    return datetime.fromtimestamp(ts or _now()).isoformat(timespec="seconds")


def _port_responds(host: str, port: int, timeout: float = 0.3) -> bool:
    """Comprueba si un puerto TCP local acepta conexiones (no envia datos)."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# LocalTelemetry - metricas de recursos del host
# ---------------------------------------------------------------------------

class LocalTelemetry:
    """Recopilador ligero de metricas de recursos del host (offline).

    Usa ``psutil`` si esta disponible; en caso contrario devuelve un subconjunto
    minimo derivado del stdlib. Nunca toca la red.
    """

    def __init__(self) -> None:
        self._psutil = None
        try:
            import psutil  # type: ignore
            self._psutil = psutil
        except Exception as exc:  # noqa: BLE001
            logger.info("psutil no disponible (%s); telemetria degradada", exc)

    @property
    def available(self) -> bool:
        return self._psutil is not None

    def collect(self) -> Dict[str, Any]:
        """Snapshot de recursos del host (nunca lanza excepciones)."""
        ts = _now()
        base: Dict[str, Any] = {
            "timestamp": ts,
            "iso": _iso(ts),
            "host": platform.node() or "unknown",
            "platform": platform.system() or "unknown",
            "python": platform.python_version(),
            "cpu_count": os.cpu_count() or 0,
        }
        ps = self._psutil
        if ps is None:
            base["source"] = "stdlib"
            base["cpu"] = None
            base["memory_percent"] = None
            base["disk_percent"] = None
            base["network"] = {"bytes_sent": 0, "bytes_recv": 0}
            return base

        try:
            base["source"] = "psutil"
            base["cpu"] = round(float(ps.cpu_percent(interval=None)), 1)
            vm = ps.virtual_memory()
            base["memory_percent"] = round(float(getattr(vm, "percent", 0.0)), 1)
            base["memory_used_bytes"] = int(getattr(vm, "used", 0))
            base["memory_total_bytes"] = int(getattr(vm, "total", 0))
            try:
                du = ps.disk_usage(os.path.expanduser("~"))
                base["disk_percent"] = round(float(getattr(du, "percent", 0.0)), 1)
                base["disk_free_bytes"] = int(getattr(du, "free", 0))
            except Exception:  # noqa: BLE001
                base["disk_percent"] = None
            net = ps.net_io_counters()
            base["network"] = {
                "bytes_sent": int(getattr(net, "bytes_sent", 0)),
                "bytes_recv": int(getattr(net, "bytes_recv", 0)),
            }
            base["boot_time"] = _iso(getattr(ps, "boot_time")() if callable(getattr(ps, "boot_time", None)) else (time.time() - 0))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Telemetria de host fallo parcialmente: %s", exc)
        return base


# ---------------------------------------------------------------------------
# ServiceWatchdog - vigilante de puertos/daemons locales
# ---------------------------------------------------------------------------

class ServiceWatchdog:
    """Verifica periodicamente que los daemons locales respondan por TCP.

    Registra transiciones up/down con timestamps y mantiene un historial.
    No ejecuta comandos destructivos ni toca la red externa (solo localhost).
    """

    def __init__(self, host: str = BACKEND_HOST, port: int = BACKEND_PORT,
                 jan_ports: Optional[List[int]] = None, interval: float = 15.0,
                 timeout: float = 0.3) -> None:
        self.host = host
        self.port = port
        self.jan_ports = list(jan_ports) if jan_ports else list(DEFAULT_JAN_PORTS)
        self.interval = interval
        self.timeout = timeout
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._hist: Dict[str, List[Dict[str, Any]]] = {}
        self._last: Dict[str, Any] = {}
        self._configure()

    def _configure(self) -> None:
        self._services: Dict[str, Dict[str, Any]] = {
            "backend": {"key": "backend", "label": "FastAPI local", "host": self.host, "port": self.port},
            "jan_primary": {"key": "jan_primary", "label": "Jan/Ollama local", "host": self.host, "port": (self.jan_ports[0] if self.jan_ports else 1337)},
        }
        for p in self.jan_ports:
            self._services[f"jan:{p}"] = {"key": f"jan:{p}", "label": f"Jan puerto {p}", "host": self.host, "port": p}

    # -- comprobacion puntual -------------------------------------------------

    def _check_one(self, service: Dict[str, Any]) -> Dict[str, Any]:
        key = service["key"]
        state = "up" if _port_responds(service["host"], int(service["port"]), self.timeout) else "down"
        now = _now()
        prev_state = (self._last.get(key) or {}).get("state")
        record = {
            "key": key,
            "label": service.get("label", key),
            "host": service["host"],
            "port": int(service["port"]),
            "state": state,
            "state_iso": _iso(now),
            "check_at": now,
        }
        if prev_state != state:
            entry = {"from": prev_state or "unknown", "to": state, "ts": now, "iso": _iso(now)}
            self._hist.setdefault(key, []).append(entry)
            del self._hist[key][-100:]
            logger.info("Servicio %s -> %s", key, state)
        self._last[key] = record
        return record

    def check_all(self) -> Dict[str, Any]:
        """Comprueba todos los servicios; devuelve {key: {key, state, ...}}."""
        out: Dict[str, Any] = {}
        with self._lock:
            for key, service in self._services.items():
                out[key] = self._check_one(service)
        return out

    def get_status(self) -> Dict[str, Any]:
        """Estado resumido de los servicios: {key: {label, host, port, state, changes}}."""
        with self._lock:
            status: Dict[str, Any] = {}
            for key, service in self._services.items():
                rec = self._last.get(key) or self._check_one(service)
                status[key] = {
                    "label": rec.get("label", service.get("label", key)),
                    "host": rec.get("host", service["host"]),
                    "port": rec.get("port", int(service["port"])),
                    "state": rec.get("state"),
                    "changes": len(self._hist.get(key, [])),
                    "state_iso": rec.get("state_iso"),
                }
            return status

    def get_history(self, key: Optional[str] = None) -> Dict[str, Any]:
        """Historial de transiciones; filtrable por clave de servicio."""
        with self._lock:
            if key:
                return {key: list(self._hist.get(key, []))}
            return {k: list(v) for k, v in self._hist.items()}

    # -- ciclo de vida --------------------------------------------------------

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="AURA-ServiceWatchdog")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.check_all()
            except Exception as exc:  # noqa: BLE001
                logger.exception("Watchdog check error: %s", exc)
            self._stop.wait(self.interval)


# ---------------------------------------------------------------------------
# JanWatchdog - subrutina especifica del motor local Jan/Ollama
# ---------------------------------------------------------------------------

class JanWatchdog:
    """Comprueba el estado del motor local Jan/Ollama-compatible.

    Detecta si el modelo de Jan y sus puertos de red responden correctamente y
    registra cualquier caida del servicio (``check()`` / ``get_last()``).
    """

    def __init__(self, host: str = BACKEND_HOST,
                 jan_ports: Optional[List[int]] = None,
                 base_url: str = "http://127.0.0.1:1337", interval: float = 30.0,
                 timeout: float = 0.3) -> None:
        self.host = host
        self.jan_ports = list(jan_ports) if jan_ports else list(DEFAULT_JAN_PORTS)
        self.base_url = base_url
        self.interval = interval
        self.timeout = timeout
        self._last: Optional[Dict[str, Any]] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def check(self) -> Dict[str, Any]:
        """Comprobacion puntual del motor Jan: puertos abiertos + conteo de modelos."""
        ts = _now()
        model_ports = [p for p in self.jan_ports if _port_responds(self.host, p, self.timeout)]
        healthy = bool(model_ports)
        models_count = len(model_ports)
        result = {
            "healthy": healthy,
            "models_count": models_count,
            "ports": self.jan_ports,
            "ports_open": model_ports,
            "base_url": self.base_url,
            "checked_at": ts,
            "checked_iso": _iso(ts),
        }
        self._last = result
        return result

    def get_last(self) -> Optional[Dict[str, Any]]:
        """Ultimo estado conocido del motor Jan (None si nunca se comprobo)."""
        return self._last

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="AURA-JanWatchdog")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.check()
            except Exception as exc:  # noqa: BLE001
                logger.exception("Jan check error: %s", exc)
            self._stop.wait(self.interval)


# ---------------------------------------------------------------------------
# Estado del ecosistema (WebSocket, mDNS, sync movil)
# ---------------------------------------------------------------------------

_LAST_WS_LATENCY_MS: List[float] = []
_ws_lock = threading.Lock()


def record_ws_latency(latency_ms: float) -> None:
    """Registra la ultima latencia medida de WebSocket (para el panel)."""
    with _ws_lock:
        _LAST_WS_LATENCY_MS.append(float(latency_ms))
        del _LAST_WS_LATENCY_MS[:-20]  # conserva las ultimas 20 muestras


def _last_ws_latency_ms() -> Optional[float]:
    with _ws_lock:
        return _LAST_WS_LATENCY_MS[-1] if _LAST_WS_LATENCY_MS else None


def _mdns_peers() -> Dict[str, Any]:
    """Lee los peers descubiertos por mDNS (sin llamadas de red bloqueantes)."""
    try:
        from backend.mobile.discovery import mdns
        hosts = mdns.get_discovered_hosts()
        safe: Dict[str, Any] = {}
        for name, info in hosts.items():
            props = dict(info.get("properties", {}))
            props.pop("token", None)
            props.pop("secret", None)
            safe[name] = {"address": info.get("address"), "port": info.get("port"), "properties": props}
        return {"count": len(safe), "peers": safe}
    except Exception as exc:  # noqa: BLE001
        return {"count": 0, "peers": {}, "error": str(exc)}


def _websocket_status() -> Dict[str, Any]:
    """Estado de la pasarela WebSocket (conexiones activas + QoS local)."""
    try:
        from backend.websocket_manager import ws_gateway
        count = ws_gateway.get_connection_count()
        gw_status = ws_gateway.get_status()
        return {
            "status": "up" if count > 0 else "idle",
            "connections": count,
            "subscribed_works": gw_status.get("subscribed_works", {}),
            "ping_latency_ms": _last_ws_latency_ms(),
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "unknown", "connections": 0, "error": str(exc)}


def _mobile_sync_status(ws: Dict[str, Any]) -> Dict[str, Any]:
    """Estado de la sincronizacion con la tarjeta SD del dispositivo movil."""
    sd: Dict[str, Any] = {}
    try:
        from backend.sync_engine import get_sync_status
        try:
            sd = get_sync_status()
        except TypeError:
            sd = {}
    except Exception:  # noqa: BLE001
        sd = {}
    try:
        from backend.mobile import sync_manager
        clients = len(getattr(sync_manager, "_connections", set()) or set())
    except Exception:  # noqa: BLE001
        clients = 0
    connected = clients > 0 or bool(sd.get("connected", False))
    ws_active = bool(ws.get("connections"))
    state = "synced" if connected else ("idle" if not ws_active else "pending")
    return {
        "status": state,
        "connected_clients": clients,
        "sd_storage": {
            "configured": bool(sd.get("configured", False)),
            "path": sd.get("path") if sd.get("configured") else None,
            "last_sync_iso": sd.get("last_sync"),
            "last_sync_at": sd.get("last_sync_at"),
        },
    }


def _global_status(host: Dict[str, Any], services: Dict[str, Any],
                   sync: Dict[str, Any]) -> str:
    """Indicador agregado: healthy | degraded | unhealthy."""
    try:
        cpu = host.get("cpu") or 0
        mem = host.get("memory_percent") or 0
        disk = host.get("disk_percent") or 0
        if cpu > 95 or mem > 95 or disk > 97:
            return "degraded"
        if services.get("backend", {}).get("state") != "up":
            return "unhealthy"
        if sync.get("status") == "error":
            return "degraded"
        return "healthy"
    except Exception:  # noqa: BLE001
        return "healthy"


# ---------------------------------------------------------------------------
# HealthDaemon - agrega telemetria + watchdogs
# ---------------------------------------------------------------------------

class HealthDaemon:
    """Daemon pasivo de salud del sistema.

    Recopila telemetria de host y estado de los watchdogs en segundo plano a
    intervalos regulares, manteniendo un snapshot en cache accesible via
    ``snapshot()`` (formato JSON listo para REST).
    """

    def __init__(self, telemetry_interval: float = 10.0,
                 watchdog_interval: float = 15.0, jan_interval: float = 30.0,
                 jan_url: str = "http://127.0.0.1:1337") -> None:
        self.telemetry = LocalTelemetry()
        self.service_watchdog = ServiceWatchdog(interval=watchdog_interval)
        self.jan_watchdog = JanWatchdog(base_url=jan_url, interval=jan_interval)
        self._telemetry_interval = telemetry_interval
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._last_snapshot: Optional[Dict[str, Any]] = None
        self._lock = threading.Lock()
        self._started_at = _now()

    def start(self) -> "HealthDaemon":
        if self._thread and self._thread.is_alive():
            return self
        self._stop.clear()
        self.service_watchdog.start()
        self.jan_watchdog.start()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="AURA-HealthDaemon")
        self._thread.start()
        self.gather()  # primer sondeo inmediato
        logger.info("HealthDaemon iniciado")
        return self

    def stop(self) -> None:
        self._stop.set()
        self.service_watchdog.stop()
        self.jan_watchdog.stop()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.gather()
            except Exception as exc:  # noqa: BLE001
                logger.exception("HealthDaemon gather error: %s", exc)
            self._stop.wait(self._telemetry_interval)

    def gather(self) -> Dict[str, Any]:
        """Recopila telemetria + servicios + jan en un snapshot."""
        snapshot = self.snapshot(force=True)
        return snapshot

    def snapshot(self, force: bool = False) -> Dict[str, Any]:
        """Snapshot del ecosistema (cacheado)."""
        with self._lock:
            if self._last_snapshot is None or force:
                ts = _now()
                host = self.telemetry.collect()
                services = self.service_watchdog.check_all()
                jan = self.jan_watchdog.check()
                ws = _websocket_status()
                peers = _mdns_peers()
                sync = _mobile_sync_status(ws)
                self._last_snapshot = {
                    "status": _global_status(host, services, sync),
                    "timestamp": ts,
                    "iso": _iso(ts),
                    "uptime_seconds": round(_now() - self._started_at, 1),
                    "host": host,
                    "services": services,
                    "jan": jan,
                    "websocket": ws,
                    "mdns_peers": peers,
                    "mobile_sync": sync,
                }
                self._last_snapshot["healthy"] = self._last_snapshot["status"] == "healthy"
            return self._last_snapshot

    def health(self) -> Dict[str, Any]:
        """Snapshot global en formato REST (indicador visual del ecosistema)."""
        snap = self.snapshot()
        out = dict(snap)
        out["healthy"] = snap.get("status") == "healthy"
        return out


# ---------------------------------------------------------------------------
# Funciones de conveniencia y singleton global
# ---------------------------------------------------------------------------

_health_daemon: Optional[HealthDaemon] = None
_daemon_lock = threading.Lock()


def get_system_resources() -> Dict[str, Any]:
    """Snapshot puntual de recursos del host (no lanza excepciones)."""
    return LocalTelemetry().collect()


def probe_service_status() -> Dict[str, Any]:
    """Comprobacion puntual de los daemons locales (contiene 'backend')."""
    return ServiceWatchdog().check_all()


def get_health_daemon() -> HealthDaemon:
    """Singleton del HealthDaemon (inicializacion perezosa)."""
    global _health_daemon
    if _health_daemon is None:
        with _daemon_lock:
            if _health_daemon is None:
                _health_daemon = HealthDaemon()
    return _health_daemon


def start_health_daemon() -> HealthDaemon:
    return get_health_daemon().start()


def stop_health_daemon() -> None:
    global _health_daemon
    if _health_daemon is not None:
        _health_daemon.stop()
        _health_daemon = None
