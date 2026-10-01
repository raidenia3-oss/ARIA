"""Tests for the APEX agent role definitions and swarm status wiring."""

from __future__ import annotations

import asyncio
from typing import Any, Dict

import pytest

from backend.agents.agent_roles import (
    APEXAgentRole,
    RoleSpec,
    get_all_roles,
    get_role_spec,
    role_to_dict,
)
from backend.agent_swarm import AgentSwarmManager


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


class TestRoleCatalogue:
    def test_twelve_roles_defined(self):
        roles = list(APEXAgentRole)
        assert len(roles) == 12

    def test_every_role_has_a_spec(self):
        for role in APEXAgentRole:
            spec = get_role_spec(role)
            assert isinstance(spec, RoleSpec)
            assert spec.role is role
            assert spec.name
            assert spec.color.startswith("#")
            assert spec.icon
            assert spec.description

    def test_get_all_roles_returns_twelve(self):
        assert len(get_all_roles()) == 12

    def test_role_to_dict_contains_capabilities(self):
        for role in APEXAgentRole:
            data = role_to_dict(role)
            assert data["role"] == role.value
            assert isinstance(data["capabilities"], list)
            assert len(data["capabilities"]) > 0

    def test_unknown_role_falls_back_to_architect(self):
        # from_string is defensive: a bogus role must not crash the registry
        assert APEXAgentRole.from_string("does-not-exist") is APEXAgentRole.ARCHITECT


class TestSwarmRoleIdentity:
    def test_create_agent_attaches_role_spec(self):
        mgr = AgentSwarmManager()
        agent = mgr.create_agent("security")
        spec = agent.get("role_spec")
        assert spec is not None
        assert spec["role"] == "security"
        assert spec["name"] == "Security"
        assert spec["color"] == "#8B008B"
        assert spec["icon"] == "🔒"

    def test_create_agent_unknown_role_gets_neutral_spec(self):
        mgr = AgentSwarmManager()
        agent = mgr.create_agent("planner")
        spec = agent.get("role_spec")
        assert spec is not None
        assert spec["role"] == "planner"
        assert spec["color"] == "#64748b"

    def test_get_agent_status_returns_snapshot(self):
        mgr = AgentSwarmManager()
        mgr.create_agent("architect")
        snapshot = mgr.get_agent_status("agent-0")
        assert snapshot is not None
        assert snapshot["role"] == "architect"
        assert snapshot["name"] == "Architect"
        assert snapshot["color"] == "#FFD700"
        assert snapshot["status"] == "idle"
        assert snapshot["tasks_completed"] == 0
        assert snapshot["error_count"] == 0
        assert "uptime_seconds" in snapshot

    def test_get_agent_status_unknown_id_returns_none(self):
        mgr = AgentSwarmManager()
        assert mgr.get_agent_status("agent-does-not-exist") is None

    def test_list_agent_status_returns_all(self):
        mgr = AgentSwarmManager()
        mgr.create_agent("architect")
        mgr.create_agent("devops")
        snapshots = mgr.list_agent_status()
        assert len(snapshots) == 2
        roles = {s["role"] for s in snapshots}
        assert roles == {"architect", "devops"}

    def test_touch_agent_refreshes_heartbeat(self):
        mgr = AgentSwarmManager()
        agent = mgr.create_agent("coder")
        original = agent["last_heartbeat"]
        import time
        time.sleep(0.01)
        assert mgr.touch_agent("agent-0") is True
        assert mgr.agents["agent-0"]["last_heartbeat"] != original

    def test_touch_agent_unknown_id_returns_false(self):
        mgr = AgentSwarmManager()
        assert mgr.touch_agent("agent-ghost") is False

    def test_busy_status_reflected_in_snapshot(self):
        mgr = AgentSwarmManager()
        mgr.create_agent("reviewer")
        # Claim the agent to flip it to busy
        claimed = mgr._claim_agent("reviewer")
        assert claimed is not None
        snapshot = mgr.get_agent_status(claimed["id"])
        assert snapshot is not None
        assert snapshot["status"] == "busy"

    def test_execution_increments_counters_and_status(self):
        mgr = AgentSwarmManager()
        mgr.create_agent("coder")
        from backend.agent_swarm import SubAgentTask
        task = SubAgentTask(
            task_id="t1",
            task_type="coder",
            description="verify dashboard feed",
            role="coder",
        )
        _run(mgr.execute_task(task, {}))
        snapshot = mgr.get_agent_status("agent-0")
        assert snapshot is not None
        assert snapshot["tasks_completed"] == 1
        assert snapshot["tasks_attempted"] == 1
        assert snapshot["status"] == "idle"

    def test_list_agent_status_includes_role_spec_color(self):
        mgr = AgentSwarmManager()
        mgr.create_agent("incident")
        snapshot = mgr.list_agent_status()[0]
        assert snapshot["color"] == "#FF4500"
        assert snapshot["icon"] == "🚨"