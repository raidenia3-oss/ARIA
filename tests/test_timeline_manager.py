"""Tests Bloque 44 - Local Narrative Timeline & Chronology Mapper.

Valida:
- Gestión de eventos cronológicos (CRUD, filtros, tipos).
- Enlaces temporales y relaciones de causa-efecto.
- Hilos narrativos / subtramas.
- Jan Chronology Validator (detección de paradojas, contradicciones).
- Endpoints REST para timeline, events, links, threads, validación.
- Persistencia on-disk y sincronización con canon/chapters.
"""

from __future__ import annotations

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.story_memory.canon_tracker import CanonTracker
from backend.story_memory.chapter_planner import ChapterPlanner
from backend.story_memory.character_bible import CharacterBible
from backend.story_memory.story_storage import StoryStorage
from backend.story_memory.timeline_manager import (
    NarrativeThread,
    NarrativeTimeline,
    TemporalRelation,
    TimelineEvent,
    TimelineEventType,
    TimelineLink,
    TimelineManager,
    get_timeline_manager,
    reset_timeline_manager,
)


@pytest.fixture
def temp_story_dir(tmp_path, monkeypatch):
    """Crea directorio temporal para story data."""
    story_dir = str(tmp_path / "story_memory")
    os.makedirs(story_dir, exist_ok=True)
    monkeypatch.setenv("AURA_STORY_DIR", story_dir)
    return story_dir


@pytest.fixture
def work_with_data(temp_story_dir):
    """Crea una obra con canon, continuity y chapters para testing."""
    storage = StoryStorage(store_dir=temp_story_dir)
    storage.create_work(
        work_id="test_timeline",
        title="Test Timeline",
        universe="Test",
        description="Test",
        author="Test",
    )

    ct = CanonTracker()
    ct.add_canon_event(
        work_id="test_timeline",
        description="El héroe nace en la aldea",
        timestamp=1000.0,
        scene_ref="ch1_sc1",
        source="user",
    )
    ct.add_canon_event(
        work_id="test_timeline",
        description="El héroe encuentra la espada",
        timestamp=2000.0,
        scene_ref="ch2_sc1",
        source="user",
    )
    ct.add_continuity_event(
        work_id="test_timeline",
        description="El héroe recuerda su infancia",
        timestamp=1500.0,
        scene_ref="ch1_sc2",
        source="user",
    )

    cb = CharacterBible()
    cb.create(work_id="test_timeline", char_id="hero", name="Aldric")
    cb.create(work_id="test_timeline", char_id="mentor", name="Merlin")

    cp = ChapterPlanner()
    cp.create_chapter(
        work_id="test_timeline",
        title="El Despertar",
        order=1,
        beat_summary="El héroe descubre su destino",
    )
    cp.create_chapter(
        work_id="test_timeline",
        title="La Prueba",
        order=2,
        beat_summary="El héroe enfrenta su primera prueba",
    )

    return temp_story_dir


@pytest.fixture
def timeline_manager(temp_story_dir):
    """Fixture que provee un TimelineManager limpio."""
    reset_timeline_manager()
    tm = get_timeline_manager(store_dir=temp_story_dir)
    yield tm
    reset_timeline_manager()


# -- NarrativeTimeline core tests ---------------------------------------------


def test_timeline_add_remove_events():
    timeline = NarrativeTimeline(work_id="test")
    event = TimelineEvent(
        event_id="evt_1",
        work_id="test",
        title="Evento 1",
        description="Descripción",
        event_type=TimelineEventType.CANON,
        timestamp=1000.0,
    )
    timeline.add_event(event)

    assert "evt_1" in timeline.events
    assert timeline.remove_event("evt_1") is True
    assert "evt_1" not in timeline.events
    assert timeline.remove_event("evt_1") is False


def test_timeline_links():
    timeline = NarrativeTimeline(work_id="test")
    e1 = TimelineEvent("evt_1", "test", "E1", "D1", TimelineEventType.CANON, timestamp=1000)
    e2 = TimelineEvent("evt_2", "test", "E2", "D2", TimelineEventType.CANON, timestamp=2000)
    timeline.add_event(e1)
    timeline.add_event(e2)

    link = TimelineLink("evt_1", "evt_2", TemporalRelation.BEFORE, strength=0.9)
    timeline.add_link(link)

    assert len(timeline.links) == 1
    assert timeline.remove_link("evt_1", "evt_2", TemporalRelation.BEFORE) is True
    assert len(timeline.links) == 0


