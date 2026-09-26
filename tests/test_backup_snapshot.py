"""Tests Bloque 49 — Local Automated Backup & Version Snapshot Engine.

Valida:
- Creación de snapshots comprimidos con todos los componentes.
- Listado, obtención y eliminación de snapshots.
- Restauración de obra desde snapshot.
- Limpieza de snapshots antiguos.
- Endpoints REST /api/story/{work_id}/snapshots.
"""

from __future__ import annotations

import io
import os
import time
import zipfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.backup.snapshot import (
    LocalSnapshotEngine,
    get_backup_engine,
    reset_backup_engine,
)
from backend.story_memory.canon_tracker import CanonTracker
from backend.story_memory.chapter_planner import ChapterPlanner
from backend.story_memory.character_bible import CharacterBible
from backend.story_memory.story_storage import StoryStorage


@pytest.fixture
def temp_story_dir(tmp_path, monkeypatch):
    story_dir = str(tmp_path / "story_memory")
    os.makedirs(story_dir, exist_ok=True)
    monkeypatch.setenv("AURA_STORY_DIR", story_dir)
    return story_dir


@pytest.fixture
def engine(temp_story_dir):
    reset_backup_engine()
    eng = get_backup_engine(store_dir=temp_story_dir)
    # Pre-create a work for testing with characters and canon
    storage = StoryStorage(store_dir=temp_story_dir)
    storage.create_work(work_id="w1", title="Test Work", universe="U", description="d", author="t")
    cb = CharacterBible()
    cb.create(work_id="w1", char_id="hero", name="Hero", voice="heroica")
    cb.create(work_id="w1", char_id="villain", name="Villain", voice="oscura")
    ct = CanonTracker()
    ct.add_canon_event(work_id="w1", description="Evento canon 1")
    yield eng
    reset_backup_engine()


@pytest.fixture
def work_with_data(temp_story_dir):
    storage = StoryStorage(store_dir=temp_story_dir)
    storage.create_work(
        work_id="backup_w", title="Obra Backup", universe="U", description="d", author="t"
    )
    cb = CharacterBible()
    cb.create(work_id="backup_w", char_id="hero", name="Aldric", voice="heroica")
    cb.create(work_id="backup_w", char_id="villain", name="Malakar", voice="oscura")
    ct = CanonTracker()
    ct.add_canon_event(work_id="backup_w", description="Fundación de Bruma")
    ct.add_canon_event(work_id="backup_w", description="Guerra de los Cielos")
    cp = ChapterPlanner()
    cp.create_chapter(work_id="backup_w", title="Capítulo 1", beat_summary="Inicio")
    cp.create_chapter(work_id="backup_w", title="Capítulo 2", beat_summary="Desarrollo")
    return temp_story_dir


def test_create_snapshot_basic(engine):
    res = engine.create_snapshot("w1", message="test", author="test")
    assert res["status"] == "created"
    snap = res["snapshot"]
    assert snap["snapshot_id"].startswith("snap_")
    assert snap["work_id"] == "w1"
    assert snap["message"] == "test"
    assert snap["author"] == "test"
    assert "work_meta" in snap["components"]
    assert "characters" in snap["components"]
    assert "canon" in snap["components"]
    assert snap["total_files"] > 0
    assert snap["total_bytes"] > 0
    assert snap["sha256"]
    # Verificar que el ZIP existe
    zip_path = engine.store_dir / snap["zip_path"]
    assert zip_path.exists()
    # Verificar contenido del ZIP
    with zipfile.ZipFile(zip_path, "r") as zf:
        assert "manifest.json" in zf.namelist()
        assert "work_meta.json" in zf.namelist()
        assert "characters.json" in zf.namelist()
        assert "canon.json" in zf.namelist()


def test_create_snapshot_selective_components(engine):
    res = engine.create_snapshot("w1", components=["work_meta", "characters"])
    assert res["status"] == "created"
    snap = res["snapshot"]
    assert set(snap["components"]) == {"work_meta", "characters"}


