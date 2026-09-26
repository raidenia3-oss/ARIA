"""Tests Bloque 43 - Local Character Relationship Graph & Faction Matrix.

Valida:
- Gestión de grafos de relaciones (nodos, aristas, tipos, pesos).
- Matriz de facciones y asignación de personajes.
- Detección de conflictos narrativos (Jan Conflict Checker).
- Endpoints REST para relaciones y facciones.
- Persistencia on-disk.
"""

from __future__ import annotations

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.story_memory.canon_tracker import CanonTracker
from backend.story_memory.character_bible import CharacterBible
from backend.story_memory.graph_manager import (
    Faction,
    FactionType,
    GraphManager,
    RelationshipEdge,
    RelationshipGraph,
    RelationshipType,
    get_graph_manager,
    reset_graph_manager,
)
from backend.story_memory.story_storage import StoryStorage


@pytest.fixture
def temp_story_dir(tmp_path, monkeypatch):
    """Crea directorio temporal para story data."""
    story_dir = str(tmp_path / "story_memory")
    os.makedirs(story_dir, exist_ok=True)
    monkeypatch.setenv("AURA_STORY_DIR", story_dir)
    return story_dir


@pytest.fixture
def work_with_characters(temp_story_dir):
    """Crea una obra con personajes para testing."""
    storage = StoryStorage(store_dir=temp_story_dir)
    storage.create_work(
        work_id="test_graph",
        title="Test Graph",
        universe="Test",
        description="Test",
        author="Test",
    )

    cb = CharacterBible()
    cb.create(
        work_id="test_graph",
        char_id="hero",
        name="Aldric",
        personality=["valiente"],
        relationships={"Merlin": "mentor", "Malakar": "enemigo", "Kael": "rival", "Elara": "novia"},
    )
    cb.create(
        work_id="test_graph",
        char_id="mentor",
        name="Merlin",
        personality=["sabio"],
        relationships={"Aldric": "alumno"},
    )
    cb.create(
        work_id="test_graph",
        char_id="villain",
        name="Malakar",
        personality=["cruel"],
        relationships={"Aldric": "enemigo"},
    )
    cb.create(
        work_id="test_graph",
        char_id="rival",
        name="Kael",
        personality=["ambicioso"],
        relationships={"Aldric": "rival"},
    )
    cb.create(
        work_id="test_graph",
        char_id="love",
        name="Elara",
        personality=["amable"],
        relationships={"Aldric": "novia"},
    )

    return temp_story_dir


@pytest.fixture
def graph_manager(temp_story_dir):
    """Fixture que provee un GraphManager limpio."""
    reset_graph_manager()
    gm = get_graph_manager(store_dir=temp_story_dir)
    yield gm
    reset_graph_manager()


# -- RelationshipGraph core tests ---------------------------------------------


def test_relationship_graph_add_nodes_and_edges():
    graph = RelationshipGraph(work_id="test")
    graph.add_node("a", {"char_id": "a", "name": "Alice"})
    graph.add_node("b", {"char_id": "b", "name": "Bob"})

    edge = RelationshipEdge(
        source_id="a",
        target_id="b",
        rel_type=RelationshipType.ALLY,
        weight=0.8,
        bidirectional=True,
    )
    graph.add_edge(edge)

    assert "a" in graph.nodes
    assert "b" in graph.nodes
    assert len(graph.edges) == 2  # bidirectional creates reverse edge
    assert graph.get_edge("a", "b").rel_type == RelationshipType.ALLY
    assert graph.get_edge("b", "a").rel_type == RelationshipType.ALLY


def test_relationship_graph_remove_edge():
    graph = RelationshipGraph(work_id="test")
    graph.add_node("a", {"char_id": "a"})
    graph.add_node("b", {"char_id": "b"})

    edge = RelationshipEdge(source_id="a", target_id="b", rel_type=RelationshipType.FRIEND)
    graph.add_edge(edge)

    assert graph.remove_edge("a", "b") is True
    assert len(graph.edges) == 0
    assert graph.remove_edge("a", "b") is False


def test_relationship_graph_get_relationships():
    graph = RelationshipGraph(work_id="test")
    graph.add_node("a", {"char_id": "a"})
    graph.add_node("b", {"char_id": "b"})
    graph.add_node("c", {"char_id": "c"})

    graph.add_edge(RelationshipEdge("a", "b", RelationshipType.ALLY))
    graph.add_edge(RelationshipEdge("b", "a", RelationshipType.FRIEND))
    graph.add_edge(RelationshipEdge("c", "a", RelationshipType.ENEMY))

    outgoing = graph.get_relationships("a", outgoing=True)
    incoming = graph.get_relationships("a", outgoing=False)

    assert len(outgoing) == 1
    assert outgoing[0].target_id == "b"
    assert len(incoming) == 2
    assert {e.source_id for e in incoming} == {"b", "c"}