def test_timeline_threads():
    timeline = NarrativeTimeline(work_id="test")
    thread = NarrativeThread("main", "test", "Principal", is_main=True)
    timeline.add_thread(thread)

    assert timeline.main_thread_id == "main"
    timeline.add_event(
        TimelineEvent("evt_1", "test", "E1", "D1", TimelineEventType.CANON, timestamp=1000)
    )
    timeline.threads["main"].event_ids.append("evt_1")

    events = timeline.get_thread_events("main")
    assert len(events) == 1

    assert timeline.remove_thread("main") is True
    assert timeline.main_thread_id is None


def test_timeline_serialization():
    timeline = NarrativeTimeline(work_id="test")
    e = TimelineEvent("evt_1", "test", "E1", "D1", TimelineEventType.CANON, timestamp=1000)
    timeline.add_event(e)
    timeline.add_link(TimelineLink("evt_1", "evt_1", TemporalRelation.SIMULTANEOUS))
    timeline.add_thread(NarrativeThread("main", "test", "Main", is_main=True))

    data = timeline.to_dict()
    restored = NarrativeTimeline.from_dict(data)

    assert restored.work_id == "test"
    assert "evt_1" in restored.events
    assert len(restored.links) == 1
    assert "main" in restored.threads


# -- TimelineManager tests ----------------------------------------------------


def test_timeline_manager_creates_and_saves(work_with_data):
    tm = TimelineManager(store_dir=work_with_data)
    timeline = tm.get_or_create_timeline("test_timeline")

    assert len(timeline.events) > 0  # synced from canon/chapters
    assert timeline.main_thread_id == "main"

    tm2 = TimelineManager(store_dir=work_with_data)
    timeline2 = tm2.get_or_create_timeline("test_timeline")
    assert len(timeline2.events) == len(timeline.events)


def test_timeline_manager_add_event(work_with_data):
    tm = TimelineManager(store_dir=work_with_data)
    result = tm.add_event(
        work_id="test_timeline",
        title="Nuevo Evento",
        description="Descripción del evento",
        event_type=TimelineEventType.FLASHBACK,
        timestamp=500.0,
        characters=["hero"],
        tags=["importante"],
    )

    assert result["status"] == "created"
    assert result["event"]["event_type"] == "flashback"
    assert result["event"]["timestamp"] == 500.0
    assert "hero" in result["event"]["characters"]


def test_timeline_manager_update_event(work_with_data):
    tm = TimelineManager(store_dir=work_with_data)
    result = tm.add_event(
        "test_timeline", "Título", "Desc", TimelineEventType.CANON, timestamp=1000
    )
    event_id = result["event"]["event_id"]

    result2 = tm.update_event(
        "test_timeline",
        event_id,
        title="Nuevo Título",
        timestamp=1500.0,
        tags=["actualizado"],
    )

    assert result2["status"] == "updated"
    assert result2["event"]["title"] == "Nuevo Título"
    assert result2["event"]["timestamp"] == 1500.0
    assert "actualizado" in result2["event"]["tags"]


def test_timeline_manager_delete_event(work_with_data):
    tm = TimelineManager(store_dir=work_with_data)
    result = tm.add_event("test_timeline", "Borrar", "Desc", TimelineEventType.CANON)
    event_id = result["event"]["event_id"]

    assert tm.delete_event("test_timeline", event_id)["status"] == "deleted"
    assert tm.delete_event("test_timeline", event_id)["status"] == "error"


