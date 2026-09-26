"""BLOQUE 81 - REST API tests for Omni-Diagnostic Suite endpoints."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.diagnostics.omni import (
    DiagnosticConfig,
    OmniAuditor,
    get_omni_auditor,
    register_default_checks,
    reset_omni_auditor,
)
from backend.diagnostics.omni_routes import router


@pytest.fixture(autouse=True)
def _reset():
    reset_omni_auditor()
    yield
    reset_omni_auditor()


@pytest.fixture
def client(tmp_path):
    reset_omni_auditor()
    cfg = DiagnosticConfig(repo_root=os.getcwd(), report_dir=str(tmp_path / "reports"))
    auditor = OmniAuditor(config=cfg)
    register_default_checks(auditor)
    get_omni_auditor(config=cfg, register_defaults=False)
    # Replace the singleton with our configured auditor
    import backend.diagnostics.omni as omni

    omni._engine = auditor
    app = FastAPI(title="AURA Omni Test", version="test")
    app.include_router(router)
    with TestClient(app) as c:
        yield c


def test_status(client):
    r = client.get("/api/diagnostics/omni/status")
    assert r.status_code == 200
    d = r.json()
    assert d["checks_total"] > 0
    assert d["offline_only"] is True
    assert "filesystem" in d["checks_registered"]


def test_checks_list(client):
    r = client.get("/api/diagnostics/omni/checks")
    assert r.status_code == 200
    d = r.json()
    assert "filesystem" in d["checks"]
    assert d["offline_only"] is True


def test_run_full_suite(client):
    r = client.post("/api/diagnostics/omni/run")
    assert r.status_code == 200
    d = r.json()
    assert d["verdict"] == "sovereign_ready"
    assert d["counts"]["fail"] == 0
    assert d["checks_total"] >= 9


def test_run_with_only_filter(client):
    r = client.post("/api/diagnostics/omni/run", json={"only": ["filesystem"]})
    assert r.status_code == 200
    d = r.json()
    assert d["checks_total"] == 1
    assert d["results"][0]["name"] == "filesystem"


def test_run_with_skip_filter(client):
    r = client.post("/api/diagnostics/omni/run", json={"skip": ["filesystem"]})
    assert r.status_code == 200
    d = r.json()
    names = [x["name"] for x in d["results"]]
    assert "filesystem" not in names


def test_history(client):
    client.post("/api/diagnostics/omni/run")
    client.post("/api/diagnostics/omni/run")
    r = client.get("/api/diagnostics/omni/history")
    assert r.status_code == 200
    assert len(r.json()["history"]) >= 2


def test_history_limit(client):
    client.post("/api/diagnostics/omni/run")
    client.post("/api/diagnostics/omni/run")
    client.post("/api/diagnostics/omni/run")
    r = client.get("/api/diagnostics/omni/history", params={"limit": 2})
    assert r.status_code == 200
    assert len(r.json()["history"]) == 2


def test_export(client):
    r = client.get("/api/diagnostics/omni/export")
    assert r.status_code == 200
    d = r.json()
    assert d["exported"]
    assert os.path.exists(d["exported"])
    assert d["offline_only"] is True


def test_reset(client):
    client.post("/api/diagnostics/omni/run")
    r = client.post("/api/diagnostics/omni/reset")
    assert r.status_code == 200
    assert r.json()["reset"] is True


def test_health(client):
    r = client.get("/api/diagnostics/omni/health")
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["offline_only"] is True


def test_run_concurrent(client):
    """Ejecutar suite multiple veces no corrompe estado."""
    for _ in range(3):
        r = client.post("/api/diagnostics/omni/run")
        assert r.status_code == 200
        assert r.json()["verdict"] == "sovereign_ready"
