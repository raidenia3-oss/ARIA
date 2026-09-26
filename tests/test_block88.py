"""BLOQUE 88 - unit tests for cognitive graph engine (local/offline)."""

from backend.memory.cognitive_graph import (
    CognitiveGraphEngine,
    get_cognitive_graph,
    reset_cognitive_graph,
)


def test_ingest_creates_nodes_and_edges():
    reset_cognitive_graph()
    g = CognitiveGraphEngine()
    nodes = g.ingest(
        "AURA usa ChromaDB y depende de Ollama para RAG.", source="rag", kind="concept"
    )
    assert len(nodes) >= 2
    assert g.stats()["nodes"] >= 2
    assert g.stats()["edges"] >= 1
    reset_cognitive_graph()


def test_search_and_neighbors():
    reset_cognitive_graph()
    g = CognitiveGraphEngine()
    g.ingest("El modulo de seguridad cifra credenciales con Fernet.", source="interaction")
    g.ingest("El modulo de seguridad usa Fernet para credenciales.", source="interaction")
    res = g.search("seguridad")
    assert len(res) >= 1
    nid = res[0].node_id
    nb = g.neighbors(nid, limit=5)
    assert len(nb) >= 1
    reset_cognitive_graph()


def test_clusters_and_summaries():
    reset_cognitive_graph()
    g = CognitiveGraphEngine()
    g.ingest("AURA integra ChromaDB, Ollama y FastEmbed en el pipeline RAG.")
    g.ingest("El motor de memoria usa ChromaDB y embeddings locales.")
    g.ingest("El pipeline RAG consume Ollama y FastEmbed para busqueda.")
    g.consolidate(force=True)
    assert g.stats()["summaries"] >= 1
    assert len(g.clusters()) >= 1
    reset_cognitive_graph()


def test_singleton():
    reset_cognitive_graph()
    assert get_cognitive_graph() is get_cognitive_graph()
    reset_cognitive_graph()


def test_reset_clears_state():
    reset_cognitive_graph()
    g = get_cognitive_graph()
    g.ingest("AURA es soberana y local.", source="interaction")
    assert g.stats()["nodes"] >= 1
    g.reset()
    assert g.stats()["nodes"] == 0
    reset_cognitive_graph()
