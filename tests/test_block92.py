"""BLOQUE 92 - unit tests for hierarchical goal planner (local)."""

import pytest

from backend.planner.hierarchical import HierarchicalGoalDecomposer, get_planner, reset_planner
from backend.planner.models import GoalStatus, MilestoneStatus


def test_decompose_creates_goal():
    reset_planner()
    e = HierarchicalGoalDecomposer()
    g = e.decompose("Test goal", "desc")
    assert g.goal_id and g.title == "Test goal"
    reset_planner()


def test_decompose_with_milestones():
    reset_planner()
    e = HierarchicalGoalDecomposer()
    g = e.decompose("G", milestones=[{"title": "M1"}, {"title": "M2"}])
    assert len(g.milestones) == 2
    assert g.milestones[0].goal_id == g.goal_id
    reset_planner()


def test_update_milestone_progress():
    reset_planner()
    e = HierarchicalGoalDecomposer()
    g = e.decompose("G", milestones=[{"title": "M1"}])
    m = e.update_milestone(g.goal_id, g.milestones[0].milestone_id, progress=50.0)
    assert m.progress == 50.0
    reset_planner()


def test_update_milestone_done_marks_goal():
    reset_planner()
    e = HierarchicalGoalDecomposer()
    g = e.decompose("G", milestones=[{"title": "M1"}])
    e.update_milestone(g.goal_id, g.milestones[0].milestone_id, status=MilestoneStatus.DONE)
    assert e.get_goal(g.goal_id).status == GoalStatus.DONE
    reset_planner()


def test_replan_returns_status():
    reset_planner()
    e = HierarchicalGoalDecomposer()
    g = e.decompose("G")
    r = e.replan(g.goal_id, "context_change")
    assert r["replanned"] is True
    reset_planner()


def test_cycle_detection():
    reset_planner()
    e = HierarchicalGoalDecomposer()
    a = e.decompose("A")
    b = e.decompose("B", parent_id=a.goal_id)
    assert e.check_cycles(b.goal_id, a.goal_id) is True
    assert e.check_cycles(a.goal_id, b.goal_id) is False
    reset_planner()


def test_singleton():
    reset_planner()
    assert get_planner() is get_planner()
    reset_planner()


def test_reset_clears():
    reset_planner()
    e = get_planner()
    e.decompose("G")
    assert e.status()["goals_total"] >= 1
    reset_planner()
    assert get_planner().status()["goals_total"] == 0
