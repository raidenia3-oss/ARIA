"""Tests Bloque 50 — AURA P2P Offline Sync & Conflict Resolution Engine.

Valida:
- Registro y listado de dispositivos
- Comparación de versiones (hash + version vector)
- Resolución de conflictos (LWW, merge, backup automático)
- Payload diferencial
- Log de conflictos
- WebSocket básico
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect

from backend.sync.engine import (
    P2PSyncEngine,
    get_p2p_sync_engine,
    reset_p2p_sync_engine,
)
from backend.sync.engine import router as p2p_sync_router


@pytest.fixture(autouse=True)
def _reset_engine():
    reset_p2p_sync_engine()
    yield
    reset_p2p_sync_engine()


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_SYNC_DIR", str(tmp_path / "sync"))
    monkeypatch.setenv("AURA_STORY_DIR", str(tmp_path / "story"))
    app = FastAPI()
    app.include_router(p2p_sync_router)
    return TestClient(app)


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_SYNC_DIR", str(tmp_path / "sync"))
    monkeypatch.setenv("AURA_STORY_DIR", str(tmp_path / "story"))
    reset_p2p_sync_engine()
    eng = get_p2p_sync_engine()
    yield eng
    reset_p2p_sync_engine()


def test_register_device(client):
    r = client.post("/api/sync/register", json={"device_id": "ame_1", "name": "Pixel 7"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "registered"
    assert body["device_id"] == "ame_1"


def test_list_devices(client):
    client.post("/api/sync/register", json={"device_id": "ame_1", "name": "Pixel 7"})
    client.post("/api/sync/register", json={"device_id": "ame_2", "name": "iPhone 15"})
    r = client.get("/api/sync/devices")
    assert r.status_code == 200
    body = r.json()
    assert len(body["devices"]) == 2


def test_get_device(client):
    client.post("/api/sync/register", json={"device_id": "ame_1", "name": "Pixel 7"})
    r = client.get("/api/sync/devices/ame_1")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["device"]["device_id"] == "ame_1"


def test_compare_versions_in_sync(client):
    # Register device first
    client.post("/api/sync/register", params={"device_id": "ame_1"})

    # Create a document on PC side first
    import os
    import tempfile

    from backend.story_memory.character_bible import CharacterBible
    from backend.story_memory.story_storage import StoryStorage

    # We need to set up a work with a character
    story_dir = Path(os.getenv("AURA_STORY_DIR", "/tmp"))
    storage = StoryStorage(store_dir=str(story_dir))
    storage.create_work(work_id="w1", title="Test Work")
    cb = CharacterBible()
    cb.create(work_id="w1", char_id="hero", name="Hero", voice="heroica")

    engine = get_p2p_sync_engine()
    pc_version = engine._load_current_version("w1", "character", "hero")
    assert pc_version is not None

    # Compare with same hash -> in_sync
    r = client.post(
        "/api/sync/compare",
        params={
            "device_id": "ame_1",
            "work_id": "w1",
            "doc_type": "character",
            "doc_id": "hero",
        },
        json={
            "mobile_hash": pc_version.version_hash,
            "mobile_version_vector": {"mobile": 1},
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "in_sync"
    assert body["doc_id"] == "hero"


def test_compare_versions_conflict(client):
    client.post("/api/sync/register", params={"device_id": "ame_1"})

    import os

    from backend.story_memory.character_bible import CharacterBible
    from backend.story_memory.story_storage import StoryStorage

    story_dir = Path(os.getenv("AURA_STORY_DIR", "/tmp"))
    storage = StoryStorage(store_dir=str(story_dir))
    storage.create_work(work_id="w1", title="Test Work")
    cb = CharacterBible()
    cb.create(work_id="w1", char_id="hero", name="Hero", voice="heroica")

    engine = get_p2p_sync_engine()
    pc_version = engine._load_current_version("w1", "character", "hero")
    assert pc_version is not None

    # Different hash -> conflict
    r = client.post(
        "/api/sync/compare",
        params={
            "device_id": "ame_1",
            "work_id": "w1",
            "doc_type": "character",
            "doc_id": "hero",
        },
        json={
            "mobile_hash": "different_hash",
            "mobile_version_vector": {"mobile": 2},
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "conflict"
    assert "pc_version" in body
    assert "mobile_version" in body
    assert "resolution_options" in body


def test_resolve_conflict_lww_mobile(client):
    client.post("/api/sync/register", params={"device_id": "ame_1"})

    import os

    from backend.story_memory.character_bible import CharacterBible
    from backend.story_memory.story_storage import StoryStorage

    story_dir = Path(os.getenv("AURA_STORY_DIR", "/tmp"))
    storage = StoryStorage(store_dir=str(story_dir))
    storage.create_work(work_id="w1", title="Test Work")
    cb = CharacterBible()
    cb.create(work_id="w1", char_id="hero", name="Hero", voice="heroica")

    engine = get_p2p_sync_engine()
    pc_version = engine._load_current_version("w1", "character", "hero")
    mobile_payload = {"char_id": "hero", "name": "Hero Mobile", "voice": "mobile"}

    r = client.post(
        "/api/sync/resolve",
        params={
            "device_id": "ame_1",
            "work_id": "w1",
            "doc_type": "character",
            "doc_id": "hero",
        },
        json={
            "mobile_payload": mobile_payload,
            "mobile_hash": "different_hash",
            "mobile_version_vector": {"mobile": 2},
            "strategy": "lww_mobile",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "resolved"
    assert "conflict" in body
    assert body["conflict"]["resolution_strategy"] == "lww_mobile"


def test_resolve_conflict_merge(client):
    client.post("/api/sync/register", params={"device_id": "ame_1"})

    import os

    from backend.story_memory.character_bible import CharacterBible
    from backend.story_memory.story_storage import StoryStorage

    story_dir = Path(os.getenv("AURA_STORY_DIR", "/tmp"))
    storage = StoryStorage(store_dir=str(story_dir))
    storage.create_work(work_id="w1", title="Test Work")
    cb = CharacterBible()
    cb.create(work_id="w1", char_id="hero", name="Hero", voice="heroica", personality=["brave"])

    engine = get_p2p_sync_engine()
    pc_version = engine._load_current_version("w1", "character", "hero")
    mobile_payload = {
        "char_id": "hero",
        "name": "Hero",
        "voice": "heroica",
        "personality": ["brave", "wise"],
        "new_field": "test",
    }

    r = client.post(
        "/api/sync/resolve",
        params={
            "device_id": "ame_1",
            "work_id": "w1",
            "doc_type": "character",
            "doc_id": "hero",
        },
        json={
            "mobile_payload": mobile_payload,
            "mobile_hash": "different_hash",
            "mobile_version_vector": {"mobile": 2},
            "strategy": "merge",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "resolved"
    assert body["conflict"]["resolution_strategy"] == "merge"
    assert body["resolved_version"] is not None


def test_get_conflict_log(client):
    client.post("/api/sync/register", params={"device_id": "ame_1"})

    import os

    from backend.story_memory.character_bible import CharacterBible
    from backend.story_memory.story_storage import StoryStorage

    story_dir = Path(os.getenv("AURA_STORY_DIR", "/tmp"))
    storage = StoryStorage(store_dir=str(story_dir))
    storage.create_work(work_id="w1", title="Test Work")
    cb = CharacterBible()
    cb.create(work_id="w1", char_id="hero", name="Hero", voice="heroica")

    engine = get_p2p_sync_engine()
    pc_version = engine._load_current_version("w1", "character", "hero")
    mobile_payload = {"char_id": "hero", "name": "Hero Mobile"}

    client.post(
        "/api/sync/resolve",
        params={
            "device_id": "ame_1",
            "work_id": "w1",
            "doc_type": "character",
            "doc_id": "hero",
        },
        json={
            "mobile_payload": mobile_payload,
            "mobile_hash": "different_hash",
            "mobile_version_vector": {"mobile": 2},
            "strategy": "lww_mobile",
        },
    )

    r = client.get("/api/sync/conflicts")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert len(body["conflicts"]) >= 1


def test_sync_status(client):
    r = client.get("/api/sync/status")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "devices" in body
    assert "total_conflicts" in body


def test_differential_payload(client):
    client.post("/api/sync/register", params={"device_id": "ame_1"})

    import os

    from backend.story_memory.character_bible import CharacterBible
    from backend.story_memory.story_storage import StoryStorage

    story_dir = Path(os.getenv("AURA_STORY_DIR", "/tmp"))
    storage = StoryStorage(store_dir=str(story_dir))
    storage.create_work(work_id="w1", title="Test Work")
    cb = CharacterBible()
    cb.create(work_id="w1", char_id="hero", name="Hero", voice="heroica")

    r = client.post(
        "/api/sync/differential",
        params={"device_id": "ame_1", "work_id": "w1"},
        json={"since_version_vector": {"pc": 0, "mobile": 0}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "changes" in body


def test_ack_sync(client):
    client.post("/api/sync/register", params={"device_id": "ame_1"})

    r = client.post(
        "/api/sync/ack",
        params={"device_id": "ame_1", "work_id": "w1"},
        json={"applied_changes": []},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "acknowledged"


def test_full_reconcile(client):
    client.post("/api/sync/register", params={"device_id": "ame_1"})

    import os

    from backend.story_memory.character_bible import CharacterBible
    from backend.story_memory.story_storage import StoryStorage

    story_dir = Path(os.getenv("AURA_STORY_DIR", "/tmp"))
    storage = StoryStorage(store_dir=str(story_dir))
    storage.create_work(work_id="w1", title="Test Work")
    cb = CharacterBible()
    cb.create(work_id="w1", char_id="hero", name="Hero", voice="heroica")

    engine = get_p2p_sync_engine()
    pc_version = engine._load_current_version("w1", "character", "hero")

    r = client.post(
        "/api/sync/reconcile",
        params={"device_id": "ame_1", "work_id": "w1"},
        json={
            "versions": [
                {
                    "doc_type": "character",
                    "doc_id": "hero",
                    "hash": pc_version.version_hash,
                    "version_vector": {"mobile": 1},
                }
            ]
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["in_sync"] >= 1


# --- WebSocket Tests ---


def test_websocket_welcome(client):
    with client.websocket_connect("/api/sync/ws/ame_test_1") as ws:
        data = ws.receive_json()
        assert data["type"] == "welcome"
        assert data["device_id"] == "ame_test_1"


def test_websocket_ping(client):
    with client.websocket_connect("/api/sync/ws/ame_test_2") as ws:
        # Skip welcome
        ws.receive_json()

        ws.send_json({"type": "ping", "request_id": "req-1"})
        data = ws.receive_json()
        assert data["type"] == "pong"
        assert data["request_id"] == "req-1"


def test_websocket_status(client):
    with client.websocket_connect("/api/sync/ws/ame_test_3") as ws:
        ws.receive_json()  # welcome

        ws.send_json({"type": "status", "request_id": "req-2"})
        data = ws.receive_json()
        assert data["type"] == "status_result"
        assert data["payload"]["status"] == "ok"


def test_websocket_compare(client):
    import os

    from backend.story_memory.character_bible import CharacterBible
    from backend.story_memory.story_storage import StoryStorage

    story_dir = Path(os.getenv("AURA_STORY_DIR", "/tmp"))
    storage = StoryStorage(store_dir=str(story_dir))
    storage.create_work(work_id="w1", title="Test Work")
    cb = CharacterBible()
    cb.create(work_id="w1", char_id="hero", name="Hero", voice="heroica")

    engine = get_p2p_sync_engine()
    pc_version = engine._load_current_version("w1", "character", "hero")

    with client.websocket_connect("/api/sync/ws/ame_test_4") as ws:
        ws.receive_json()  # welcome

        ws.send_json(
            {
                "type": "compare",
                "device_id": "ame_test_4",
                "work_id": "w1",
                "payload": {
                    "doc_type": "character",
                    "doc_id": "hero",
                    "mobile_hash": pc_version.version_hash,
                    "mobile_version_vector": {"mobile": 1},
                },
                "request_id": "req-3",
            }
        )
        data = ws.receive_json()
        assert data["type"] == "compare_result"
        assert data["payload"]["status"] == "in_sync"


def test_websocket_resolve(client):
    import os

    from backend.story_memory.character_bible import CharacterBible
    from backend.story_memory.story_storage import StoryStorage

    story_dir = Path(os.getenv("AURA_STORY_DIR", "/tmp"))
    storage = StoryStorage(store_dir=str(story_dir))
    storage.create_work(work_id="w1", title="Test Work")
    cb = CharacterBible()
    cb.create(work_id="w1", char_id="hero", name="Hero", voice="heroica")

    engine = get_p2p_sync_engine()
    pc_version = engine._load_current_version("w1", "character", "hero")

    with client.websocket_connect("/api/sync/ws/ame_test_5") as ws:
        ws.receive_json()  # welcome

        ws.send_json(
            {
                "type": "resolve",
                "device_id": "ame_test_5",
                "work_id": "w1",
                "payload": {
                    "doc_type": "character",
                    "doc_id": "hero",
                    "mobile_payload": {"char_id": "hero", "name": "Hero Mobile"},
                    "mobile_hash": "different_hash",
                    "mobile_version_vector": {"mobile": 2},
                    "strategy": "lww_mobile",
                },
                "request_id": "req-4",
            }
        )
        data = ws.receive_json()
        assert data["type"] == "resolve_result"
        assert data["payload"]["status"] == "resolved"


def test_engine_persistence(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_SYNC_DIR", str(tmp_path / "sync"))
    monkeypatch.setenv("AURA_STORY_DIR", str(tmp_path / "story"))

    eng1 = get_p2p_sync_engine()
    eng1.register_device("test_device", {"name": "Test"})

    # Restart engine
    reset_p2p_sync_engine()
    eng2 = get_p2p_sync_engine()

    devices = eng2.list_devices()
    assert len(devices["devices"]) == 1
    assert devices["devices"][0]["device_id"] == "test_device"
