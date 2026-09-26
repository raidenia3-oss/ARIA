"""Tests Bloque 48 — Local Diagnostics & System Health.

Valida:
- LocalTelemetry: recopila métricas de host (CPU, RAM, disco).
- ServiceWatchdog: comprueba estado de daemons y registra transiciones up/down.
- JanWatchdog: estado del motor local Jan/Ollama.
- HealthDaemon: estructura JSON global del panel (sin secretos).
- REST helpers: get_system_resources, probe_service_status.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.diagnostics.health import (
    HealthDaemon,
    JanWatchdog,
    LocalTelemetry,
    ServiceWatchdog,
    get_system_resources,
    probe_service_status,
    start_health_daemon,
    stop_health_daemon,
)


class _FakePsutil:
    def cpu_percent(self, interval=None):
        return 12.5

    class virtual_memory:
        percent = 42.5
        used = 8_000_000_000
        total = 16_000_000_000

    @staticmethod
    def disk_usage(path):
        class _Du:
            percent = 60.0
            free = 50_000_000_000

        return _Du()

    @staticmethod
    def net_io_counters():
        class _Net:
            bytes_sent = 1000
            bytes_recv = 2000

        return _Net()

    @staticmethod
    def boot_time():
        import time

        return time.time() - 3600


def test_local_telemetry_collect():
    telemetry = LocalTelemetry()
    res = telemetry.collect()
    assert "timestamp" in res
    assert "iso" in res
    assert "host" in res
    assert "platform" in res
    assert "python" in res
    assert "cpu_count" in res
    assert "source" in res


def test_local_telemetry_with_psutil():
    telemetry = LocalTelemetry()
    telemetry._psutil = _FakePsutil()
    res = telemetry.collect()
    assert res["source"] == "psutil"
    assert res["cpu"] == 12.5
    assert res["memory_percent"] == 42.5
    assert res["memory_used_bytes"] == 8_000_000_000
    assert res["memory_total_bytes"] == 16_000_000_000
    assert res["disk_percent"] == 60.0
    assert res["network"]["bytes_sent"] == 1000
    assert "boot_time" in res


def test_get_system_resources():
    res = get_system_resources()
    assert "timestamp" in res
    assert "cpu_count" in res
    assert isinstance(res["cpu_count"], int)


def test_service_watchdog_check_all():
    sw = ServiceWatchdog()
    res = sw.check_all()
    assert isinstance(res, dict)
    assert "backend" in res
    assert "jan_primary" in res
    for key, val in res.items():
        assert "key" in val
        assert "state" in val
        assert val["state"] in ("up", "down")


def test_service_watchdog_get_status():
    sw = ServiceWatchdog()
    status = sw.get_status()
    assert isinstance(status, dict)
    for key, val in status.items():
        assert "label" in val
        assert "host" in val
        assert "port" in val


def test_service_watchdog_history():
    sw = ServiceWatchdog()
    history = sw.get_history()
    assert isinstance(history, dict)


def test_service_watchdog_start_stop():
    sw = ServiceWatchdog()
    sw.start()
    # give it a moment to run one check
    import time

    time.sleep(0.1)
    status = sw.get_status()
    assert "backend" in status
    sw.stop()


def test_jan_watchdog_check():
    jw = JanWatchdog()
    res = jw.check()
    assert "healthy" in res
    assert "models_count" in res
    assert "checked_at" in res
    assert "checked_iso" in res


def test_jan_watchdog_get_last():
    jw = JanWatchdog()
    assert jw.get_last() is None
    jw.check()
    assert jw.get_last() is not None


def test_health_daemon_snapshot():
    hd = HealthDaemon()
    snap = hd.snapshot()
    assert "host" in snap
    assert "services" in snap
    assert "jan" in snap
    # host
    assert "cpu_count" in snap["host"]
    # services
    assert "backend" in snap["services"]
    # jan
    assert "healthy" in snap["jan"]


def test_health_daemon_start_stop():
    hd = HealthDaemon()
    hd.start()
    snap = hd.snapshot()
    assert "host" in snap
    assert "services" in snap
    assert "jan" in snap
    hd.stop()


def test_start_stop_health_daemon_singleton():
    start_health_daemon()
    daemon = h.get_health_daemon() if False else None  # noqa
    from backend.diagnostics.health import get_health_daemon

    daemon = get_health_daemon()
    assert daemon is not None
    snap = daemon.snapshot()
    assert "host" in snap
    stop_health_daemon()


def test_probe_service_status():
    res = probe_service_status()
    assert isinstance(res, dict)
    assert "backend" in res


# --- REST endpoints tests ---


def _rest_setup():
    from backend.diagnostics.health import stop_health_daemon
    from backend.diagnostics.routes import router

    stop_health_daemon()
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    yield client
    stop_health_daemon()


def test_rest_health_snapshot():
    for client in _rest_setup():
        r = client.get("/api/system/health")
        assert r.status_code == 200
        data = r.json()
        assert "host" in data
        assert "services" in data
        assert "jan" in data


def test_rest_health_host():
    for client in _rest_setup():
        r = client.get("/api/system/health/host")
        assert r.status_code == 200
        data = r.json()
        assert "cpu_count" in data
        assert "platform" in data


def test_rest_health_services():
    for client in _rest_setup():
        r = client.get("/api/system/health/services")
        assert r.status_code == 200
        data = r.json()
        assert "backend" in data
        assert "jan_primary" in data


def test_rest_health_services_status():
    for client in _rest_setup():
        r = client.get("/api/system/health/services/status")
        assert r.status_code == 200
        data = r.json()
        assert "backend" in data


def test_rest_health_jan():
    for client in _rest_setup():
        r = client.get("/api/system/health/jan")
        assert r.status_code == 200
        data = r.json()
        assert "healthy" in data
        assert "models_count" in data


def test_rest_health_jan_check():
    for client in _rest_setup():
        r = client.post("/api/system/health/jan/check")
        assert r.status_code == 200
        data = r.json()
        assert "healthy" in data