def test_relationship_graph_faction_operations():
    graph = RelationshipGraph(work_id="test")
    graph.add_node("a", {"char_id": "a", "name": "Alice"})
    graph.add_node("b", {"char_id": "b", "name": "Bob"})

    faction = Faction(
        faction_id="order",
        name="Order of Light",
        faction_type=FactionType.RELIGIOUS,
        leader_id="a",
    )
    graph.add_faction(faction)
    graph.assign_character_to_faction("a", "order")
    graph.assign_character_to_faction("b", "order")

    assert graph.get_character_faction("a").faction_id == "order"
    assert sorted(graph.get_faction_members("order")) == ["a", "b"]
    assert graph.remove_character_from_faction("b") is True
    assert graph.get_faction_members("order") == ["a"]


def test_relationship_graph_matrices():
    graph = RelationshipGraph(work_id="test")
    graph.add_node("a", {"char_id": "a"})
    graph.add_node("b", {"char_id": "b"})
    graph.add_node("c", {"char_id": "c"})

    graph.add_edge(RelationshipEdge("a", "b", RelationshipType.ALLY, weight=0.8))
    graph.add_edge(RelationshipEdge("a", "c", RelationshipType.ENEMY, weight=-0.9))

    rel_matrix = graph.get_relationship_matrix()
    assert rel_matrix["a"]["b"] == 0.8
    assert rel_matrix["a"]["c"] == -0.9
    assert rel_matrix["b"]["a"] == 0.0  # no reverse edge


def test_relationship_graph_shortest_path():
    graph = RelationshipGraph(work_id="test")
    graph.add_node("a", {"char_id": "a"})
    graph.add_node("b", {"char_id": "b"})
    graph.add_node("c", {"char_id": "c"})
    graph.add_node("d", {"char_id": "d"})

    graph.add_edge(RelationshipEdge("a", "b", RelationshipType.FRIEND))
    graph.add_edge(RelationshipEdge("b", "c", RelationshipType.ALLY))
    graph.add_edge(RelationshipEdge("c", "d", RelationshipType.FAMILY))

    path = graph.find_shortest_path("a", "d")
    assert path == ["a", "b", "c", "d"]

    assert graph.find_shortest_path("a", "a") == ["a"]
    assert graph.find_shortest_path("a", "x") is None


def test_relationship_graph_serialization():
    graph = RelationshipGraph(work_id="test")
    graph.add_node("a", {"char_id": "a", "name": "Alice"})
    graph.add_edge(RelationshipEdge("a", "a", RelationshipType.NEUTRAL))  # self-edge test

    data = graph.to_dict()
    restored = RelationshipGraph.from_dict(data)

    assert restored.work_id == "test"
    assert "a" in restored.nodes
    assert "a:a" in restored.edges


# -- GraphManager tests -------------------------------------------------------


def test_graph_manager_creates_and_saves(work_with_characters):
    gm = GraphManager(store_dir=work_with_characters)
    graph = gm.get_or_create_graph("test_graph")

    assert "hero" in graph.nodes
    assert "mentor" in graph.nodes
    assert "villain" in graph.nodes

    # Check that relationships from CharacterBible were synced
    assert len(graph.edges) > 0


def test_graph_manager_add_relationship(work_with_characters):
    gm = GraphManager(store_dir=work_with_characters)
    result = gm.add_relationship(
        work_id="test_graph",
        source_id="hero",
        target_id="villain",
        rel_type=RelationshipType.ENEMY,
        weight=-0.9,
        evidence=["canon:evt_1"],
    )

    assert result["status"] == "added"
    assert result["edge"]["rel_type"] == "enemy"
    assert result["edge"]["weight"] == -0.9

    # Verify persistence
    gm2 = GraphManager(store_dir=work_with_characters)
    graph = gm2.get_or_create_graph("test_graph")
    edge = graph.get_edge("hero", "villain")
    assert edge is not None
    assert edge.rel_type == RelationshipType.ENEMY