def test_list_snapshots(engine):
    engine.create_snapshot("w1", message="snap1")
    engine.create_snapshot("w1", message="snap2")
    lst = engine.list_snapshots("w1")
    assert lst["status"] == "ok"
    assert lst["count"] == 2
    assert lst["snapshots"][0]["message"] == "snap1"
    assert lst["snapshots"][1]["message"] == "snap2"


def test_get_snapshot(engine):
    res = engine.create_snapshot("w1", message="test")
    snap_id = res["snapshot"]["snapshot_id"]
    g = engine.get_snapshot("w1", snap_id)
    assert g["status"] == "ok"
    assert g["snapshot"]["snapshot_id"] == snap_id


def test_delete_snapshot(engine):
    res = engine.create_snapshot("w1", message="test")
    snap_id = res["snapshot"]["snapshot_id"]
    d = engine.delete_snapshot("w1", snap_id)
    assert d["status"] == "deleted"
    assert engine.get_snapshot("w1", snap_id)["status"] == "error"
    # ZIP debe haber sido eliminado
    lst = engine.list_snapshots("w1")
    assert lst["count"] == 0


def test_cleanup_old_keeps_recent(engine):
    # Crear 5 snapshots con timestamps diferentes
    for i in range(5):
        engine.create_snapshot("w1", message=f"snap{i}")
        time.sleep(0.01)  # Ensure different timestamps
    # Mantener 3, eliminar los 2 más antiguos
    removed = engine.cleanup_old("w1", keep=3, max_age_days=30)
    assert removed == 2
    lst = engine.list_snapshots("w1")
    assert lst["count"] == 3


def test_restore_snapshot_creates_new_work(engine, work_with_data):
    reset_backup_engine()
    eng = get_backup_engine(store_dir=work_with_data)
    # Crear snapshot de la obra con datos
    res = eng.create_snapshot("backup_w", message="full backup")
    snap_id = res["snapshot"]["snapshot_id"]

    # Restaurar a nueva obra
    restored = eng.restore_snapshot("backup_w", snap_id, target_work_id="restored_w")
    assert restored["status"] == "restored"
    assert restored["target_work_id"] == "restored_w"
    assert "characters" in restored["restored_components"]
    assert "canon" in restored["restored_components"]
    assert "chapters" in restored["restored_components"]

    # Verificar que la obra restaurada tiene los datos
    storage = StoryStorage(store_dir=work_with_data)
    assert storage.work_exists("restored_w")
    cb = CharacterBible()
    chars = cb.list("restored_w")
    assert len(chars) == 2
    ct = CanonTracker()
    events = ct.get_all_events("restored_w")
    assert len(events) == 2
    cp = ChapterPlanner()
    chaps = cp.list_chapters("restored_w")
    assert len(chaps) == 2
    reset_backup_engine()


def test_persistence_across_restart(engine, temp_story_dir):
    res = engine.create_snapshot("w1", message="persist test")
    snap_id = res["snapshot"]["snapshot_id"]
    reset_backup_engine()
    eng2 = get_backup_engine(store_dir=temp_story_dir)
    lst = eng2.list_snapshots("w1")
    assert lst["count"] == 1
    assert lst["snapshots"][0]["snapshot_id"] == snap_id
    reset_backup_engine()


def test_snapshot_includes_optional_components(engine, work_with_data):
    reset_backup_engine()
    eng = get_backup_engine(store_dir=work_with_data)
    res = eng.create_snapshot(
        "backup_w", components=["work_meta", "graph", "timeline", "gazetteer"]
    )
    assert res["status"] == "created"
    # Los componentes opcionales pueden o no estar según disponibilidad
    reset_backup_engine()


# --- REST endpoints tests ---