def test_timeline_manager_list_events(work_with_data):
    tm = TimelineManager(store_dir=work_with_data)
    tm.add_event(
        "test_timeline",
        "Evento A",
        "Desc",
        TimelineEventType.CANON,
        timestamp=1000,
        characters=["hero"],
    )
    tm.add_event(
        "test_timeline",
        "Evento B",
        "Desc",
        TimelineEventType.FLASHBACK,
        timestamp=500,
        characters=["mentor"],
    )

    # Filter by type
    result = tm.list_events("test_timeline", event_type=TimelineEventType.FLASHBACK)
    assert len(result["events"]) >= 1
    assert all(e["event_type"] == "flashback" for e in result["events"])

    # Filter by character
    result = tm.list_events("test_timeline", character_id="hero")
    assert all("hero" in e["characters"] for e in result["events"])

    # Filter by time range
    result = tm.list_events("test_timeline", start_time=800, end_time=1200)
    assert all(800 <= e["timestamp"] <= 1200 for e in result["events"])


def test_timeline_manager_chronology(work_with_data):
    tm = TimelineManager(store_dir=work_with_data)
    result = tm.get_chronology("test_timeline", max_events=10)

    assert result["status"] == "ok"
    assert len(result["events"]) > 0
    # Events should be sorted by timestamp
    timestamps = [e["timestamp"] for e in result["events"]]
    assert timestamps == sorted(timestamps)


def test_timeline_manager_links(work_with_data):
    tm = TimelineManager(store_dir=work_with_data)
    e1 = tm.add_event("test_timeline", "E1", "D1", TimelineEventType.CANON, timestamp=1000)
    e2 = tm.add_event("test_timeline", "E2", "D2", TimelineEventType.CANON, timestamp=2000)

    id1 = e1["event"]["event_id"]
    id2 = e2["event"]["event_id"]

    result = tm.add_link("test_timeline", id1, id2, TemporalRelation.CAUSES, strength=0.8)
    assert result["status"] == "created"
    assert result["link"]["relation"] == "causes"

    links = tm.get_links("test_timeline")
    assert len(links["links"]) == 1

    assert tm.remove_link("test_timeline", id1, id2, TemporalRelation.CAUSES)["status"] == "removed"


def test_timeline_manager_threads(work_with_data):
    tm = TimelineManager(store_dir=work_with_data)
    result = tm.create_thread(
        "test_timeline", "romance", "Subtrama Romántica", color="#E91E63", is_main=False
    )

    assert result["status"] == "created"
    assert result["thread"]["name"] == "Subtrama Romántica"
    assert result["thread"]["color"] == "#E91E63"

    threads = tm.list_threads("test_timeline")
    assert len(threads["threads"]) >= 2  # main + romance

    tm.add_event("test_timeline", "Cita", "Cita romántica", TimelineEventType.SCENE, timestamp=1500)
    eid = tm.get_event(
        "test_timeline", list(tm.get_or_create_timeline("test_timeline").events.keys())[-1]
    )["event"]["event_id"]
    tm.add_event_to_thread("test_timeline", "romance", eid)

    thread = tm.get_thread("test_timeline", "romance")
    assert len(thread["events"]) == 1


# -- Chronology Validation tests ----------------------------------------------


def test_validate_chronology_flashback(work_with_data):
    tm = TimelineManager(store_dir=work_with_data)
    # Add a canon event at timestamp 2000
    tm.add_event(
        "test_timeline",
        "Evento Presente",
        "En el presente",
        TimelineEventType.CANON,
        timestamp=2000,
    )

    # Try to add flashback at timestamp 2500 (should be before 2000)
    result = tm.validate_chronology(
        "test_timeline",
        {
            "event_id": "new_flashback",
            "title": "Flashback Futuro",
            "description": "Flashback en el futuro",
            "event_type": "flashback",
            "timestamp": 2500.0,
        },
    )

    assert result["status"] == "ok"
    assert result["valid"] is False
    assert any(w["type"] == "flashback_timing" for w in result["warnings"])


def test_validate_chronology_flashforward(work_with_data):
    tm = TimelineManager(store_dir=work_with_data)
    tm.add_event(
        "test_timeline", "Evento Pasado", "En el pasado", TimelineEventType.CANON, timestamp=1000
    )

    result = tm.validate_chronology(
        "test_timeline",
        {
            "event_id": "new_flashforward",
            "title": "Flashforward Pasado",
            "description": "Flashforward en el pasado",
            "event_type": "flashforward",
            "timestamp": 500.0,
        },
    )

    assert result["valid"] is False
    assert any(w["type"] == "flashforward_timing" for w in result["warnings"])


