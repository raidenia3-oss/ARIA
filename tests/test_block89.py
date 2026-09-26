"""BLOQUE 89 - unit tests for swarm consensus + negotiation (local)."""

import pytest

from backend.mesh_consensus import (
    get_consensus_engine,
    reset_consensus_engine,
)


def test_open_rejects_empty():
    reset_consensus_engine()
    e = get_consensus_engine()
    with pytest.raises(ValueError):
        e.open_round("", "p", ["a"])
    with pytest.raises(ValueError):
        e.open_round("t", "p", [])
    reset_consensus_engine()


def test_quorum_accepts_majority():
    reset_consensus_engine()
    e = get_consensus_engine()
    rnd = e.open_round("mision", "desplegar", ["a", "b", "c"])
    e.vote(rnd.round_id, "a", "yes")
    out = e.vote(rnd.round_id, "b", "yes")
    assert out["status"] == "decided" and out["result"] == "accepted"
    reset_consensus_engine()


def test_rejects_non_voter_and_bad_choice():
    reset_consensus_engine()
    e = get_consensus_engine()
    rnd = e.open_round("t", "p", ["a"])
    assert e.vote(rnd.round_id, "zzz", "yes")["voted"] is False
    assert e.vote(rnd.round_id, "a", "maybe")["voted"] is False
    assert e.vote("nope", "a", "yes")["voted"] is False
    reset_consensus_engine()


def test_task_auction_highest_capacity_wins():
    reset_consensus_engine()
    e = get_consensus_engine()
    t = e.publish_task("subtarea-1", {"x": 1})
    e.bid(t["task_id"], "nodo-a", 0.3)
    out = e.bid(t["task_id"], "nodo-b", 0.9)
    assert out["assignee"] == "nodo-b"
    reset_consensus_engine()


def test_publish_rejects_empty():
    reset_consensus_engine()
    e = get_consensus_engine()
    with pytest.raises(ValueError):
        e.publish_task("  ")
    reset_consensus_engine()


def test_singleton():
    reset_consensus_engine()
    assert get_consensus_engine() is get_consensus_engine()
    reset_consensus_engine()
