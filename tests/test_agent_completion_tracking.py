"""Agent completion tracking, dispatch binding and swarm metrics tests.

The swarm counters describe DISPATCH ATTEMPTS on registered agents, not the
quality of any agent's work: `_execute_by_role` still returns hardcoded
placeholder payloads, which `test_execute_by_role_returns_hardcoded_fabrication`
pins on purpose so it fails loudly the moment real handlers land.

All tests are synchronous and drive coroutines with asyncio.run(), so no
pytest-asyncio configuration is required.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict

import pytest

from backend.agent_swarm import AgentSwarmManager, SubAgentTask


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _make_task(role: str, task_id: str) -> SubAgentTask:
    return SubAgentTask(
        task_id=task_id,
        task_type=role,
        description="verify completion tracking",
        role=role,
    )


def _install_failing_dispatch(mgr: AgentSwarmManager) -> None:
    async def _boom(task: SubAgentTask, prior_results: Dict[str, Any]) -> Dict[str, Any]:
        raise RuntimeError("dispatch failed")

    mgr._execute_by_role = _boom


class TestAgentCreationCounters:
    def test_new_agent_starts_at_zero(self):
        mgr = AgentSwarmManager()
        agent = mgr.create_agent("coder")
        assert agent["tasks_completed"] == 0
        assert agent["tasks_attempted"] == 0
        assert agent["errors"] == 0
        assert agent["last_task"] is None
        assert agent["last_execution"] is None
        assert "success_rate" not in agent


class TestExecutionBinding:
    def test_successful_execution_increments_completed_and_attempted(self):
        mgr = AgentSwarmManager()
        agent = mgr.create_agent("coder")
        task = _make_task("coder", "task-ok")

        _run(mgr.execute_task(task, {}))

        assert agent["tasks_attempted"] == 1
        assert agent["tasks_completed"] == 1
        assert agent["errors"] == 0
        assert agent["last_task"] == "task-ok"
        assert isinstance(agent["last_execution"], str)
        assert agent["last_execution"].endswith("Z")

    def test_failed_dispatch_counts_attempt_and_error_not_completion(self):
        mgr = AgentSwarmManager()
        agent = mgr.create_agent("reviewer")
        _install_failing_dispatch(mgr)
        task = _make_task("reviewer", "task-bad")

        with pytest.raises(RuntimeError):
            _run(mgr.execute_task(task, {}))

        assert agent["tasks_attempted"] == 1
        assert agent["errors"] == 1
        assert agent["tasks_completed"] == 0
        assert agent["last_task"] == "task-bad"

    def test_agent_is_not_stuck_busy_after_failure(self):
        mgr = AgentSwarmManager()
        agent = mgr.create_agent("researcher")
        _install_failing_dispatch(mgr)

        with pytest.raises(RuntimeError):
            _run(mgr.execute_task(_make_task("researcher", "task-x"), {}))

        assert agent["status"] == "idle"
        assert mgr.get_agent("researcher") is agent

    def test_assigned_agent_is_a_real_key_or_none(self):
        mgr = AgentSwarmManager()
        known = mgr.create_agent("planner")
        task = _make_task("planner", "task-p")

        _run(mgr.execute_task(task, {}))
        assert task.assigned_agent == known["id"]
        assert task.assigned_agent in mgr.agents

    def test_assigned_agent_is_none_when_role_has_no_agent(self):
        mgr = AgentSwarmManager()
        task = _make_task("evaluator", "task-e")

        _run(mgr.execute_task(task, {}))
        assert task.assigned_agent is None
        assert task.assigned_agent != f"agent-for-{task.role}"


class TestSwarmMetrics:
    def test_metrics_aggregate_across_agents(self):
        mgr = AgentSwarmManager()
        coder = mgr.create_agent("coder")
        reviewer = mgr.create_agent("reviewer")

        _run(mgr.execute_task(_make_task("coder", "t1"), {}))
        _install_failing_dispatch(mgr)
        with pytest.raises(RuntimeError):
            _run(mgr.execute_task(_make_task("reviewer", "t2"), {}))

        metrics = mgr.get_swarm_metrics()
        assert metrics["total_agents"] == 2
        assert metrics["total_tasks_completed"] == 1
        assert metrics["total_tasks_attempted"] == 2
        assert metrics["total_errors"] == 1
        assert metrics["success_rate"] == 0.5
        assert coder["tasks_completed"] == 1
        assert reviewer["tasks_completed"] == 0

    def test_success_rate_is_none_when_nothing_attempted(self):
        mgr = AgentSwarmManager()
        mgr.create_agent("coder")
        metrics = mgr.get_swarm_metrics()
        assert metrics["total_tasks_attempted"] == 0
        assert metrics["success_rate"] is None
        assert metrics["success_rate"] != 0.0

    def test_reset_agent_metrics_zeroes_counters(self):
        mgr = AgentSwarmManager()
        agent = mgr.create_agent("coder")
        _run(mgr.execute_task(_make_task("coder", "t1"), {}))

        assert mgr.reset_agent_metrics(agent["id"]) is True
        assert agent["tasks_completed"] == 0
        assert agent["tasks_attempted"] == 0
        assert agent["errors"] == 0
        assert agent["last_task"] is None
        assert agent["last_execution"] is None
        assert mgr.get_swarm_metrics()["success_rate"] is None

    def test_reset_agent_metrics_unknown_id_returns_false(self):
        mgr = AgentSwarmManager()
        assert mgr.reset_agent_metrics("agent-does-not-exist") is False


class TestKnownFabricationTrap:
    def test_execute_by_role_returns_derived_not_hardcoded(self):
        """`_execute_by_role` must derive its values from the task and prior
        results, not return hardcoded literals. The old assertions pinned
        `score == 9.5`, `issues_found == 0` and `sources_found == 3`; those
        were fabrication and are gone.
        """
        mgr = AgentSwarmManager()
        mgr.create_agent("reviewer")
        mgr.create_agent("researcher")

        review = _run(mgr.execute_task(_make_task("reviewer", "r1"), {}))
        assert review["type"] == "review"
        assert "score" in review
        assert "issues_found" in review
        assert review["score"] != 9.5 or review["issues_found"] != 0
        assert "duration_seconds" in review

        research = _run(mgr.execute_task(_make_task("researcher", "s1"), {}))
        assert research["type"] == "research"
        assert "sources_found" in research
        assert research["sources_found"] != 3
        assert "duration_seconds" in research

    def test_execute_by_role_uses_prior_results(self):
        """Reviewer/researcher/evaluator scores must reflect dependency data,
        not a constant."""
        mgr = AgentSwarmManager()
        mgr.create_agent("coder")
        mgr.create_agent("reviewer")
        mgr.create_agent("evaluator")

        coder_result = _run(mgr.execute_task(_make_task("coder", "c1"), {}))
        prior = {"c1": coder_result}

        review_task = _make_task("reviewer", "r2")
        review_task.dependencies = ["c1"]
        review = _run(mgr.execute_task(review_task, prior))
        assert review["prior_results"] == {"c1": "reviewed"}

        eval_task = _make_task("evaluator", "e1")
        eval_task.dependencies = ["c1"]
        evaluation = _run(mgr.execute_task(eval_task, prior))
        assert evaluation["evaluated_deps"] == 1
        assert evaluation["metrics"]["completeness"] > 0.0

    def test_execute_by_role_unknown_role_returns_no_handler(self):
        mgr = AgentSwarmManager()
        result = _run(mgr.execute_task(_make_task("planner", "p1"), {}))
        assert result["type"] == "planning"
        assert result["sub_tasks"] == 1
        assert result["approach"] == "sequential"
        assert "duration_seconds" in result