def test_validate_chronology_contradiction(work_with_data):
    tm = TimelineManager(store_dir=work_with_data)
    tm.add_event(
        "test_timeline", "Muerte", "El héroe murió", TimelineEventType.CANON, timestamp=1000
    )

    result = tm.validate_chronology(
        "test_timeline",
        {
            "event_id": "new_event",
            "title": "Supervivencia",
            "description": "El héroe sobrevivió a todo",
            "event_type": "canon",
            "timestamp": 2000,
        },
    )

    assert result["valid"] is False
    assert any(c["type"] == "temporal_contradiction" for c in result["conflicts"])


def test_validate_chronology_causality(work_with_data):
    tm = TimelineManager(store_dir=work_with_data)
    tm.add_event(
        "test_timeline", "Causa Raíz", "Esto causó todo", TimelineEventType.CANON, timestamp=1000
    )

    result = tm.validate_chronology(
        "test_timeline",
        {
            "event_id": "new_event",
            "title": "Efecto",
            "description": "Esto fue causado por la causa raíz",
            "event_type": "canon",
            "timestamp": 2000,
        },
    )

    # This might trigger causality warning
    assert result["status"] == "ok"


def test_check_event_sequence(work_with_data):
    tm = TimelineManager(store_dir=work_with_data)
    e1 = tm.add_event("test_timeline", "Primero", "D1", TimelineEventType.CANON, timestamp=2000)
    e2 = tm.add_event("test_timeline", "Segundo", "D2", TimelineEventType.CANON, timestamp=1000)

    id1 = e1["event"]["event_id"]
    id2 = e2["event"]["event_id"]

    result = tm.check_event_sequence("test_timeline", [id1, id2])

    assert result["status"] == "ok"
    assert result["valid"] is False
    assert any(i["type"] == "sequence_violation" for i in result["issues"])


def test_check_event_sequence_valid(work_with_data):
    tm = TimelineManager(store_dir=work_with_data)
    e1 = tm.add_event("test_timeline", "Primero", "D1", TimelineEventType.CANON, timestamp=1000)
    e2 = tm.add_event("test_timeline", "Segundo", "D2", TimelineEventType.CANON, timestamp=2000)

    id1 = e1["event"]["event_id"]
    id2 = e2["event"]["event_id"]

    result = tm.check_event_sequence("test_timeline", [id1, id2])

    assert result["valid"] is True
    assert len(result["issues"]) == 0


def test_timeline_stats(work_with_data):
    tm = TimelineManager(store_dir=work_with_data)
    stats = tm.get_timeline_stats("test_timeline")

    assert stats["status"] == "ok"
    assert stats["total_events"] > 0
    assert "by_type" in stats
    assert "time_span" in stats


def test_export_timeline(work_with_data):
    tm = TimelineManager(store_dir=work_with_data)
    export = tm.export_timeline("test_timeline")

    assert export["status"] == "ok"
    assert len(export["nodes"]) > 0
    assert len(export["threads"]) >= 1
    assert "stats" in export


# -- REST API tests -----------------------------------------------------------


