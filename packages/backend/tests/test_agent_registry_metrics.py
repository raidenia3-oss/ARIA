"""Tests for request_count tracking in AgentRegistryV2.

The counter was previously hardcoded to 0 at registration time and never
incremented, so /api/agents/status always showed 0 requests for every agent.
These tests cover the increment path, persistence, per-agent isolation and
the dispatcher wiring in PluginManager.
"""

import tempfile

import pytest

from backend.core.agent_registry_v2 import AgentRegistryV2


@pytest.fixture
def registry():
    with tempfile.TemporaryDirectory() as tmp:
        reg = AgentRegistryV2(storage_dir=tmp)
        reg.register_agent({"name": "summarizer", "type": "plugin", "commands": ["summarize"]})
        reg.register_agent({"name": "qa", "type": "plugin", "commands": ["ask"]})
        yield reg


def test_request_count_starts_at_zero(registry):
    agents = registry.list_agents()
    assert all(a["request_count"] == 0 for a in agents)


def test_request_count_increments(registry):
    agent_id = registry.list_agents()[0]["agent_id"]
    assert registry.increment_request_count(agent_id) == 1
    assert registry.increment_request_count(agent_id) == 2
    assert registry.get_agent_metrics(agent_id)["request_count"] == 2


def test_request_count_persists_in_agent_entry(registry):
    agent_id = registry.list_agents()[0]["agent_id"]
    registry.increment_request_count(agent_id)
    registry.increment_request_count(agent_id)
    assert registry._agents[agent_id]["request_count"] == 2


def test_different_agents_have_separate_counters(registry):
    a1 = registry.list_agents()[0]["agent_id"]
    a2 = registry.list_agents()[1]["agent_id"]
    registry.increment_request_count(a1)
    registry.increment_request_count(a1)
    registry.increment_request_count(a2)
    assert registry.get_agent_metrics(a1)["request_count"] == 2
    assert registry.get_agent_metrics(a2)["request_count"] == 1


def test_get_all_metrics(registry):
    agents = registry.list_agents()
    registry.increment_request_count(agents[0]["agent_id"])
    registry.increment_request_count(agents[1]["agent_id"])
    registry.increment_request_count(agents[1]["agent_id"])
    all_metrics = registry.get_all_metrics()
    assert all_metrics[agents[0]["agent_id"]]["request_count"] == 1
    assert all_metrics[agents[1]["agent_id"]]["request_count"] == 2


def test_increment_nonexistent_agent_is_noop(registry):
    # Must not raise; returns 0 for unknown agents.
    assert registry.increment_request_count("agent-does-not-exist") == 0
    assert registry.get_agent_metrics("agent-does-not-exist") is None


def test_last_request_time_updated(registry):
    agent_id = registry.list_agents()[0]["agent_id"]
    assert registry.get_agent_metrics(agent_id)["last_request_time"] is None
    registry.increment_request_count(agent_id)
    assert registry.get_agent_metrics(agent_id)["last_request_time"] is not None


def test_get_agent_metrics_unknown_returns_none(registry):
    assert registry.get_agent_metrics("agent-ghost") is None


def test_get_agent_metrics_fields(registry):
    agent_id = registry.list_agents()[0]["agent_id"]
    registry.increment_request_count(agent_id)
    m = registry.get_agent_metrics(agent_id)
    for key in ("agent_id", "name", "type", "status", "request_count",
                "last_request_time", "revenue", "created_at"):
        assert key in m


def test_plugin_manager_bumps_counter_on_hook(monkeypatch):
    """execute_hook should call _bump_request_count for tagged plugins."""
    from backend.plugins.plugin_manager import PluginManager

    with tempfile.TemporaryDirectory() as tmp:
        pm = PluginManager(plugins_dir=tmp)
        bumps = []

        def fake_bump(plugin_name):
            bumps.append(plugin_name)

        monkeypatch.setattr(pm, "_bump_request_count", fake_bump)

        calls = []

        def hook(*args, **kwargs):
            calls.append(1)
            return "ok"

        hook.__plugin__ = "fake-plugin"
        pm.hooks["on_test"] = [hook]

        pm.execute_hook("on_test")
        pm.execute_hook("on_test")

        assert len(calls) == 2
        assert bumps == ["fake-plugin", "fake-plugin"]


def test_plugin_manager_async_hook_bumps_counter(monkeypatch):
    """execute_hook_async should also call _bump_request_count."""
    import asyncio
    from backend.plugins.plugin_manager import PluginManager

    with tempfile.TemporaryDirectory() as tmp:
        pm = PluginManager(plugins_dir=tmp)
        bumps = []

        def fake_bump(plugin_name):
            bumps.append(plugin_name)

        monkeypatch.setattr(pm, "_bump_request_count", fake_bump)

        async def hook(*args, **kwargs):
            return "ok"

        hook.__plugin__ = "fake-plugin"
        pm.hooks["on_test"] = [hook]

        asyncio.get_event_loop().run_until_complete(
            pm.execute_hook_async("on_test")
        )

        assert bumps == ["fake-plugin"]