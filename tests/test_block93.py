"""BLOQUE 93 - unit tests for swarm role specialization & skill marketplace (local)."""

import pytest

from backend.swarm.models import RoleType
from backend.swarm.specialization import (
    DynamicSkillMarketplace,
    LocalSwarmRoleRegistry,
    RoleSpecializationEngine,
    get_swarm_engine,
    reset_swarm_engine,
)


def test_register_and_find_by_role():
    r = LocalSwarmRoleRegistry()
    r.register("node_a", roles=["analyst"], skills=["code"])
    items = r.find_by_role("analyst")
    assert len(items) == 1 and items[0].node_id == "node_a"


def test_marketplace_publish_and_discover():
    m = DynamicSkillMarketplace()
    s = m.publish("CodeScan", "security", "scans code", owner="local")
    assert s.skill_id and s.signature
    found = m.discover(category="security")
    assert len(found) == 1 and found[0].name == "CodeScan"
    dl = m.download(s.skill_id)
    assert dl.downloads == 1


def test_assign_role_requires_capability():
    reset_swarm_engine()
    e = RoleSpecializationEngine()
    e.registry.register("n1", roles=["analyst"])
    a = e.assign_role("t1", "n1", "analyst")
    assert a is not None and a.role == "analyst"
    assert e.assign_role("t2", "n1", "auditor") is None
    reset_swarm_engine()


def test_status_counts():
    reset_swarm_engine()
    e = get_swarm_engine()
    e.registry.register("n1", roles=["analyst"])
    e.marketplace.publish("S", "code")
    s = e.status()
    assert s["nodes"] >= 1 and s["skills"] >= 1
    reset_swarm_engine()


def test_singleton():
    reset_swarm_engine()
    assert get_swarm_engine() is get_swarm_engine()
    reset_swarm_engine()


def test_reset_clears():
    reset_swarm_engine()
    e = get_swarm_engine()
    e.registry.register("n1", roles=["analyst"])
    assert e.status()["nodes"] >= 1
    reset_swarm_engine()
    assert get_swarm_engine().status()["nodes"] == 0
