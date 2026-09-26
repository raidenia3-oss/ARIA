"""Tests Bloque 32 — Literary Snapshot Engine (Git-lite versioning).

Valida:
- Creación de snapshots con manifest y hash canónico.
- Listado y recuperación de snapshots.
- Branches narrativas (ramificación y restauración).
- Diff entre snapshots.
- Export para Discord Vault Auto-Backup.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

from backend.story_memory.versioning import (
    LiterarySnapshotEngine,
    get_snapshot_engine,
    set_engine_store_path,
)


@pytest.fixture
def engine(tmp_path, monkeypatch):
    """Engine con storage temporal aislado."""
    story_dir = str(tmp_path / "story")
    monkeypatch.setenv("AURA_STORY_DIR", story_dir)
    set_engine_store_path(story_dir)
    eng = get_snapshot_engine()
    yield eng
    set_engine_store_path(None)


@pytest.fixture
def work_with_canon(engine):
    """Crea una obra + canon para tests de snapshot."""
    from backend.story_memory.canon_tracker import CanonTracker
    from backend.story_memory.story_storage import StoryStorage

    store = StoryStorage(store_dir=engine.store_dir)
    store.create_work(
        work_id="obra_test", title="Obra Test", universe="test", description="d", author="tester"
    )
    ct = CanonTracker()
    ct.add_canon_event(work_id="obra_test", description="El héroe nace", source="user")
    ct.add_canon_event(work_id="obra_test", description="El héroe salva el mundo", source="user")
    return engine


def test_create_snapshot_returns_manifest(work_with_canon):
    """Snapshot creado con manifest, hash y metadatos."""
    result = work_with_canon.create_snapshot(
        "obra_test", message="primer checkpoint", author="tester"
    )
    assert result["status"] == "created"
    snap = result["snapshot"]
    assert snap["work_id"] == "obra_test"
    assert snap["message"] == "primer checkpoint"
    assert snap["author"] == "tester"
    assert snap["branch"] == "main"
    assert len(snap["canon_hash"]) == 64  # SHA-256 hex
    assert snap["parent"] is None


def test_list_snapshots_after_create(work_with_canon):
    """Listado retorna snapshots creados."""
    work_with_canon.create_snapshot("obra_test")
    work_with_canon.create_snapshot("obra_test", message="segundo")
    snaps = work_with_canon.list_snapshots("obra_test")
    assert len(snaps) == 2
    assert snaps[1]["message"] == "segundo"


def test_get_snapshot_retrieves_data(work_with_canon):
    """Recupera snapshot con manifest y data serializada."""
    create = work_with_canon.create_snapshot("obra_test", message="data check")
    snap_id = create["snapshot"]["snapshot_id"]

    snap = work_with_canon.get_snapshot("obra_test", snap_id)
    assert snap is not None
    assert snap["manifest"]["snapshot_id"] == snap_id
    assert "work" in snap["data"]
    assert len(snap["data"]["canon"]) == 2


def test_snapshot_not_found_returns_none(work_with_canon):
    """Snapshot ID inexistente retorna None."""
    assert work_with_canon.get_snapshot("obra_test", "nonexistent") is None


def test_list_branches_defaults_to_main(engine):
    """Una obra nueva sin snapshots lista 'main' como branch."""
    from backend.story_memory.story_storage import StoryStorage

    store = StoryStorage(store_dir=engine.store_dir)
    store.create_work(work_id="w", title="W")
    branches = engine.list_branches("w")
    assert branches == ["main"]


def test_create_branch_and_restore(work_with_canon):
    """Restaurar un snapshot crea una nueva rama."""
    create = work_with_canon.create_snapshot("obra_test", message="restore point")
    snap_id = create["snapshot"]["snapshot_id"]

    result = work_with_canon.restore_snapshot("obra_test", snap_id)
    assert result["status"] == "restored"
    assert result["snapshot_id"] == snap_id
    assert result["restored_to_branch"] is not None

    branches = work_with_canon.list_branches("obra_test")
    assert any("restored" in b for b in branches)


def test_diff_snapshots_detects_changes(work_with_canon):
    """Diff detecta cambios en canon entre dos snapshots."""
    from backend.story_memory.canon_tracker import CanonTracker

    ct = CanonTracker()

    snap_a = work_with_canon.create_snapshot("obra_test", message="antes")
    ct.add_canon_event(work_id="obra_test", description="Nueva revelación canónica", source="user")
    snap_b = work_with_canon.create_snapshot("obra_test", message="después")

    diff = work_with_canon.diff_snapshots(
        "obra_test", snap_a["snapshot"]["snapshot_id"], snap_b["snapshot"]["snapshot_id"]
    )
    assert diff["status"] == "ok"
    assert diff["changed"] is True
    assert len(diff["canon_diff"]["added"]) == 1


def test_diff_snapshots_same_content(work_with_canon):
    """Diff entre snapshots idénticos no reporta cambios."""
    snap_a = work_with_canon.create_snapshot("obra_test", message="a")
    snap_b = work_with_canon.create_snapshot("obra_test", message="b")

    diff = work_with_canon.diff_snapshots(
        "obra_test", snap_a["snapshot"]["snapshot_id"], snap_b["snapshot"]["snapshot_id"]
    )
    assert diff["changed"] is False


def test_export_snapshot_returns_json(work_with_canon):
    """Export serializa el snapshot como JSON válido."""
    create = work_with_canon.create_snapshot("obra_test")
    snap_id = create["snapshot"]["snapshot_id"]

    json_str = work_with_canon.export_snapshot("obra_test", snap_id)
    assert json_str is not None
    data = json.loads(json_str)
    assert "manifest" in data
    assert "data" in data


def test_work_not_found_returns_error(engine):
    """Snapshot de una obra inexistente retorna error."""
    result = engine.create_snapshot("nonexistent_work", message="fail")
    assert result["status"] == "error"
    assert result["error"] == "work_not_found"


# -- REST integration tests --------------------------------------------------

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.story_routes import router as story_router


@pytest.fixture
def rest_client(monkeypatch, tmp_path):
    story_dir = str(tmp_path / "story")
    monkeypatch.setenv("AURA_STORY_DIR", story_dir)
    set_engine_store_path(story_dir)
    from backend.story_memory.story_storage import StoryStorage

    store = StoryStorage(store_dir=story_dir)
    store.create_work(
        work_id="rest_work", title="REST Test", universe="test", description="d", author="tester"
    )
    from backend.story_memory.canon_tracker import CanonTracker

    ct = CanonTracker()
    ct.add_canon_event(work_id="rest_work", description="Evento canónico REST", source="user")
    app = FastAPI()
    app.include_router(story_router)
    return TestClient(app)


def test_rest_create_snapshot(rest_client):
    r = rest_client.post(
        "/api/story/rest_work/snapshots", json={"message": "REST snap", "author": "test"}
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "created"
    assert body["snapshot"]["canon_hash"]


def test_rest_list_snapshots(rest_client):
    rest_client.post("/api/story/rest_work/snapshots", json={"message": "s1"})
    rest_client.post("/api/story/rest_work/snapshots", json={"message": "s2"})
    r = rest_client.get("/api/story/rest_work/snapshots")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert len(body["snapshots"]) == 2


def test_rest_list_branches(rest_client):
    r = rest_client.get("/api/story/rest_work/branches")
    assert r.status_code == 200
    body = r.json()
    assert "main" in body["branches"]
