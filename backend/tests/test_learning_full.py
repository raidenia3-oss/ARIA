import pytest
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestAutoDocumentation:
    def setup_method(self):
        from backend.learning.auto_documentation import AutoDocumenter
        self.doc = AutoDocumenter(project_root="backend", output_dir="data/test_doc")

    def test_scan_project(self):
        scan = self.doc.scan_project()
        assert "modules" in scan
        assert isinstance(scan["modules"], list)
        assert scan["total_modules"] >= 0

    def test_readme_generation(self):
        readme = self.doc.generate_readme("Test Project")
        assert "# Test Project" in readme
        assert "## Estructura del Proyecto" in readme

    def test_changelog_generation(self):
        changelog = self.doc.generate_changelog("1.0.0")
        assert "# Changelog v1.0.0" in changelog

    def test_api_docs_generation(self):
        docs = self.doc.generate_api_docs()
        assert "# API Documentation" in docs

    def test_architecture_guide(self):
        guide = self.doc.generate_architecture_guide()
        assert "# Guía de Arquitectura" in guide

    def test_documentation_status(self):
        self.doc.scan_project()
        status = self.doc.get_documentation_status()
        assert status["project_scanned"] is True
        assert status["last_update"] is not None


class TestLearningEngine:
    def setup_method(self):
        from backend.learning.learning_loop import LearningEngine
        self.engine = LearningEngine()
        self.engine._data_file.unlink(missing_ok=True)
        self.engine.evaluations.clear()
        self.engine.proposals.clear()

    def test_evaluate_research(self):
        output = {
            "papers": [{"title": "Test"}] * 10,
            "findings": [{"text": "test"}] * 5,
            "summary": "A" * 200,
            "coverage": 0.8,
            "confidence": 0.9,
            "concepts": {"ai": 5, "test": 3},
            "sources": [{"url": "test.com"}] * 5,
        }
        result = self.engine.evaluate_research(output)
        assert 0 <= result.score <= 1.0
        assert len(result.metrics) > 0
        assert len(result.suggestions) > 0

    def test_evaluate_research_low_quality(self):
        output = {"summary": "short"}
        result = self.engine.evaluate_research(output)
        assert result.score < 0.7
        assert len(result.suggestions) > 0

    def test_propose_improvements(self):
        for _ in range(5):
            self.engine.evaluate_research({"papers": [], "summary": "test", "coverage": 0.3})
        proposals = self.engine.propose_improvements()
        assert isinstance(proposals, list)

    def test_apply_proposal(self):
        self.engine.propose_improvements()
        if self.engine.proposals:
            applied = self.engine.apply_proposal(self.engine.proposals[0].proposal_id)
            assert applied is True

    def test_get_learning_report(self):
        report = self.engine.get_learning_report()
        assert "total_evaluations" in report
        assert "average_score" in report
        assert "score_trend" in report


class TestMistakeMemory:
    def setup_method(self):
        from backend.learning.mistake_memory import MistakeMemory
        self.memory = MistakeMemory()
        self.memory._index_file.unlink(missing_ok=True)
        self.memory.mistakes.clear()

    def test_record_mistake(self):
        result = self.memory.record("test_error", "Something failed", {"key": "value"})
        assert result.error_type == "test_error"
        assert result.times_repeated == 1

    def test_record_repeat(self):
        self.memory.record("test_error", "msg")
        self.memory.record("test_error", "msg")
        self.memory.record("test_error", "msg")
        entry = self.memory.mistakes[list(self.memory.mistakes.keys())[-1]]
        assert entry.times_repeated == 3

    def test_check_before_safe(self):
        result = self.memory.check_before_execute("new_error", {})
        assert result["safe"] is True

    def test_check_before_blocked(self):
        for _ in range(3):
            self.memory.record("blocked_error", "msg")
        result = self.memory.check_before_execute("blocked_error", {})
        assert result["safe"] is False

    def test_learn_from(self):
        self.memory.record("learn_error", "msg")
        result = self.memory.learn_from("learn_error", "alternative_action")
        assert result is True

    def test_get_stats(self):
        stats = self.memory.get_stats()
        assert "total_mistakes" in stats


class TestKnowledgeGraph:
    def setup_method(self):
        from backend.learning.knowledge_graph import KnowledgeGraph
        self.kg = KnowledgeGraph()
        self.kg.STORAGE_FILE.unlink(missing_ok=True)
        self.kg.nodes.clear()
        self.kg.edges.clear()
        self.kg._adjacency.clear()
        self.kg._reverse_adj.clear()

    def test_add_node(self):
        node = self.kg.add_node("test", "Test", "topic")
        assert node.label == "Test"
        assert node.node_id == "test"

    def test_add_edge(self):
        self.kg.add_node("a", "A", "topic")
        self.kg.add_node("b", "B", "topic")
        edge = self.kg.add_edge("a", "b", "related")
        assert edge.source == "a"
        assert edge.target == "b"

    def test_get_neighbors(self):
        self.kg.add_node("a", "A", "topic")
        self.kg.add_node("b", "B", "topic")
        self.kg.add_node("c", "C", "topic")
        self.kg.add_edge("a", "b", "related")
        self.kg.add_edge("a", "c", "related")
        neighbors = self.kg.get_neighbors("a")
        assert len(neighbors) == 2

    def test_find_path(self):
        self.kg.add_node("a", "A", "topic")
        self.kg.add_node("b", "B", "topic")
        self.kg.add_node("c", "C", "topic")
        self.kg.add_edge("a", "b", "related")
        self.kg.add_edge("b", "c", "related")
        path = self.kg.find_path("a", "c")
        assert path == ["a", "b", "c"]

    def test_detect_gaps(self):
        self.kg.add_node("isolated", "Iso", "research")
        gaps = self.kg.detect_gaps("research")
        assert len(gaps) >= 1

    def test_search(self):
        self.kg.add_node("AI Research", "AI Research", "topic")
        results = self.kg.search("AI")
        assert len(results) >= 1

    def test_get_stats(self):
        stats = self.kg.get_stats()
        assert "total_nodes" in stats
        assert "total_edges" in stats


