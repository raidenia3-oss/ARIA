"""Tests Bloque 47 - Local Asset & Media Gallery Manager.

Valida:
- Ingest/Upload de assets multimedia (imágenes).
- Generación de thumbnails.
- Listado con filtros (kind, char_id, codex_entry_id).
- Asset-to-Lore Mapper (vinculación personaje/codex).
- Descarga de original y thumbnail.
- Persistencia en disco y metadatos JSON.
- Endpoints REST /api/story/{work_id}/media.
"""

from __future__ import annotations

import io
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from backend.media.manager import (
    AssetKind,
    MediaManager,
    get_media_manager,
    reset_media_manager,
)
from backend.story_memory.story_storage import StoryStorage


@pytest.fixture
def temp_story_dir(tmp_path, monkeypatch):
    story_dir = str(tmp_path / "story_memory")
    os.makedirs(story_dir, exist_ok=True)
    monkeypatch.setenv("AURA_STORY_DIR", story_dir)
    monkeypatch.setenv("AURA_MEDIA_MAX_BYTES", str(5 * 1024 * 1024))
    return story_dir


@pytest.fixture
def mgr(temp_story_dir):
    reset_media_manager()
    m = get_media_manager(store_dir=temp_story_dir)
    yield m
    reset_media_manager()


@pytest.fixture
def work_with_char(temp_story_dir):
    storage = StoryStorage(store_dir=temp_story_dir)
    storage.create_work(
        work_id="media_w", title="Obra Media", universe="U", description="d", author="t"
    )
    return temp_story_dir


def _make_png_bytes(size=(100, 100), color=(255, 0, 0)) -> bytes:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_ingest_png_creates_asset_and_thumb(mgr, temp_story_dir):
    data = _make_png_bytes()
    stream = io.BytesIO(data)
    res = mgr.ingest(
        "w1", stream, "test.png", "image/png", kind=AssetKind.PORTRAIT.value, title="Retrato"
    )
    assert res["status"] == "created"
    asset = res["asset"]
    assert asset["kind"] == "portrait"
    assert asset["width"] == 100
    assert asset["height"] == 100
    assert asset["thumb_name"].endswith("_thumb.webp")
    # Verificar archivos en disco
    wdir = mgr._work_dir("w1")
    assert (wdir / asset["stored_name"]).exists()
    assert (wdir / asset["thumb_name"]).exists()


def test_ingest_rejects_invalid_mime(mgr):
    stream = io.BytesIO(b"fake")
    res = mgr.ingest("w1", stream, "test.txt", "text/plain")
    assert res["status"] == "error"
    assert "mime_not_allowed" in res["error"]


def test_ingest_rejects_too_large(mgr):
    # 6MB > 5MB limit
    big = b"x" * (6 * 1024 * 1024)
    stream = io.BytesIO(big)
    res = mgr.ingest("w1", stream, "big.png", "image/png")
    assert res["status"] == "error"
    assert res["error"] == "file_too_large"


def test_get_and_list(mgr):
    data = _make_png_bytes()
    mgr.ingest("w1", io.BytesIO(data), "a.png", "image/png", kind="map", title="Mapa")
    mgr.ingest("w1", io.BytesIO(data), "b.png", "image/png", kind="concept_art", title="Concepto")
    # Get
    assets = mgr._load("w1")
    aid = list(assets.keys())[0]
    g = mgr.get("w1", aid)
    assert g["status"] == "ok"
    # List all
    lst = mgr.list("w1")
    assert lst["total"] == 2
    # Filter by kind
    maps = mgr.list("w1", kind="map")
    assert maps["total"] == 1
    assert maps["assets"][0]["kind"] == "map"


def test_update_metadata(mgr):
    data = _make_png_bytes()
    res = mgr.ingest("w1", io.BytesIO(data), "a.png", "image/png")
    aid = res["asset"]["asset_id"]
    upd = mgr.update("w1", aid, {"title": "Nuevo titulo", "tags": ["tag1", "tag2"]})
    assert upd["status"] == "updated"
    assert upd["asset"]["title"] == "Nuevo titulo"
    assert "tag1" in upd["asset"]["tags"]


