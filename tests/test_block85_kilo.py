"""BLOQUE 85 - REST + WS tests for /api/recovery (offline)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.recovery.recovery_routes import router
from backend.recovery.snapshot import reset_recovery_engine


@pytest.fixture
def client(tmp_path, monkeypatch):
    store = tmp_path / "store"
    monkeypatch.setenv("AURA_RECOVERY_DIR", str(store))
    import backend.recovery.snapshot as _s

    _s.STORE_SUBDIR = str(store)
    reset_recovery_engine()
    src = tmp_path / "src"
    src.mkdir()
    (src / "f.txt").write_text("data", encoding="utf-8")
    app = FastAPI(title="AURA Recovery Test", version="test")
    app.include_router(router)
    with TestClient(app) as c:
        c.src_dir = str(src)
        c.out_dir = str(tmp_path / "out")
        yield c
    reset_recovery_engine()


def test_status(client):
    r = client.get("/api/recovery/status")
    assert r.status_code == 200 and r.json()["offline_only"] is True


def test_full_lifecycle(client):
    r = client.post(
        "/api/recovery/snapshot", json={"sources": {"docs": client.src_dir}, "label": "web"}
    )
    assert r.status_code == 200
    sid = r.json()["snapshot_id"]
    assert r.json()["verified"] is True
    l = client.get("/api/recovery/snapshots")
    assert l.json()["count"] == 1
    v = client.post(f"/api/recovery/snapshots/{sid}/verify")
    assert v.json()["verified"] is True
    d = client.get(f"/api/recovery/snapshots/{sid}")
    assert d.status_code == 200
    rr = client.post(
        f"/api/recovery/snapshots/{sid}/restore",
        json={"dest_dir": client.out_dir, "overwrite": True},
    )
    assert rr.json()["restored"] is True
    rec = client.get("/api/recovery/recoveries")
    assert rec.json()["count"] == 1
    dl = client.delete(f"/api/recovery/snapshots/{sid}")
    assert dl.json()["deleted"] is True


def test_rejects_empty_sources(client):
    assert client.post("/api/recovery/snapshot", json={"sources": {}}).status_code == 422


def test_restore_needs_dest(client):
    r = client.post("/api/recovery/snapshot", json={"sources": {"d": client.src_dir}})
    sid = r.json()["snapshot_id"]
    assert (
        client.post(f"/api/recovery/snapshots/{sid}/restore", json={"dest_dir": ""}).status_code
        == 422
    )


def test_404s(client):
    assert client.get("/api/recovery/snapshots/nope").status_code == 404
    assert client.delete("/api/recovery/snapshots/nope").status_code == 404


def test_ws_heartbeat(client):
    with client.websocket_connect("/api/recovery/ws") as ws:
        d = ws.receive_json()
        assert d["event"] == "heartbeat" and d["offline_only"] is True
