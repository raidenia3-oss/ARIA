from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import os

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture(autouse=True)
def set_api_key(monkeypatch):
    monkeypatch.setenv("AURA_API_KEY", "test-key")
    monkeypatch.setenv("AURA_JWT_SECRET", "test-secret")


@pytest.fixture()
def client():
    return TestClient(app)


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_login_returns_token(client):
    response = client.post("/token", data={"username": "user@example.com", "password": "secret"})
    assert response.status_code == 400


def test_status_endpoint_requires_api_key(client):
    response = client.get("/api/status")
    assert response.status_code == 401


def test_status_endpoint_with_api_key(client):
    response = client.get("/api/status", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    payload = response.json()
    assert "backend" in payload


def test_logs_endpoint_persists_entries(client):
    client.post(
        "/api/logs",
        json={"service": "backend", "level": "INFO", "message": "test log"},
        headers={"X-API-Key": "test-key"},
    )
    response = client.get("/api/logs?service=backend&lines=10", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "backend"
    assert "test log" in payload["logs"]


def test_restart_endpoint_updates_status(client):
    response = client.post(
        "/api/restart",
        json={"service": "backend"},
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    assert "restarted" in response.json()["message"]


def test_deploy_endpoint_updates_status(client):
    response = client.post(
        "/api/deploy",
        json={"service": "discord-bot"},
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    assert "deployed" in response.json()["message"]


def test_training_status_endpoint(client):
    response = client.get("/api/training/status", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    payload = response.json()
    assert "jobs" in payload


def test_metrics_endpoint_returns_prometheus(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text
