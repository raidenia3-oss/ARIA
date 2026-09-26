"""BLOQUE 72 - Unit tests for Knowledge RAG engine."""

import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pytest

from backend.knowledge.models import (
    IndexStrategy,
)
from backend.knowledge.rag import (
    KnowledgeStore,
    KnowledgeVectorizer,
    RAGEngine,
    chunk_text,
    get_rag_engine,
    reset_rag_engine,
)


def test_vectorizer_basic():
    v = KnowledgeVectorizer(dim=256)
    a = v.vectorize("hello world hello")
    b = v.vectorize("hello world")
    assert a.shape == (256,)
    assert b.shape == (256,)
    # both are L2-normalized unit vectors
    assert abs(float(np.linalg.norm(a)) - 1.0) < 1e-6
    assert abs(float(np.linalg.norm(b)) - 1.0) < 1e-6


def test_vectorizer_different_texts():
    v = KnowledgeVectorizer(dim=256)
    a = v.vectorize("the cat sat on the mat")
    b = v.vectorize("the dog ran in the park")
    assert a.shape == (256,)
    assert not (a == b).all()


def test_vectorizer_empty():
    v = KnowledgeVectorizer(dim=128)
    vec = v.vectorize("")
    assert vec.shape == (128,)


def test_chunk_text_paragraph():
    text = "Para one.\n\nPara two.\n\nPara three."
    chunks = chunk_text(text, strategy=IndexStrategy.PARAGRAPH, chunk_size=400, chunk_overlap=80)
    assert len(chunks) == 3


def test_chunk_text_sentence():
    text = "First sentence. Second sentence. Third sentence."
    chunks = chunk_text(text, strategy=IndexStrategy.SENTENCE, chunk_size=400, chunk_overlap=80)
    assert len(chunks) == 3


def test_chunk_text_fixed():
    text = "x" * 1000
    chunks = chunk_text(text, strategy=IndexStrategy.FIXED, chunk_size=200, chunk_overlap=50)
    assert len(chunks) >= 3


def test_chunk_text_empty():
    assert chunk_text("") == []


def test_store_roundtrip():
    tmp = tempfile.mkdtemp()
    try:
        store = KnowledgeStore(store_dir=tmp)
        store.save_collection("coll", {"collection": "coll", "fragments": [], "status": "ready"})
        data = store.load_collection("coll")
        assert data is not None
        assert data["collection"] == "coll"
        assert "coll" in store.list_collections()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_engine_index_and_search():
    tmp = tempfile.mkdtemp()
    try:
        eng = RAGEngine(store_dir=tmp)
        res = eng.index_text(
            "The quick brown fox jumps over the lazy dog.",
            collection="test",
            title="fox",
            source_type="manual",
        )
        assert res["status"] == "ok"
        assert res["chunks"] > 0
        info = eng.get_collection("test")
        assert info.chunk_count > 0
        sr = eng.search_text("fox", collection="test", top_k=3)
        assert sr.total_hits > 0
        assert len(sr.results) > 0
        ctx = eng.inject_context("fox", collection="test")
        assert "CONOCIMIENTO" in ctx
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_engine_purge():
    tmp = tempfile.mkdtemp()
    try:
        eng = RAGEngine(store_dir=tmp)
        eng.index_text("some content here", collection="p")
        eng.purge_collection("p")
        info = eng.get_collection("p")
        assert info.chunk_count == 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_engine_status():
    tmp = tempfile.mkdtemp()
    try:
        eng = RAGEngine(store_dir=tmp)
        st = eng.status()
        assert st.enabled is True
        assert st.total_documents == 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_engine_reset():
    tmp = tempfile.mkdtemp()
    try:
        eng = RAGEngine(store_dir=tmp)
        eng.index_text("data", collection="r")
        eng.reset()
        assert eng.list_collections() == []
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_singleton():
    reset_rag_engine()
    e1 = get_rag_engine()
    e2 = get_rag_engine()
    assert e1 is e2
    reset_rag_engine()
    e3 = get_rag_engine()
    assert e3 is not e1


def test_concurrent_index():
    import threading

    tmp = tempfile.mkdtemp()
    try:
        eng = RAGEngine(store_dir=tmp)
        errors = []

        def worker(i):
            try:
                eng.index_text(
                    "document number " + str(i) + " with unique content xyz" + str(i),
                    collection="conc",
                    doc_id="doc_" + str(i),
                )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert eng.get_collection("conc").document_count == 10
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
