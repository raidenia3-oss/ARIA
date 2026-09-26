"""Tests Bloque 45 - Local Interactive Codex & World Gazetteer Engine.

Valida:
- CRUD de entradas del codex (ubicaciones, artefactos, mitos, criaturas).
- Referencias cruzadas lore <-> personajes/canon/capitulos.
- Busqueda por radio de influencia y control territorial.
- Jan Spatial Consistency Checker.
- Endpoints REST /api/story/{work_id}/codex.
- Persistencia on-disk.
"""

from __future__ import annotations

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.story_memory.canon_tracker import CanonTracker
from backend.story_memory.character_bible import CharacterBible
from backend.story_memory.gazetteer import (
    CodexEntryType,
    GazetteerEngine,
    get_gazetteer,
    reset_gazetteer,
)
from backend.story_memory.story_storage import StoryStorage


@pytest.fixture
def temp_story_dir(tmp_path, monkeypatch):
    story_dir = str(tmp_path / "story_memory")
    os.makedirs(story_dir, exist_ok=True)
    monkeypatch.setenv("AURA_STORY_DIR", story_dir)
    return story_dir


@pytest.fixture
def gaz(temp_story_dir):
    reset_gazetteer()
    g = get_gazetteer(store_dir=temp_story_dir)
    yield g
    reset_gazetteer()


@pytest.fixture
def work_with_lore(temp_story_dir):
    storage = StoryStorage(store_dir=temp_story_dir)
    storage.create_work(
        work_id="codex_w", title="Obra Codex", universe="U", description="d", author="t"
    )
    cb = CharacterBible()
    cb.create(work_id="codex_w", char_id="hero", name="Aldric")
    ct = CanonTracker()
    ct.add_canon_event(work_id="codex_w", description="Fundacion de Bruma")
    return temp_story_dir


def test_create_and_get_entry(gaz):
    r = gaz.create_entry(
        "w1",
        "Bruma",
        CodexEntryType.LOCATION,
        description="Aldea entre montanas",
        x=10.0,
        y=20.0,
        region="Norte",
        climate="temperate",
        traits=["montanas", "niebla"],
    )
    assert r["status"] == "created"
    eid = r["entry"]["entry_id"]
    g = gaz.get_entry("w1", eid)
    assert g["status"] == "ok"
    assert g["entry"]["title"] == "Bruma"
    assert g["entry"]["x"] == 10.0
    assert "niebla" in g["entry"]["traits"]


def test_create_requires_title(gaz):
    assert gaz.create_entry("w1", "  ")["status"] == "error"


def test_create_invalid_type(gaz):
    assert gaz.create_entry("w1", "X", entry_type="nave")["status"] == "error"


def test_list_filter_by_type_and_region(gaz):
    gaz.create_entry("w1", "Bruma", "location", region="Norte")
    gaz.create_entry("w1", "Espada del Alba", "artifact", region="Norte")
    gaz.create_entry("w1", "Puerto Sur", "location", region="Sur")
    all_e = gaz.list_entries("w1")
    assert all_e["count"] == 3
    locs = gaz.list_entries("w1", entry_type="location")
    assert locs["count"] == 2
    norte = gaz.list_entries("w1", region="Norte")
    assert norte["count"] == 2


def test_update_and_delete(gaz):
    r = gaz.create_entry("w1", "Bruma", "location")
    eid = r["entry"]["entry_id"]
    u = gaz.update_entry("w1", eid, {"climate": "arid", "controlling_faction": "clan-rojo"})
    assert u["status"] == "updated"
    assert u["entry"]["climate"] == "arid"
    d = gaz.delete_entry("w1", eid)
    assert d["status"] == "deleted"
    assert gaz.get_entry("w1", eid)["status"] == "error"


def test_cross_references_character_exists(gaz, work_with_lore):
    reset_gazetteer()
    g = get_gazetteer(store_dir=work_with_lore)
    r = g.create_entry("codex_w", "Bruma", "location", x=0, y=0)
    eid = r["entry"]["entry_id"]
    a = g.create_entry("codex_w", "Espada del Alba", "artifact")
    aid = a["entry"]["entry_id"]
    assert g.link_artifact("codex_w", eid, aid)["status"] == "linked"
    assert g.link_character("codex_w", eid, "hero")["status"] == "linked"
    assert g.link_character("codex_w", eid, "ghost")["status"] == "linked"
    refs = g.get_cross_references("codex_w", eid)
    assert refs["status"] == "ok"
    assert aid in refs["outbound"]["artifacts"]
    assert refs["character_exists"]["hero"] is True
    assert refs["character_exists"]["ghost"] is False
    reset_gazetteer()


def test_search_by_radius_and_control(gaz):
    gaz.create_entry("w1", "Capital", "location", x=0, y=0, influence_radius=10.0)
    gaz.create_entry("w1", "Aldea", "location", x=5, y=0, influence_radius=2.0)
    gaz.create_entry("w1", "Lejos", "location", x=100, y=100)
    s = gaz.search_by_radius("w1", 0, 0, 6.0)
    assert s["count"] == 2
    assert s["results"][0]["entry"]["title"] == "Capital"
    c = gaz.find_controlling_entry("w1", 5, 0)
    assert c["entry"]["title"] == "Aldea"
    c2 = gaz.find_controlling_entry("w1", 100, 100)
    assert c2["entry"] is None


