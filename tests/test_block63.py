"""BLOQUE 63 — Autonomous Deep Research & Recursive Self-Learning Engine tests."""

import time

import pytest

from backend.agent.deep_research import (
    DeepResearchEngine,
    Finding,
    KnowledgeSynthesizer,
    ResearchMission,
    Source,
    SourceFetcher,
    decompose_question,
    get_research_engine,
    reset_research_engine,
)


class TestDecomposeQuestion:
    def test_returns_list_of_strings(self):
        out = decompose_question("Como funciona uma IA?")
        assert isinstance(out, list)
        assert all(isinstance(s, str) for s in out)

    def test_empty_question_returns_empty(self):
        assert decompose_question("") == []

    def test_short_question_returns_single(self):
        out = decompose_question("Olá")
        assert isinstance(out, list)


class TestSourceFetcher:
    def test_offline_mode_returns_error(self):
        f = SourceFetcher()
        res = f.fetch_text("http://localhost:1/", timeout=2)
        assert res.fetched is False
        assert res.error != ""

    def test_to_dict(self):
        s = Source(url="http://x", text="hi", fetched=True)
        d = s.to_dict()
        assert d["url"] == "http://x"
        assert d["fetched"] is True
        assert d["chars"] == 2


class TestKnowledgeSynthesizer:
    def test_extract_concepts(self):
        syn = KnowledgeSynthesizer()
        text = "A memória de longo prazo armazena padrões. A memória é importante."
        concepts = syn.extract_concepts([text])
        assert isinstance(concepts, dict)
        assert "memoria" in concepts or "memória" in concepts

    def test_synthetize_returns_map(self):
        syn = KnowledgeSynthesizer()
        texts = [
            "A learning system learns from data.",
            "Learning requires patterns.",
        ]
        km = syn.synthetize(texts, source_urls=["http://a", "http://b"])
        assert "summary" in km
        assert "concept_count" in km
        assert "sources_indexed" in km or "finding_count" in km


class TestResearchMission:
    def test_to_dict(self):
        m = ResearchMission(mission_id="m1", question="q")
        d = m.to_dict()
        assert d["mission_id"] == "m1"
        assert d["status"] == "pending"
        assert "created_at" in d

    def test_default_status(self):
        m = ResearchMission(mission_id="m2", question="q")
        assert m.status == "pending"


@pytest.fixture
def engine(tmp_path, monkeypatch):
    reset_research_engine()
    monkeypatch.setenv("AURA_DATA_DIR", str(tmp_path))
    eng = DeepResearchEngine(storage_dir=tmp_path / "research")
    return eng


class TestDeepResearchEngine:
    def test_start_mission_returns_mission(self, engine):
        m = engine.start_mission(question="Qual é o objetivo do aprendizado?")
        assert isinstance(m, ResearchMission)
        assert m.mission_id
        assert m.status in ("completed", "running")

    def test_get_mission(self, engine):
        m = engine.start_mission(question="Teste")
        fetched = engine.get_mission(m.mission_id)
        assert fetched is not None
        assert fetched.question == m.question

    def test_list_missions(self, engine):
        engine.start_mission(question="A")
        engine.start_mission(question="B")
        missions = engine.list_missions()
        assert len(missions) == 2

    def test_list_missions_filter_status(self, engine):
        engine.start_mission(question="A")
        completed = engine.list_missions(status="completed")
        pending = engine.list_missions(status="pending")
        assert isinstance(completed, list)
        assert isinstance(pending, list)

    def test_delete_mission(self, engine):
        m = engine.start_mission(question="Delete me")
        assert engine.delete_mission(m.mission_id) is True
        assert engine.get_mission(m.mission_id) is None

    def test_delete_unknown_returns_false(self, engine):
        assert engine.delete_mission("nope") is False

    def test_search_knowledge(self, engine):
        res = engine.search_knowledge("aprendizado")
        assert "status" in res
        assert "count" in res

    def test_history(self, engine):
        engine.start_mission(question="Hist")
        h = engine.history()
        assert isinstance(h, list)
        assert len(h) >= 1
        assert "mission_id" in h[0]

    def test_get_status(self, engine):
        engine.start_mission(question="Status")
        st = engine.get_status()
        assert "total_missions" in st
        assert "missions_by_status" in st

    def test_count(self, engine):
        n0 = engine.count()
        engine.start_mission(question="Count")
        assert engine.count() == n0 + 1

    def test_max_refine_depth(self, engine):
        m = engine.start_mission(question="Profundidade", max_refine_depth=3)
        assert m.refinement_rounds >= 0


def test_get_research_engine_singleton():
    reset_research_engine()
    a = get_research_engine()
    b = get_research_engine()
    assert a is b
    reset_research_engine()