def _rest_setup(temp_story_dir, monkeypatch):
    from backend.story_memory.canon_tracker import CanonTracker
    from backend.story_memory.chapter_planner import ChapterPlanner
    from backend.story_memory.character_bible import CharacterBible
    from backend.story_memory.story_storage import StoryStorage
    from backend.story_routes import router

    monkeypatch.setenv("AURA_STORY_DIR", temp_story_dir)

    storage = StoryStorage(store_dir=temp_story_dir)
    storage.create_work("rest_timeline", "REST Timeline", "Test", "Test", "Test")

    cb = CharacterBible()
    cb.create("rest_timeline", "hero", "Aldric")

    ct = CanonTracker()
    ct.add_canon_event("rest_timeline", "Evento canon", timestamp=1000)

    cp = ChapterPlanner()
    cp.create_chapter("rest_timeline", "Cap 1", 1, "Beat 1")

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_rest_get_timeline(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    r = client.get("/api/story/rest_timeline/timeline")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "nodes" in body
    assert "edges" in body
    assert "threads" in body


def test_rest_get_timeline_stats(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    r = client.get("/api/story/rest_timeline/timeline/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "total_events" in body


def test_rest_get_chronology(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    r = client.get("/api/story/rest_timeline/timeline/chronology?max_events=10")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "events" in body


def test_rest_create_timeline_event(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    r = client.post(
        "/api/story/rest_timeline/timeline/events",
        json={
            "title": "Nuevo Evento",
            "description": "Descripción",
            "event_type": "flashback",
            "timestamp": 500.0,
            "characters": ["hero"],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "created"
    assert body["event"]["event_type"] == "flashback"
    assert "event_id" in body["event"]


def test_rest_create_timeline_event_invalid_type(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    r = client.post(
        "/api/story/rest_timeline/timeline/events",
        json={
            "title": "Evento",
            "description": "Desc",
            "event_type": "invalid_type",
        },
    )
    assert r.status_code == 422


def test_rest_list_timeline_events(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    client.post(
        "/api/story/rest_timeline/timeline/events",
        json={
            "title": "Evento A",
            "description": "D",
            "event_type": "canon",
            "timestamp": 1000,
            "characters": ["hero"],
        },
    )

    r = client.get("/api/story/rest_timeline/timeline/events?character_id=hero")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert all("hero" in e["characters"] for e in body["events"])


def test_rest_get_timeline_event(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    create = client.post(
        "/api/story/rest_timeline/timeline/events",
        json={"title": "Evento", "description": "D", "event_type": "canon"},
    )
    event_id = create.json()["event"]["event_id"]

    r = client.get(f"/api/story/rest_timeline/timeline/events/{event_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["event"]["event_id"] == event_id


def test_rest_update_timeline_event(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    create = client.post(
        "/api/story/rest_timeline/timeline/events",
        json={"title": "Original", "description": "D", "event_type": "canon"},
    )
    event_id = create.json()["event"]["event_id"]

    r = client.put(
        f"/api/story/rest_timeline/timeline/events/{event_id}",
        json={
            "title": "Actualizado",
            "event_type": "flashback",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "updated"
    assert body["event"]["title"] == "Actualizado"
    assert body["event"]["event_type"] == "flashback"


def test_rest_delete_timeline_event(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    create = client.post(
        "/api/story/rest_timeline/timeline/events",
        json={"title": "Borrar", "description": "D", "event_type": "canon"},
    )
    event_id = create.json()["event"]["event_id"]

    r = client.delete(f"/api/story/rest_timeline/timeline/events/{event_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "deleted"


def test_rest_create_timeline_link(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    e1 = client.post(
        "/api/story/rest_timeline/timeline/events",
        json={"title": "E1", "description": "D", "event_type": "canon", "timestamp": 1000},
    )
    e2 = client.post(
        "/api/story/rest_timeline/timeline/events",
        json={"title": "E2", "description": "D", "event_type": "canon", "timestamp": 2000},
    )

    id1 = e1.json()["event"]["event_id"]
    id2 = e2.json()["event"]["event_id"]

    r = client.post(
        "/api/story/rest_timeline/timeline/links",
        json={
            "source_id": id1,
            "target_id": id2,
            "relation": "causes",
            "strength": 0.9,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "created"
    assert body["link"]["relation"] == "causes"


def test_rest_delete_timeline_link(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    e1 = client.post(
        "/api/story/rest_timeline/timeline/events",
        json={"title": "E1", "description": "D", "event_type": "canon", "timestamp": 1000},
    )
    e2 = client.post(
        "/api/story/rest_timeline/timeline/events",
        json={"title": "E2", "description": "D", "event_type": "canon", "timestamp": 2000},
    )

    id1 = e1.json()["event"]["event_id"]
    id2 = e2.json()["event"]["event_id"]

    client.post(
        "/api/story/rest_timeline/timeline/links",
        json={"source_id": id1, "target_id": id2, "relation": "before"},
    )

    r = client.delete(
        f"/api/story/rest_timeline/timeline/links?source_id={id1}&target_id={id2}&relation=before"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "removed"


def test_rest_list_timeline_links(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    r = client.get("/api/story/rest_timeline/timeline/links")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"


def test_rest_create_timeline_thread(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    r = client.post(
        "/api/story/rest_timeline/timeline/threads",
        json={
            "thread_id": "romance",
            "name": "Romance",
            "description": "Subtrama romántica",
            "color": "#E91E63",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "created"
    assert body["thread"]["name"] == "Romance"


def test_rest_list_timeline_threads(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    client.post(
        "/api/story/rest_timeline/timeline/threads",
        json={"thread_id": "sub1", "name": "Sub 1", "color": "#FF0000"},
    )

    r = client.get("/api/story/rest_timeline/timeline/threads")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert len(body["threads"]) >= 2


def test_rest_get_timeline_thread(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    client.post(
        "/api/story/rest_timeline/timeline/threads",
        json={"thread_id": "test_thread", "name": "Test Thread"},
    )

    r = client.get("/api/story/rest_timeline/timeline/threads/test_thread")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["thread"]["thread_id"] == "test_thread"


def test_rest_update_timeline_thread(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    client.post(
        "/api/story/rest_timeline/timeline/threads",
        json={"thread_id": "update_me", "name": "Original"},
    )

    r = client.put(
        "/api/story/rest_timeline/timeline/threads/update_me",
        json={
            "name": "Actualizado",
            "color": "#00FF00",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "updated"
    assert body["thread"]["name"] == "Actualizado"


def test_rest_delete_timeline_thread(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    client.post(
        "/api/story/rest_timeline/timeline/threads",
        json={"thread_id": "delete_me", "name": "Delete Me"},
    )

    r = client.delete("/api/story/rest_timeline/timeline/threads/delete_me")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "deleted"


def test_rest_add_event_to_thread(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    client.post(
        "/api/story/rest_timeline/timeline/threads",
        json={"thread_id": "thread1", "name": "Thread 1"},
    )
    e = client.post(
        "/api/story/rest_timeline/timeline/events",
        json={"title": "Event", "description": "D", "event_type": "canon"},
    )
    event_id = e.json()["event"]["event_id"]

    r = client.post(f"/api/story/rest_timeline/timeline/threads/thread1/events/{event_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "added"


def test_rest_validate_chronology(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    # Add canon event
    client.post(
        "/api/story/rest_timeline/timeline/events",
        json={
            "title": "Muerte",
            "description": "El héroe murió",
            "event_type": "canon",
            "timestamp": 1000,
        },
    )

    r = client.post(
        "/api/story/rest_timeline/timeline/validate",
        json={
            "event_id": "new",
            "title": "Vida",
            "description": "El héroe sobrevivió",
            "event_type": "canon",
            "timestamp": 2000,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["valid"] is False
    assert len(body["conflicts"]) > 0


def test_rest_check_sequence(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    e1 = client.post(
        "/api/story/rest_timeline/timeline/events",
        json={"title": "E1", "description": "D", "event_type": "canon", "timestamp": 2000},
    )
    e2 = client.post(
        "/api/story/rest_timeline/timeline/events",
        json={"title": "E2", "description": "D", "event_type": "canon", "timestamp": 1000},
    )

    id1 = e1.json()["event"]["event_id"]
    id2 = e2.json()["event"]["event_id"]

    r = client.post(
        "/api/story/rest_timeline/timeline/check-sequence", json={"event_ids": [id1, id2]}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["valid"] is False
    assert len(body["issues"]) > 0


def test_rest_check_sequence_valid(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    e1 = client.post(
        "/api/story/rest_timeline/timeline/events",
        json={"title": "E1", "description": "D", "event_type": "canon", "timestamp": 1000},
    )
    e2 = client.post(
        "/api/story/rest_timeline/timeline/events",
        json={"title": "E2", "description": "D", "event_type": "canon", "timestamp": 2000},
    )

    id1 = e1.json()["event"]["event_id"]
    id2 = e2.json()["event"]["event_id"]

    r = client.post(
        "/api/story/rest_timeline/timeline/check-sequence", json={"event_ids": [id1, id2]}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is True
    assert len(body["issues"]) == 0
