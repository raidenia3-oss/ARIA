"""Tests Bloque 41 - Local Semantic Memory & Vector RAG Engine.

Valida:
- Vectorizacion local offline (feature hashing + n-gramas, NumPy).
- Indexacion persistente en disco del lore (canon, characters, chapters).
- Precision de recuperacion: query relevante retorna el fragmento canonico correcto.
- Persistencia on-disk mantiene recall entre sesiones.
- Jan Context Injector produce un bloque de lore inyectable.
- Endpoints REST semanticos (/semantic-index, /status, /semantic-search, /context-inject).
"""

from __future__ import annotations

import numpy as np
import pytest

from backend.story_memory.canon_tracker import CanonTracker
from backend.story_memory.character_bible import CharacterBible
from backend.story_memory.story_storage import StoryStorage
from backend.story_memory.vector_rag import (
    LocalEmbeddingVectorizer,
    chunk_text,
    get_vector_engine,
    reset_vector_engine,
    set_engine_store_path,
)

DIM = 256  # dimension pequena para tests rapidos y deterministicos


@pytest.fixture
def engine(tmp_path, monkeypatch):
    story_dir = str(tmp_path / "story")
    monkeypatch.setenv("AURA_STORY_DIR", story_dir)
    set_engine_store_path(story_dir)
    eng = get_vector_engine()
    eng.vectorizer = LocalEmbeddingVectorizer(dim=DIM, n=3)
    yield eng
    reset_vector_engine()


@pytest.fixture
def work_with_lore(engine):
    store = StoryStorage(store_dir=engine.store_dir)
    store.create_work(
        work_id="obra_rag",
        title="Obra RAG",
        universe="fantasia",
        description="d",
        author="tester",
    )
    ct = CanonTracker()
    ct.add_canon_event(work_id="obra_rag", description="El héroe nace en la aldea de Bruma")
    ct.add_canon_event(work_id="obra_rag", description="El héroe salva el mundo del dragón")
    cb = CharacterBible()
    cb.create(
        work_id="obra_rag",
        char_id="heroe",
        name="Aiden",
        voice="Narrativa en tercera persona",
        personality=["valiente", "leal"],
        backstory="Hijo de un herrero de la aldea de Bruma",
    )
    return engine


# -- vectorizador ----------------------------------------------------------


def test_vectorizer_shape_and_normalized():
    v = LocalEmbeddingVectorizer(dim=128, n=3)
    vec = v.vectorize("El héroe valiente")
    assert vec.shape == (128,)
    assert abs(np.linalg.norm(vec) - 1.0) < 1e-6


def test_vectorizer_deterministic():
    v = LocalEmbeddingVectorizer(dim=128, n=3)
    a = v.vectorize("El dragón de fuego")
    b = v.vectorize("El dragón de fuego")
    assert np.allclose(a, b)


def test_vectorizer_empty_text_is_zero():
    v = LocalEmbeddingVectorizer(dim=64, n=3)
    vec = v.vectorize("")
    assert np.linalg.norm(vec) == 0.0


def test_vectorizer_relevant_overlap_has_higher_similarity():
    v = LocalEmbeddingVectorizer(dim=256, n=3)
    q = v.vectorize("el héroe salva")
    near = v.vectorize("el héroe salva el mundo")
    far = v.vectorize("la tienda de pan fríen pan")
    sim_near = float(np.dot(q, near))
    sim_far = float(np.dot(q, far))
    assert sim_near > sim_far


# -- chunker ----------------------------------------------------------------


def test_chunk_text_short_text_single_chunk():
    assert chunk_text("hola", 150, 50) == ["hola"]


def test_chunk_text_long_overlapping():
    text = "a" * 400
    chunks = chunk_text(text, 150, 50)
    assert len(chunks) >= 2
    assert chunks[-1].endswith("a")


# -- indexacion -------------------------------------------------------------


def test_index_work_creates_fragments(work_with_lore):
    res = work_with_lore.index_work("obra_rag")
    assert res["status"] == "ok"
    assert res["indexed_fragments"] > 0
    assert "canon" in res["sources"]


def test_index_work_not_found_returns_error(work_with_lore):
    res = work_with_lore.index_work("nonexistent_work")
    assert res["status"] == "error"
    assert res["error"] == "work_not_found"


def test_get_status_not_indexed(engine):
    assert engine.get_status("sin_indice")["status"] == "not_indexed"


def test_get_status_indexed_after_index(work_with_lore):
    work_with_lore.index_work("obra_rag")
    st = work_with_lore.get_status("obra_rag")
    assert st["status"] == "indexed"
    assert st["fragments"] > 0
    assert "canon" in st["source_counts"]


# -- busqueda semantica -----------------------------------------------------


def test_search_returns_relevant_canon(work_with_lore):
    work_with_lore.index_work("obra_rag")
    res = work_with_lore.semantic_search("obra_rag", "héroe salva el mundo")
    assert res["status"] == "ok"
    assert len(res["results"]) > 0
    top = res["results"][0]
    assert top["score"] > 0
    assert "dragón" in " ".join(r["text"] for r in res["results"][:3]).lower()


