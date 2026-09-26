"""BLOQUE 77 - REST API tests for Sandbox Management endpoints."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.sandbox.executor import (
    SandboxExecutor,
    get_sandbox_orchestrator,
    reset_sandbox_orchestrator,
)
from backend.sandbox.router import router


@pytest.fixture(autouse=True)
def _reset():
    reset_sandbox_orchestrator()
    yield
    reset_sandbox_orchestrator()


@pytest.fixture
def client():
    reset_sandbox_orchestrator()
    tmp = tempfile.mkdtemp(prefix="aura_sbx_rest_")
    get_sandbox_orchestrator(executor=SandboxExecutor(), workdir_root=tmp)
    app = FastAPI(title="AURA Sandbox Test", version="test")
    app.include_router(router)
    with TestClient(app) as c:
        yield c
    reset_sandbox_orchestrator()


def test_run_python_success(client):
    r = client.post("/api/sandbox/run", json={"lang": "python", "code": "print('hi')"})
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "success"
    assert "hi" in d["stdout"]


def test_run_error(client):
    r = client.post(
        "/api/sandbox/run", json={"lang": "python", "code": "raise RuntimeError('kaboom')"}
    )
    assert r.status_code == 200
    assert r.json()["status"] == "error"
    assert "kaboom" in r.json()["stderr"]


def test_run_denied_fs(client):
    r = client.post(
        "/api/sandbox/run", json={"lang": "python", "code": "open('/etc/passwd').read()"}
    )
    assert r.status_code == 200
    assert r.json()["status"] == "denied"


def test_run_timeout(client):
    r = client.post(
        "/api/sandbox/run",
        json={"lang": "python", "code": "import time; time.sleep(5)", "timeout_ms": 300},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "timeout"


def test_run_network_denied(client):
    r = client.post(
        "/api/sandbox/run",
        json={"lang": "python", "code": "import socket; socket.socket()", "network": False},
    )
    assert r.status_code == 200
    assert "network access denied" in r.json()["stderr"]


def test_status(client):
    r = client.get("/api/sandbox/status")
    assert r.status_code == 200
    assert r.json()["enabled"] is True


def test_instances_after_run(client):
    r = client.post("/api/sandbox/run", json={"lang": "python", "code": "print(1)"})
    sid = r.json()["sandbox_id"]
    inst = client.get("/api/sandbox/instances")
    assert inst.status_code == 200
    assert any(i["sandbox_id"] == sid for i in inst.json())


def test_destroy(client):
    r = client.post("/api/sandbox/run", json={"lang": "python", "code": "print(1)"})
    sid = r.json()["sandbox_id"]
    d = client.post("/api/sandbox/destroy", json={"sandbox_id": sid})
    assert d.status_code == 200 and d.json()["destroyed"] is True
    d2 = client.post("/api/sandbox/destroy", json={"sandbox_id": sid})
    assert d2.status_code == 404


def test_health(client):
    r = client.get("/api/sandbox/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["has_docker"] is False