def test_graph_manager_update_relationship(work_with_characters):
    gm = GraphManager(store_dir=work_with_characters)
    gm.add_relationship("test_graph", "hero", "rival", RelationshipType.RIVAL, weight=-0.4)

    result = gm.update_relationship(
        work_id="test_graph",
        source_id="hero",
        target_id="rival",
        rel_type=RelationshipType.ENEMY,
        weight=-0.8,
    )

    assert result["status"] == "updated"
    assert result["edge"]["rel_type"] == "enemy"
    assert result["edge"]["weight"] == -0.8


def test_graph_manager_remove_relationship(work_with_characters):
    gm = GraphManager(store_dir=work_with_characters)
    gm.add_relationship("test_graph", "hero", "love", RelationshipType.ROMANTIC)

    result = gm.remove_relationship("test_graph", "hero", "love")
    assert result["status"] == "removed"

    result2 = gm.remove_relationship("test_graph", "hero", "love")
    assert result2["status"] == "error"


def test_graph_manager_get_relationships(work_with_characters):
    gm = GraphManager(store_dir=work_with_characters)
    gm.add_relationship("test_graph", "hero", "villain", RelationshipType.ENEMY)

    result = gm.get_relationships("test_graph", "hero")
    assert result["status"] == "ok"
    assert result["character_id"] == "hero"
    assert len(result["outgoing"]) >= 1
    assert any(e["target_id"] == "villain" for e in result["outgoing"])


def test_graph_manager_get_all_relationships(work_with_characters):
    gm = GraphManager(store_dir=work_with_characters)
    gm.add_relationship("test_graph", "hero", "villain", RelationshipType.ENEMY)

    result = gm.get_all_relationships("test_graph")
    assert result["status"] == "ok"
    assert len(result["relationships"]) >= 1


# -- Faction tests ------------------------------------------------------------


def test_graph_manager_create_faction(work_with_characters):
    gm = GraphManager(store_dir=work_with_characters)
    result = gm.create_faction(
        work_id="test_graph",
        faction_id="order",
        name="Order of Light",
        faction_type=FactionType.RELIGIOUS,
        description="Guardianes de la luz",
        leader_id="mentor",
        ideology=["luz", "justicia"],
    )

    assert result["status"] == "created"
    assert result["faction"]["name"] == "Order of Light"
    assert result["faction"]["faction_type"] == "religious"
    assert result["faction"]["leader_id"] == "mentor"
    assert "mentor" in result["faction"]["members"]


def test_graph_manager_faction_allies_enemies(work_with_characters):
    gm = GraphManager(store_dir=work_with_characters)
    gm.create_faction("test_graph", "order", "Order", FactionType.RELIGIOUS)
    gm.create_faction("test_graph", "cult", "Dark Cult", FactionType.SECRET_SOCIETY)

    result = gm.update_faction(
        "test_graph",
        "order",
        allies=["cult"],  # temporarily allies
    )
    assert "cult" in result["faction"]["allies"]

    result = gm.update_faction("test_graph", "order", enemies=["cult"], allies=[])
    assert "cult" in result["faction"]["enemies"]
    assert "cult" not in result["faction"]["allies"]


def test_graph_manager_assign_character_to_faction(work_with_characters):
    gm = GraphManager(store_dir=work_with_characters)
    gm.create_faction("test_graph", "guild", "Merchant Guild", FactionType.GUILD)

    result = gm.add_character_to_faction("test_graph", "hero", "guild")
    assert result["status"] == "assigned"

    graph = gm.get_or_create_graph("test_graph")
    assert graph.character_factions["hero"] == "guild"
    assert "hero" in graph.factions["guild"].members


def test_graph_manager_remove_character_from_faction(work_with_characters):
    gm = GraphManager(store_dir=work_with_characters)
    gm.create_faction("test_graph", "guild", "Guild", FactionType.GUILD)
    gm.add_character_to_faction("test_graph", "hero", "guild")

    result = gm.remove_character_from_faction("test_graph", "hero")
    assert result["status"] == "removed"

    graph = gm.get_or_create_graph("test_graph")
    assert "hero" not in graph.character_factions
    assert "hero" not in graph.factions["guild"].members


def test_graph_manager_list_factions(work_with_characters):
    gm = GraphManager(store_dir=work_with_characters)
    gm.create_faction("test_graph", "f1", "Faction 1", FactionType.POLITICAL)
    gm.create_faction("test_graph", "f2", "Faction 2", FactionType.MILITARY)

    result = gm.list_factions("test_graph")
    assert result["status"] == "ok"
    assert len(result["factions"]) == 2


# -- Conflict Checker tests ---------------------------------------------------


