"""BLOQUE 80 - REST API tests for Daemon Lifecycle endpoints."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.daemon.bootstrapper import (
    Bootstrapper,
    DaemonConfig,
    DaemonStore,
    get_daemon_controller,
    reset_daemon_engine,
)
from backend.daemon.daemon_routes import router


@pytest.fixture(autouse=True)
def _reset():
    reset_daemon_engine()
    yield
    reset_daemon_engine()


@pytest.fixture
def client(tmp_path):
    reset_daemon_engine()
    cfg = DaemonConfig(service_name="aura-rest", strategy="windows_task")
    store = DaemonStore(store_dir=tmp_path)
    get_daemon_controller(bootstrapper=Bootstrapper(config=cfg, store=store, execute=False))
    app = FastAPI(title="AURA Daemon Test", version="test")
    app.include_router(router)
    with TestClient(app) as c:
        yield c
    reset_daemon_engine()


def test_status(client):
    r = client.get("/api/daemon/status")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "stopped"
    assert d["bootstrapper"]["service"] == "aura-rest"


def test_get_config(client):
    r = client.get("/api/daemon/config")
    assert r.status_code == 200
    assert r.json()["service"] == "aura-rest"
    assert r.json()["offline_only"] is True


def test_post_config(client):
    r = client.post("/api/daemon/config", json={"autostart_enabled": False, "max_restarts": 3})
    assert r.status_code == 200 and r.json()["ok"] is True
    cfg = r.json()["config"]
    assert cfg["autostart_enabled"] is False and cfg["max_restarts"] == 3


def test_install_dry_run(client):
    r = client.post("/api/daemon/install", json={"execute": False})
    assert r.status_code == 200
    d = r.json()
    assert d["installed"] is True and d["executed"] is False


def test_uninstall_dry_run(client):
    client.post("/api/daemon/install", json={"execute": False})
    r = client.post("/api/daemon/uninstall", json={"execute": False})
    assert r.status_code == 200 and r.json()["uninstalled"] is True


def test_artifacts(client):
    client.post("/api/daemon/install", json={"execute": False})
    r = client.get("/api/daemon/artifacts")
    assert r.status_code == 200
    assert len(r.json()["artifacts"]) > 0


def test_start_stop_restart(client):
    r = client.post("/api/daemon/start")
    assert r.status_code == 200 and r.json()["ok"] is True
    r2 = client.post("/api/daemon/restart")
    assert r2.status_code == 200 and r2.json()["ok"] is True
    r3 = client.post("/api/daemon/stop")
    assert r3.status_code == 200 and r3.json()["ok"] is True
    st = client.get("/api/daemon/status").json()
    assert st["status"] == "stopped"


def test_health(client):
    client.post("/api/daemon/start")
    r = client.get("/api/daemon/health")
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True and d["offline_only"] is True


def test_config_persisted_across_reads(client, tmp_path):
    client.post("/api/daemon/config", json={"autostart_enabled": True})
    r = client.get("/api/daemon/status")
    assert r.status_code == 200
    assert r.json()["bootstrapper"]["autostart_enabled"] is True


def test_install_then_status_reflects_state(client):
    client.post("/api/daemon/install", json={"execute": False})
    client.post("/api/daemon/start")
    st = client.get("/api/daemon/status").json()
    assert st["status"] == "running"
    assert st["bootstrapper"]["autostart_enabled"] is True
