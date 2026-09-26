"""BLOQUE 91 - tests for WebSocket channel & router mounting (local, offline)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.refactoring.engine import get_engine, reset_engine, router


@pytest.fixture(autouse=True)
def _reset():
    reset_engine()
    yield
    reset_engine()


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_ws_heartbeat():
    c = _client()
    with c.websocket_connect("/api/refactoring/ws") as ws:
        msg = ws.receive_json()
    assert msg["event"] == "heartbeat"
    assert msg["offline_only"] is True
    assert "metrics" in msg and "patches" in msg


def test_router_endpoints_available():
    c = _client()
    assert c.get("/api/refactoring/status").status_code == 200
    assert c.get("/api/refactoring/patches").status_code == 200
    assert c.post("/api/refactoring/reset").json()["reset"] is True


def test_router_is_instance_of_api_router():
    from fastapi import APIRouter

    assert isinstance(router, APIRouter)
    assert router.prefix == "/api/refactoring"