def test_delete_removes_files(mgr):
    data = _make_png_bytes()
    res = mgr.ingest("w1", io.BytesIO(data), "a.png", "image/png")
    aid = res["asset"]["asset_id"]
    d = mgr.delete("w1", aid)
    assert d["status"] == "deleted"
    assert mgr.get("w1", aid)["status"] == "error"
    wdir = mgr._work_dir("w1")
    assert not list(wdir.glob("*"))


def test_link_character_and_codex(mgr, work_with_char):
    reset_media_manager()
    m = get_media_manager(store_dir=work_with_char)
    data = _make_png_bytes()
    res = m.ingest("media_w", io.BytesIO(data), "portrait.png", "image/png")
    aid = res["asset"]["asset_id"]
    # Link character
    lc = m.link_character("media_w", aid, "hero")
    assert lc["status"] == "updated"
    assert lc["asset"]["char_id"] == "hero"
    # Link codex
    lx = m.link_codex("media_w", aid, "loc_123")
    assert lx["status"] == "updated"
    assert lx["asset"]["codex_entry_id"] == "loc_123"
    # Query by character
    by_char = m.get_by_character("media_w", "hero")
    assert by_char["total"] == 1
    # Query by codex
    by_codex = m.get_by_codex("media_w", "loc_123")
    assert by_codex["total"] == 1
    reset_media_manager()


def test_stats(mgr):
    data = _make_png_bytes()
    mgr.ingest("w1", io.BytesIO(data), "a.png", "image/png", kind="map")
    mgr.ingest("w1", io.BytesIO(data), "b.png", "image/png", kind="map")
    mgr.ingest("w1", io.BytesIO(data), "c.png", "image/png", kind="portrait")
    st = mgr.stats("w1")
    assert st["total_assets"] == 3
    assert st["by_kind"]["map"] == 2
    assert st["by_kind"]["portrait"] == 1
    assert st["total_bytes"] > 0


def test_persistence(temp_story_dir):
    reset_media_manager()
    m = get_media_manager(store_dir=temp_story_dir)
    data = _make_png_bytes()
    res = m.ingest("pw", io.BytesIO(data), "persist.png", "image/png", kind="map")
    aid = res["asset"]["asset_id"]
    reset_media_manager()
    m2 = get_media_manager(store_dir=temp_story_dir)
    assert m2.get("pw", aid)["status"] == "ok"
    reset_media_manager()


def test_file_path_and_thumb(mgr):
    data = _make_png_bytes()
    res = mgr.ingest("w1", io.BytesIO(data), "thumbtest.png", "image/png")
    aid = res["asset"]["asset_id"]
    orig = mgr.file_path("w1", aid, thumb=False)
    thumb = mgr.file_path("w1", aid, thumb=True)
    assert orig is not None and orig.exists()
    assert thumb is not None and thumb.exists()
    assert thumb.suffix == ".webp"


# --- REST endpoints tests ---


def _rest_setup(monkeypatch, tmp_path):
    from backend.media import routes as mr
    from backend.media.routes import router

    story_dir = str(tmp_path / "story")
    os.makedirs(story_dir, exist_ok=True)
    monkeypatch.setenv("AURA_STORY_DIR", story_dir)
    monkeypatch.setenv("AURA_MEDIA_MAX_BYTES", str(5 * 1024 * 1024))
    reset_media_manager()
    storage = StoryStorage(store_dir=story_dir)
    storage.create_work(
        work_id="rest_media", title="REST Media", universe="u", description="d", author="t"
    )
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    yield client
    reset_media_manager()


