"""Tests para AgentAutoConfigurator sin datos fabricados (regla: lo no medido se omite)."""
from __future__ import annotations

import asyncio
import json
from typing import Any

import backend.agents.agent_autoconfigurator as module
from backend.agents.agent_autoconfigurator import AgentAutoConfigurator


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def test_no_file_returns_unavailable(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    cfg = AgentAutoConfigurator()
    out = _run(cfg.analyze_agent_performance("fanfic"))
    assert out["data_source"] == "unavailable"
    assert out["total_runs"] == 0
    assert "accuracy" not in out or not isinstance(out.get("accuracy"), float)


def test_corrupt_json_is_unreadable(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "agents").mkdir(parents=True)
    (tmp_path / "data" / "agents" / "code_logs.json").write_text("{no json", encoding="utf-8")
    cfg = AgentAutoConfigurator()
    out = _run(cfg.analyze_agent_performance("code"))
    assert "error" in out
    assert out["data_source"] == "unavailable"
    # distinguible de missing: el archivo existe pero no se pudo medir
    import os
    assert os.path.isfile("data/agents/code_logs.json")


def test_real_logs_compute_accuracy(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "agents").mkdir(parents=True)
    logs = [
        {"timestamp": 1.0, "accuracy": 1.0, "duration": 2.0, "success": True},
        {"timestamp": 2.0, "accuracy": 0.0, "duration": 4.0, "success": False},
    ]
    (tmp_path / "data" / "agents" / "research_logs.json").write_text(json.dumps(logs), encoding="utf-8")
    cfg = AgentAutoConfigurator()
    out = _run(cfg.analyze_agent_performance("research"))
    assert out["accuracy"] == 0.5
    assert out["total_runs"] == 2


def test_detect_weaknesses_reports_skipped(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    cfg = AgentAutoConfigurator()
    out = _run(cfg.detect_weaknesses())
    assert "skipped_no_data" in out
    assert "agents_measured" in out
    assert out["agents_measured"] == 0
    assert set(out["skipped_no_data"]) == set(module.AGENT_NAMES)


def test_to_dict_emits_no_zero_for_unmeasured():
    from backend.agents.agent_autoconfigurator import AgentMetrics
    m = AgentMetrics(name="x")
    d = m.to_dict()
    for k in ("accuracy", "speed_seconds", "errors", "total_runs"):
        assert d[k] is None, f"{k} emite {d[k]!r} sin haber sido medido"
    assert not hasattr(module, "_generate_mock_logs")