def _rest_setup(monkeypatch, tmp_path):
    from backend.backup.routes import router
    from backend.backup.snapshot import reset_backup_engine

    story_dir = str(tmp_path / "story")
    os.makedirs(story_dir, exist_ok=True)
    monkeypatch.setenv("AURA_STORY_DIR", story_dir)
    reset_backup_engine()
    storage = StoryStorage(store_dir=story_dir)
    storage.create_work(
        work_id="rest_backup", title="REST Backup", universe="u", description="d", author="t"
    )
    cb = CharacterBible()
    cb.create(work_id="rest_backup", char_id="hero", name="Hero")
    ct = CanonTracker()
    ct.add_canon_event(work_id="rest_backup", description="Evento 1")
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    yield client
    reset_backup_engine()


def test_rest_create_snapshot(monkeypatch, tmp_path):
    for client in _rest_setup(monkeypatch, tmp_path):
        r = client.post("/api/story/rest_backup/snapshots", params={"message": "test backup"})
        assert r.status_code == 201
        data = r.json()
        assert data["status"] == "created"
        assert "snapshot" in data
        assert data["snapshot"]["message"] == "test backup"


def test_rest_list_snapshots(monkeypatch, tmp_path):
    for client in _rest_setup(monkeypatch, tmp_path):
        client.post("/api/story/rest_backup/snapshots", params={"message": "snap1"})
        client.post("/api/story/rest_backup/snapshots", params={"message": "snap2"})
        lst = client.get("/api/story/rest_backup/snapshots")
        assert lst.status_code == 200
        assert lst.json()["count"] == 2


def test_rest_get_snapshot(monkeypatch, tmp_path):
    for client in _rest_setup(monkeypatch, tmp_path):
        r = client.post("/api/story/rest_backup/snapshots", params={"message": "snap1"})
        snap_id = r.json()["snapshot"]["snapshot_id"]
        g = client.get(f"/api/story/rest_backup/snapshots/{snap_id}")
        assert g.status_code == 200
        assert g.json()["snapshot"]["snapshot_id"] == snap_id


def test_rest_restore_snapshot(monkeypatch, tmp_path):
    for client in _rest_setup(monkeypatch, tmp_path):
        r = client.post("/api/story/rest_backup/snapshots", params={"message": "snap1"})
        snap_id = r.json()["snapshot"]["snapshot_id"]
        res = client.post(
            f"/api/story/rest_backup/snapshots/{snap_id}/restore",
            params={"target_work_id": "restored_rest"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "restored"
        assert data["target_work_id"] == "restored_rest"


def test_rest_delete_snapshot(monkeypatch, tmp_path):
    for client in _rest_setup(monkeypatch, tmp_path):
        r = client.post("/api/story/rest_backup/snapshots", params={"message": "snap1"})
        snap_id = r.json()["snapshot"]["snapshot_id"]
        d = client.delete(f"/api/story/rest_backup/snapshots/{snap_id}")
        assert d.status_code == 200
        assert d.json()["status"] == "deleted"
        g = client.get(f"/api/story/rest_backup/snapshots/{snap_id}")
        assert g.status_code == 404


def test_rest_cleanup(monkeypatch, tmp_path):
    for client in _rest_setup(monkeypatch, tmp_path):
        for i in range(5):
            client.post("/api/story/rest_backup/snapshots", params={"message": f"snap{i}"})
            time.sleep(0.01)
        cl = client.post(
            "/api/story/rest_backup/snapshots/cleanup", params={"keep": 2, "max_age_days": 30}
        )
        assert cl.status_code == 200
        assert cl.json()["removed"] == 3
        lst = client.get("/api/story/rest_backup/snapshots")
        assert lst.json()["count"] == 2


def test_rest_work_not_found(monkeypatch, tmp_path):
    for client in _rest_setup(monkeypatch, tmp_path):
        r = client.post("/api/story/ghost/snapshots", params={"message": "test"})
        assert r.status_code == 404