def test_rest_upload_and_get(monkeypatch, tmp_path):
    for client in _rest_setup(monkeypatch, tmp_path):
        png = _make_png_bytes()
        r = client.post(
            "/api/story/rest_media/media",
            files={"file": ("test.png", png, "image/png")},
            data={"kind": "portrait", "title": "Hero"},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["status"] == "created"
        assert data["asset"]["kind"] == "portrait"
        aid = data["asset"]["asset_id"]
        g = client.get(f"/api/story/rest_media/media/{aid}")
        assert g.status_code == 200
        assert g.json()["asset"]["asset_id"] == aid


def test_rest_list_and_filter(monkeypatch, tmp_path):
    for client in _rest_setup(monkeypatch, tmp_path):
        png = _make_png_bytes()
        client.post(
            "/api/story/rest_media/media",
            files={"file": ("a.png", png, "image/png")},
            data={"kind": "map"},
        )
        client.post(
            "/api/story/rest_media/media",
            files={"file": ("b.png", png, "image/png")},
            data={"kind": "map"},
        )
        client.post(
            "/api/story/rest_media/media",
            files={"file": ("c.png", png, "image/png")},
            data={"kind": "concept_art"},
        )
        lst = client.get("/api/story/rest_media/media")
        assert lst.json()["total"] == 3
        maps = client.get("/api/story/rest_media/media", params={"kind": "map"})
        assert maps.json()["total"] == 2


def test_rest_stats(monkeypatch, tmp_path):
    for client in _rest_setup(monkeypatch, tmp_path):
        png = _make_png_bytes()
        client.post(
            "/api/story/rest_media/media",
            files={"file": ("a.png", png, "image/png")},
            data={"kind": "map"},
        )
        client.post(
            "/api/story/rest_media/media",
            files={"file": ("b.png", png, "image/png")},
            data={"kind": "map"},
        )
        s = client.get("/api/story/rest_media/media/stats")
        assert s.json()["total_assets"] == 2
        assert s.json()["by_kind"]["map"] == 2


def test_rest_file_and_thumb_download(monkeypatch, tmp_path):
    for client in _rest_setup(monkeypatch, tmp_path):
        png = _make_png_bytes()
        r = client.post(
            "/api/story/rest_media/media", files={"file": ("orig.png", png, "image/png")}
        )
        aid = r.json()["asset"]["asset_id"]
        # Original
        f = client.get(f"/api/story/rest_media/media/{aid}/file")
        assert f.status_code == 200
        assert f.headers["content-type"] == "image/png"
        # Thumb
        t = client.get(f"/api/story/rest_media/media/{aid}/thumb")
        assert t.status_code == 200
        assert t.headers["content-type"] == "image/webp"


def test_rest_update_and_link(monkeypatch, tmp_path):
    for client in _rest_setup(monkeypatch, tmp_path):
        png = _make_png_bytes()
        r = client.post("/api/story/rest_media/media", files={"file": ("a.png", png, "image/png")})
        aid = r.json()["asset"]["asset_id"]
        # Update
        u = client.put(
            f"/api/story/rest_media/media/{aid}", json={"title": "Updated", "tags": ["t1"]}
        )
        assert u.status_code == 200
        assert u.json()["asset"]["title"] == "Updated"
        # Link character
        lc = client.post(
            f"/api/story/rest_media/media/{aid}/link/character", data={"char_id": "hero"}
        )
        assert lc.status_code == 200
        assert lc.json()["asset"]["char_id"] == "hero"
        # Link codex
        lx = client.post(
            f"/api/story/rest_media/media/{aid}/link/codex", data={"codex_entry_id": "loc_1"}
        )
        assert lx.status_code == 200
        assert lx.json()["asset"]["codex_entry_id"] == "loc_1"


def test_rest_delete(monkeypatch, tmp_path):
    for client in _rest_setup(monkeypatch, tmp_path):
        png = _make_png_bytes()
        r = client.post("/api/story/rest_media/media", files={"file": ("a.png", png, "image/png")})
        aid = r.json()["asset"]["asset_id"]
        d = client.delete(f"/api/story/rest_media/media/{aid}")
        assert d.status_code == 200
        assert d.json()["status"] == "deleted"
        g = client.get(f"/api/story/rest_media/media/{aid}")
        assert g.status_code == 404


def test_rest_work_not_found(monkeypatch, tmp_path):
    for client in _rest_setup(monkeypatch, tmp_path):
        png = _make_png_bytes()
        r = client.post("/api/story/ghost/media", files={"file": ("a.png", png, "image/png")})
        assert r.status_code == 404