def test_spatial_checker_consistent(gaz):
    r = gaz.create_entry(
        "w1",
        "Bruma",
        "location",
        climate="temperate",
        controlling_faction="clan",
        traits=["niebla"],
    )
    eid = r["entry"]["entry_id"]
    ok = gaz.check_spatial_consistency(
        "w1",
        {
            "entry_id": eid,
            "expected_climate": "temperate",
            "expected_faction": "clan",
            "expected_traits": ["niebla"],
            "scene_description": "La niebla cubre Bruma al amanecer",
        },
    )
    assert ok["status"] == "ok"
    assert ok["consistent"] is True
    assert "niebla" in ok["trait_hits"]


def test_spatial_checker_mismatch(gaz):
    r = gaz.create_entry(
        "w1", "Desierto", "location", climate="arid", controlling_faction="nomadas"
    )
    eid = r["entry"]["entry_id"]
    bad = gaz.check_spatial_consistency(
        "w1",
        {
            "entry_id": eid,
            "expected_climate": "polar",
            "expected_faction": "imperio",
            "expected_traits": ["nieve"],
        },
    )
    assert bad["consistent"] is False
    assert len(bad["issues"]) == 3


def test_persistence(temp_story_dir):
    reset_gazetteer()
    g = get_gazetteer(store_dir=temp_story_dir)
    r = g.create_entry("pw", "Bruma Eterna", "location", x=1, y=2)
    eid = r["entry"]["entry_id"]
    reset_gazetteer()
    g2 = get_gazetteer(store_dir=temp_story_dir)
    assert g2.get_entry("pw", eid)["status"] == "ok"
    reset_gazetteer()


def test_codex_context_block(gaz):
    gaz.create_entry(
        "w1", "Bruma", "location", region="Norte", climate="temperate", description="Aldea"
    )
    ctx = gaz.build_codex_context("w1")
    assert ctx.startswith("[CODEX")
    assert "Bruma" in ctx


def _rest_setup(monkeypatch, tmp_path):
    from backend.story_memory.story_storage import StoryStorage
    from backend.story_routes import router

    story_dir = str(tmp_path / "story")
    monkeypatch.setenv("AURA_STORY_DIR", story_dir)
    import backend.story_routes as sr

    sr.storage = StoryStorage(store_dir=story_dir)
    from backend.story_memory.gazetteer import reset_gazetteer

    reset_gazetteer()
    store = sr.storage
    store.create_work(work_id="rest_codex", title="REST", universe="u", description="d", author="t")
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    yield client
    reset_gazetteer()


def test_rest_create_and_get(monkeypatch, tmp_path):
    for client in _rest_setup(monkeypatch, tmp_path):
        r = client.post(
            "/api/story/rest_codex/codex",
            json={
                "title": "Bruma",
                "entry_type": "location",
                "description": "Aldea",
                "x": 1,
                "y": 2,
                "region": "Norte",
            },
        )
        assert r.status_code == 201
        eid = r.json()["entry"]["entry_id"]
        g = client.get(f"/api/story/rest_codex/codex/{eid}")
        assert g.status_code == 200
        assert g.json()["entry"]["title"] == "Bruma"


def test_rest_list_and_stats(monkeypatch, tmp_path):
    for client in _rest_setup(monkeypatch, tmp_path):
        client.post("/api/story/rest_codex/codex", json={"title": "A", "entry_type": "location"})
        client.post("/api/story/rest_codex/codex", json={"title": "B", "entry_type": "artifact"})
        l = client.get("/api/story/rest_codex/codex")
        assert l.status_code == 200
        assert l.json()["count"] == 2
        s = client.get("/api/story/rest_codex/codex/stats")
        assert s.json()["total"] == 2


def test_rest_radius_search(monkeypatch, tmp_path):
    for client in _rest_setup(monkeypatch, tmp_path):
        client.post("/api/story/rest_codex/codex", json={"title": "C", "x": 0, "y": 0})
        client.post("/api/story/rest_codex/codex", json={"title": "L", "x": 100, "y": 100})
        r = client.get(
            "/api/story/rest_codex/codex/search/radius", params={"x": 0, "y": 0, "radius": 5}
        )
        assert r.status_code == 200
        assert r.json()["count"] == 1


def test_rest_check_spatial(monkeypatch, tmp_path):
    for client in _rest_setup(monkeypatch, tmp_path):
        r = client.post(
            "/api/story/rest_codex/codex",
            json={"title": "Bruma", "entry_type": "location", "climate": "temperate"},
        )
        eid = r.json()["entry"]["entry_id"]
        c = client.post(
            "/api/story/rest_codex/codex/check-spatial",
            json={"entry_id": eid, "expected_climate": "arid"},
        )
        assert c.status_code == 200
        assert c.json()["consistent"] is False


def test_rest_work_not_found(monkeypatch, tmp_path):
    for client in _rest_setup(monkeypatch, tmp_path):
        r = client.get("/api/story/ghost/codex")
        assert r.status_code == 404
