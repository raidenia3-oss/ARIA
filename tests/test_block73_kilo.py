"""REST integration tests for Bloque 73 - Desktop Window Manager API.

Uses a minimal FastAPI app with only the window router mounted
to avoid heavy imports from backend.main (HuggingFace API calls).
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Patch storage dir before importing
_tmp = tempfile.mkdtemp(prefix="aura_win_test_")
os.environ["AURA_LAYOUTS_DIR"] = _tmp


@pytest.fixture(autouse=True)
def _reset():
    from backend.desktop.window_manager import reset_window_manager

    reset_window_manager()
    yield
    reset_window_manager()


@pytest.fixture
def client():
    from backend.desktop.window_manager import reset_window_manager

    reset_window_manager()

    app = FastAPI(title="AURA Windows Test", version="test")
    from backend.desktop.window_routes import router as window_router

    app.include_router(window_router)

    with TestClient(app) as c:
        yield c

    reset_window_manager()
    shutil.rmtree(_tmp, ignore_errors=True)


class TestMonitorsEndpoint:
    def test_monitors_returns_200(self, client):
        r = client.get("/api/desktop/windows/monitors")
        assert r.status_code == 200
        body = r.json()
        assert "count" in body
        assert "monitors" in body
        assert isinstance(body["monitors"], list)


class TestWindowsListEndpoint:
    def test_list_returns_200(self, client):
        r = client.get("/api/desktop/windows/list")
        assert r.status_code == 200
        body = r.json()
        assert "count" in body
        assert "windows" in body
        assert isinstance(body["windows"], list)

    def test_list_visible_only_param(self, client):
        r = client.get("/api/desktop/windows/list?visible_only=false")
        assert r.status_code == 200


class TestLayoutEndpoints:
    def test_create_and_list_layout(self, client):
        r = client.post(
            "/api/desktop/windows/layouts",
            json={"name": "TestLayout", "description": "d", "slots": [{"title_substring": "foo"}]},
        )
        assert r.status_code == 200
        created = r.json()
        assert created["name"] == "TestLayout"
        assert len(created["slots"]) == 1

        r2 = client.get("/api/desktop/windows/layouts")
        assert r2.status_code == 200
        body = r2.json()
        assert body["count"] >= 1
        assert any(l["name"] == "TestLayout" for l in body["layouts"])

    def test_apply_missing_layout(self, client):
        r = client.post(
            "/api/desktop/windows/layouts/apply",
            json={"layout_id": "nonexistent-id"},
        )
        assert r.status_code == 404

    def test_delete_layout(self, client):
        r = client.post(
            "/api/desktop/windows/layouts",
            json={"name": "ToDelete", "slots": [{"title_substring": "x"}]},
        )
        layout_id = r.json()["layout_id"]
        r2 = client.delete(f"/api/desktop/windows/layouts/{layout_id}")
        assert r2.status_code == 200
        assert r2.json()["deleted"] is True

    def test_delete_missing_layout(self, client):
        r = client.delete("/api/desktop/windows/layouts/missing-id")
        assert r.status_code == 404

    def test_capture_layout(self, client):
        r = client.post(
            "/api/desktop/windows/layouts/capture",
            json={"name": "Captured", "description": "auto"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "Captured"


class TestWindowActionEndpoints:
    def test_move_invalid_handle(self, client):
        r = client.post(
            "/api/desktop/windows/move",
            json={"handle": 99999999, "x": 0, "y": 0, "width": 100, "height": 100},
        )
        assert r.status_code in (200, 400)

    def test_focus_invalid_handle(self, client):
        r = client.post("/api/desktop/windows/focus", params={"handle": 99999999})
        assert r.status_code in (200, 400)

    def test_maximize_invalid_handle(self, client):
        r = client.post("/api/desktop/windows/maximize", params={"handle": 99999999})
        assert r.status_code in (200, 400)

    def test_restore_invalid_handle(self, client):
        r = client.post("/api/desktop/windows/restore", params={"handle": 99999999})
        assert r.status_code in (200, 400)

    def test_close_invalid_handle(self, client):
        r = client.post("/api/desktop/windows/close", params={"handle": 99999999})
        assert r.status_code in (200, 400)