def test_check_relationship_conflict_betrayal(work_with_characters):
    gm = GraphManager(store_dir=work_with_characters)
    gm.add_relationship("test_graph", "hero", "mentor", RelationshipType.MENTOR, weight=0.7)

    result = gm.check_relationship_conflict("test_graph", "hero", "traiciona a su mentor", "mentor")

    assert result["status"] == "ok"
    assert result["has_conflicts"] is True
    assert len(result["conflicts"]) > 0
    assert result["conflicts"][0]["type"] == "betrayal"


def test_check_relationship_conflict_hostile_to_ally(work_with_characters):
    gm = GraphManager(store_dir=work_with_characters)
    gm.add_relationship("test_graph", "hero", "love", RelationshipType.ROMANTIC, weight=0.8)

    result = gm.check_relationship_conflict("test_graph", "hero", "ataca a su amada", "love")

    assert result["has_conflicts"] is True
    assert result["conflicts"][0]["type"] == "hostile_to_ally"


def test_check_relationship_conflict_support_to_enemy(work_with_characters):
    gm = GraphManager(store_dir=work_with_characters)
    gm.add_relationship("test_graph", "hero", "villain", RelationshipType.ENEMY, weight=-0.9)

    result = gm.check_relationship_conflict("test_graph", "hero", "ayuda a su enemigo", "villain")

    assert result["has_conflicts"] is True
    assert result["conflicts"][0]["type"] == "support_to_enemy"


def test_check_relationship_conflict_faction_enemy(work_with_characters):
    gm = GraphManager(store_dir=work_with_characters)
    gm.create_faction("test_graph", "order", "Order", FactionType.RELIGIOUS)
    gm.create_faction("test_graph", "cult", "Cult", FactionType.SECRET_SOCIETY)
    gm.update_faction("test_graph", "order", enemies=["cult"])
    gm.add_character_to_faction("test_graph", "hero", "order")
    gm.add_character_to_faction("test_graph", "villain", "cult")

    result = gm.check_relationship_conflict("test_graph", "hero", "colabora con", "villain")

    assert result["has_conflicts"] is True
    assert any(c["type"] == "faction_conflict" for c in result["conflicts"])


def test_check_relationship_conflict_no_conflict(work_with_characters):
    gm = GraphManager(store_dir=work_with_characters)
    gm.add_relationship("test_graph", "hero", "rival", RelationshipType.RIVAL, weight=-0.3)

    result = gm.check_relationship_conflict("test_graph", "hero", "compite en un torneo", "rival")

    # Rivalry + competition should not be a conflict
    assert result["has_conflicts"] is False


def test_get_relationship_summary(work_with_characters):
    gm = GraphManager(store_dir=work_with_characters)
    gm.add_relationship("test_graph", "hero", "mentor", RelationshipType.MENTOR)
    gm.add_relationship("test_graph", "hero", "villain", RelationshipType.ENEMY)
    gm.create_faction("test_graph", "order", "Order", FactionType.RELIGIOUS)
    gm.add_character_to_faction("test_graph", "hero", "order")

    result = gm.get_relationship_summary("test_graph", "hero")

    assert result["status"] == "ok"
    assert "Relaciones activas" in result["summary"]
    assert "Merlin" in result["summary"]  # mentor's name
    assert "Malakar" in result["summary"]  # villain's name
    assert "Facción: Order" in result["summary"]


def test_export_graph_data(work_with_characters):
    gm = GraphManager(store_dir=work_with_characters)
    gm.add_relationship("test_graph", "hero", "villain", RelationshipType.ENEMY)
    gm.create_faction("test_graph", "order", "Order", FactionType.RELIGIOUS)
    gm.add_character_to_faction("test_graph", "hero", "order")

    result = gm.export_graph_data("test_graph")

    assert result["status"] == "ok"
    assert len(result["nodes"]) >= 5
    assert len(result["edges"]) >= 1
    assert len(result["factions"]) >= 1
    assert "hero" in result["character_factions"]
    assert "hero" in result["relationship_matrix"]
    assert "order" in result["faction_matrix"]


# -- REST API tests -----------------------------------------------------------


def _rest_setup(temp_story_dir, monkeypatch):
    from backend.story_memory.character_bible import CharacterBible
    from backend.story_memory.story_storage import StoryStorage
    from backend.story_routes import router

    monkeypatch.setenv("AURA_STORY_DIR", temp_story_dir)

    storage = StoryStorage(store_dir=temp_story_dir)
    storage.create_work("rest_graph", "REST Graph", "Test", "Test", "Test")

    cb = CharacterBible()
    cb.create("rest_graph", "hero", "Aldric")
    cb.create("rest_graph", "villain", "Malakar")

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_rest_get_relationships(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)

    r = client.get("/api/story/rest_graph/relationships")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"


