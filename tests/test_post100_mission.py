"""FASE POST-100 - tests for live autonomous mission (planner + P2P zero-trust + marketplace)."""

import pytest

from scripts.post100_mission import (
    AUDIT_TARGETS,
    mission_marketplace,
    mission_p2p_zero_trust,
    mission_stress,
    run_mission,
)


def test_p2p_zero_trust_signature():
    r = mission_p2p_zero_trust()
    assert r["signature_valid"] is True
    assert r["tamper_rejected"] is True
    assert r["local_node"] != r["remote_node"]


def test_stress_scenario_completes():
    r = mission_stress()
    assert r["status"] == "completed"
    assert r["faults_injected"] == 2
    assert 0.0 <= r["consensus_accuracy"] <= 1.0
    assert r["resilience"] >= 0.0


def test_marketplace_skill_exchange():
    r = mission_marketplace()
    assert r["published_version"] == "1.0.0"
    assert r["search_hits"] >= 1
    assert r["versions"] >= 1


def test_full_mission_success():
    rep = run_mission()
    assert rep["verdict"] == "MISSION_SUCCESS"
    assert rep["runtime"]["total_blocks"] == 100
    assert rep["mission_plan"]["findings"] > 0
    assert len(AUDIT_TARGETS) == 2