class TestAutoPromptGenerator:
    def setup_method(self):
        from backend.learning.auto_prompt import AutoPromptGenerator
        self.gen = AutoPromptGenerator()
        self.gen.STORAGE_FILE.unlink(missing_ok=True)
        self.gen.population.clear()
        self.gen.history.clear()

    def test_generate_prompt(self):
        prompt = self.gen.generate_prompt("research", {"topic": "AI"})
        assert "AI" in prompt.template
        assert prompt.genome_id.startswith("PG-")

    def test_evaluate_prompt(self):
        prompt = self.gen.generate_prompt("research")
        self.gen.evaluate_prompt(prompt.genome_id, success=True, score=0.8)
        assert prompt.uses == 1

    def test_evolve(self):
        for _ in range(3):
            self.gen.generate_prompt("research")
            self.gen.evaluate_prompt(self.gen.population[-1].genome_id, True, 0.7)
        best = self.gen.evolve("research")
        assert best is not None

    def test_get_best_prompt(self):
        self.gen.generate_prompt("research")
        best = self.gen.get_best_prompt("research")
        assert best is not None


class TestAutoScaler:
    def setup_method(self):
        from backend.learning.auto_scaling import AutoScaler
        self.scaler = AutoScaler(default_parallel=4)

    def test_get_parallelism_default(self):
        assert self.scaler.get_parallelism("test") == 4

    def test_record_task(self):
        self.scaler.record_task_start("test")
        time.sleep(0.01)
        duration = self.scaler.record_task_end("test", success=True)
        assert duration > 0

    def test_scale_up(self):
        self.scaler.update_system_metrics(0.2, 0.3)
        parallel = self.scaler.get_parallelism("test")
        assert parallel >= 4

    def test_scale_down(self):
        self.scaler.update_system_metrics(0.95, 0.3)
        parallel = self.scaler.get_parallelism("test")
        assert parallel <= 2

    def test_bottleneck_report(self):
        report = self.scaler.get_bottlenecks_report()
        assert "active_bottlenecks" in report


class TestLearningDaemon:
    def setup_method(self):
        from backend.daemon.learning_daemon import LearningDaemon
        self.daemon = LearningDaemon()

    def test_initial_status(self):
        status = self.daemon.get_status()
        assert status["active"] is False
        assert status["cycle_count"] == 0

    def test_get_status(self):
        status = self.daemon.get_status()
        assert "next_cycle_in" in status


class TestLearningIntegration:
    def test_full_pipeline(self):
        from backend.learning.learning_loop import learning_engine
        from backend.learning.mistake_memory import mistake_memory
        from backend.learning.knowledge_graph import knowledge_graph
        from backend.learning.auto_prompt import auto_prompt_generator

        research = {
            "papers": [{"title": f"Paper {i}"} for i in range(10)],
            "findings": [{"text": f"Finding {i}"} for i in range(5)],
            "summary": "Comprehensive analysis of AI trends.",
            "coverage": 0.85,
            "confidence": 0.9,
            "concepts": {"AI": 3, "research": 2, "deep": 1},
            "sources": [{"url": f"source{i}.com"} for i in range(5)],
        }
        eval_result = learning_engine.evaluate_research(research, "integration_test")
        assert eval_result.score > 0.6

        mistakes_before = mistake_memory.get_stats()["total_mistakes"]
        mistake_memory.record("integration_test", "test error")
        mistakes_after = mistake_memory.get_stats()["total_mistakes"]
        assert mistakes_after == mistakes_before + 1

        kg_node = knowledge_graph.add_node("integration_test", "integration_test", "topic")
        assert kg_node.node_id == "integration_test"

        best = auto_prompt_generator.get_best_prompt("research")
        if best is None:
            auto_prompt_generator.generate_prompt("research", {"topic": "test"})
            best = auto_prompt_generator.get_best_prompt("research")
        assert best is not None


class TestLearningRoutes:
    def test_routes_importable(self):
        from backend.api.learning_routes import router
        assert router is not None
        prefix = getattr(router, "prefix", "")
        assert "/api/learning" in prefix or prefix == "/api/learning"

    def test_routes_list(self):
        from backend.api.learning_routes import router
        routes = [r.path for r in router.routes if hasattr(r, "path")]
        expected = ["/status", "/cycle", "/evaluate", "/proposals", "/prompts", "/knowledge", "/bottlenecks", "/mistakes"]
        for path in expected:
            assert any(path in r for r in routes), f"Missing route: {path}"