def test_search_returns_character_fragment(work_with_lore):
    work_with_lore.index_work("obra_rag")
    res = work_with_lore.semantic_search("obra_rag", "aldea de Bruma herrero")
    texts = " ".join(r["text"] for r in res["results"])
    assert "bruma" in texts.lower()


def test_search_empty_when_not_indexed(work_with_lore):
    res = work_with_lore.semantic_search("obra_rag", "héroe")
    assert res["results"] == []
    assert res["context"] == ""


def test_search_respects_top_k(work_with_lore):
    work_with_lore.index_work("obra_rag")
    res = work_with_lore.semantic_search("obra_rag", "héroe", top_k=1)
    assert len(res["results"]) == 1


# -- persistencia ----------------------------------------------------------


def test_persistence_maintains_recall(tmp_path, monkeypatch):
    from backend.story_memory.vector_rag import VectorRAGEngine  # noqa: F401 (sanity import)

    store_dir = str(tmp_path / "story")
    monkeypatch.setenv("AURA_STORY_DIR", store_dir)
    set_engine_store_path(store_dir)
    eng1 = get_vector_engine()
    eng1.vectorizer = LocalEmbeddingVectorizer(dim=DIM, n=3)
    store = StoryStorage(store_dir=store_dir)
    store.create_work(work_id="w", title="W", universe="u", description="d", author="t")
    CanonTracker().add_canon_event(work_id="w", description="La llama eterna del templo")
    eng1.index_work("w")

    reset_vector_engine()
    set_engine_store_path(store_dir)
    eng2 = get_vector_engine()
    eng2.vectorizer = LocalEmbeddingVectorizer(dim=DIM, n=3)
    assert eng2.get_status("w")["status"] == "indexed"
    res = eng2.semantic_search("w", "llama eterna")
    assert any("llama" in r["text"].lower() for r in res["results"])
    reset_vector_engine()


# -- Jan Context Injector --------------------------------------------------


def test_inject_context_returns_block(work_with_lore):
    work_with_lore.index_work("obra_rag")
    ctx = work_with_lore.inject_context("obra_rag", "dragón", top_k=3, max_chars=500)
    assert ctx.startswith("[LORE")
    assert "dragón" in ctx.lower()


def test_inject_context_empty_when_no_index(engine):
    assert engine.inject_context("nope", "algo") == ""


# -- REST integration -------------------------------------------------------


def _rest_setup(monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.story_routes import router

    story_dir = str(tmp_path / "story")
    monkeypatch.setenv("AURA_STORY_DIR", story_dir)
    set_engine_store_path(story_dir)
    store = StoryStorage(store_dir=story_dir)
    store.create_work(
        work_id="rest_rag", title="REST RAG", universe="u", description="d", author="tester"
    )
    ct = CanonTracker()
    ct.add_canon_event(work_id="rest_rag", description="La espada elegida del rey")
    ct.add_canon_event(work_id="rest_rag", description="La traición en la corte")
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_rest_index_and_status(monkeypatch, tmp_path):
    client = _rest_setup(monkeypatch, tmp_path)
    r = client.post("/api/story/rest_rag/semantic-index")
    assert r.status_code == 201
    assert r.json()["status"] == "ok"
    s = client.get("/api/story/rest_rag/semantic-index/status")
    assert s.status_code == 200
    assert s.json()["status"] == "indexed"
    reset_vector_engine()


def test_rest_index_work_not_found(monkeypatch, tmp_path):
    client = _rest_setup(monkeypatch, tmp_path)
    r = client.post("/api/story/ghost/semantic-index")
    assert r.status_code == 404
    reset_vector_engine()


def test_rest_semantic_search(monkeypatch, tmp_path):
    client = _rest_setup(monkeypatch, tmp_path)
    client.post("/api/story/rest_rag/semantic-index")
    r = client.post(
        "/api/story/rest_rag/semantic-search", json={"query": "espada elegida", "top_k": 2}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["query"] == "espada elegida"
    assert len(body["results"]) <= 2
    assert "espada" in " ".join(x["text"] for x in body["results"]).lower()
    reset_vector_engine()


def test_rest_context_inject(monkeypatch, tmp_path):
    client = _rest_setup(monkeypatch, tmp_path)
    client.post("/api/story/rest_rag/semantic-index")
    r = client.post(
        "/api/story/rest_rag/context-inject",
        json={"query": "traición corte", "top_k": 2, "max_chars": 300},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["context"].startswith("[LORE")
    assert "traición" in body["context"].lower()
    reset_vector_engine()


def test_rest_semantic_search_requires_query(monkeypatch, tmp_path):
    client = _rest_setup(monkeypatch, tmp_path)
    r = client.post("/api/story/rest_rag/semantic-search", json={"top_k": 2})
    assert r.status_code == 422
    reset_vector_engine()