def test_rest_add_relationship(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)

    r = client.post(
        "/api/story/rest_graph/relationships",
        json={
            "source_id": "hero",
            "target_id": "villain",
            "rel_type": "enemy",
            "weight": -0.9,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "added"
    assert body["edge"]["rel_type"] == "enemy"


def test_rest_add_relationship_invalid_type(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)

    r = client.post(
        "/api/story/rest_graph/relationships",
        json={
            "source_id": "hero",
            "target_id": "villain",
            "rel_type": "invalid_type",
        },
    )
    assert r.status_code == 422


def test_rest_update_relationship(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    client.post(
        "/api/story/rest_graph/relationships",
        json={"source_id": "hero", "target_id": "villain", "rel_type": "rival"},
    )

    r = client.put(
        "/api/story/rest_graph/relationships/hero/villain",
        json={
            "rel_type": "enemy",
            "weight": -0.8,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "updated"
    assert body["edge"]["rel_type"] == "enemy"


def test_rest_remove_relationship(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    client.post(
        "/api/story/rest_graph/relationships",
        json={"source_id": "hero", "target_id": "villain", "rel_type": "enemy"},
    )

    r = client.delete("/api/story/rest_graph/relationships/hero/villain")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "removed"


def test_rest_relationship_summary(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    client.post(
        "/api/story/rest_graph/relationships",
        json={"source_id": "hero", "target_id": "villain", "rel_type": "enemy"},
    )

    r = client.get("/api/story/rest_graph/relationships/summary/hero")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "enemy" in body["summary"]


def test_rest_check_conflict(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    client.post(
        "/api/story/rest_graph/relationships",
        json={"source_id": "hero", "target_id": "villain", "rel_type": "enemy"},
    )

    r = client.post(
        "/api/story/rest_graph/relationships/check-conflict",
        json={
            "char_id": "hero",
            "proposed_action": "ayuda al villano",
            "target_char_id": "villain",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["has_conflicts"] is True


def test_rest_export_graph(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)

    r = client.get("/api/story/rest_graph/relationships/graph")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "nodes" in body
    assert "edges" in body
    assert "factions" in body
    assert "relationship_matrix" in body


# -- Faction REST tests -------------------------------------------------------


def test_rest_create_faction(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)

    r = client.post(
        "/api/story/rest_graph/factions",
        json={
            "faction_id": "order",
            "name": "Order of Light",
            "faction_type": "religious",
            "leader_id": "hero",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "created"
    assert body["faction"]["name"] == "Order of Light"


def test_rest_list_factions(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    client.post(
        "/api/story/rest_graph/factions",
        json={"faction_id": "f1", "name": "F1", "faction_type": "political"},
    )

    r = client.get("/api/story/rest_graph/factions")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert len(body["factions"]) >= 1


def test_rest_get_faction(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    client.post(
        "/api/story/rest_graph/factions",
        json={"faction_id": "order", "name": "Order", "faction_type": "religious"},
    )

    r = client.get("/api/story/rest_graph/factions/order")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["faction"]["faction_id"] == "order"


def test_rest_update_faction(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    client.post(
        "/api/story/rest_graph/factions",
        json={"faction_id": "order", "name": "Order", "faction_type": "religious"},
    )

    r = client.put(
        "/api/story/rest_graph/factions/order",
        json={
            "enemies": ["cult"],
            "territory": ["capital"],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "updated"
    assert "cult" in body["faction"]["enemies"]


def test_rest_delete_faction(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    client.post(
        "/api/story/rest_graph/factions",
        json={"faction_id": "order", "name": "Order", "faction_type": "religious"},
    )

    r = client.delete("/api/story/rest_graph/factions/order")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "deleted"


def test_rest_add_character_to_faction(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    client.post(
        "/api/story/rest_graph/factions",
        json={"faction_id": "guild", "name": "Guild", "faction_type": "guild"},
    )

    r = client.post("/api/story/rest_graph/factions/guild/members/hero")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "assigned"
    assert body["character_id"] == "hero"


def test_rest_remove_character_from_faction(temp_story_dir, monkeypatch):
    client = _rest_setup(temp_story_dir, monkeypatch)
    client.post(
        "/api/story/rest_graph/factions",
        json={"faction_id": "guild", "name": "Guild", "faction_type": "guild"},
    )
    client.post("/api/story/rest_graph/factions/guild/members/hero")

    r = client.delete("/api/story/rest_graph/factions/guild/members/hero")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "removed"
