"""BLOQUE 95 - unit tests for cross-device sync & daemon orchestration."""

import os

import pytest

from backend.daemon.cross_device import (
    CrossDeviceSynchronizer,
    DaemonSyncEngine,
    ResilientDaemonController,
    get_sync_engine,
    reset_sync_engine,
)


@pytest.fixture(autouse=True)
def _clean_state():
    """Limpia estado persistente antes de cada test."""
    for f in ["data/daemon_sync/peers.json", "data/daemon_sync/sync_log.json"]:
        if os.path.exists(f):
            os.remove(f)
    reset_sync_engine()
    yield
    reset_sync_engine()


def test_register_and_list_peers():
    s = CrossDeviceSynchronizer(local_node_id="test_node")
    s.register_peer("peer_a", "Node A", "192.168.1.10", capabilities=["code", "rag"])
    peers = s.list_peers()
    assert len(peers) == 1
    assert peers[0].node_id == "peer_a"


def test_create_snapshot():
    s = CrossDeviceSynchronizer(local_node_id="test_node")
    snap = s.create_snapshot({"memory": 42, "state": "active"})
    assert snap.snapshot_id.startswith("snap_")
    assert snap.state_data["memory"] == 42


def test_compute_delta():
    s = CrossDeviceSynchronizer(local_node_id="test_node")
    delta = s.compute_delta({"a": 1, "b": 2}, {"a": 1, "b": 3, "c": 4})
    assert "b" in delta
    assert "c" in delta
    assert "a" not in delta


def test_merge_states_with_conflicts():
    s = CrossDeviceSynchronizer(local_node_id="test_node")
    merged, conflicts = s.merge_states({"x": 1, "y": 2}, {"y": 3, "z": 4}, "remote")
    assert merged["y"] == 3
    assert "y" in conflicts
    assert merged["z"] == 4


def test_daemon_start_stop():
    d = ResilientDaemonController()
    assert d.start() is True
    assert d.is_running() is True
    assert d.stop() is True
    assert d.is_running() is False


def test_daemon_restart_resilience():
    d = ResilientDaemonController(max_restarts=3)
    d.start()
    result = d.simulate_interruption()
    assert result["recovered"] is True
    assert d.is_running() is True


def test_daemon_max_restarts():
    d = ResilientDaemonController(max_restarts=2)
    d.start()
    d.simulate_interruption()
    d.simulate_interruption()
    result = d.simulate_interruption()
    assert result["recovered"] is False


def test_engine_integrated():
    e = get_sync_engine()
    e.start_daemon()
    e.synchronizer.register_peer("p1_integ", "Peer1")
    snap = e.synchronizer.create_snapshot({"k": "v"})
    result = e.synchronizer.sync_with_peer("p1_integ", {"k": "v"})
    assert result["sync"] is True
    status = e.get_status()
    assert status["sync"]["peers_count"] == 1


def test_singleton():
    a = get_sync_engine()
    b = get_sync_engine()
    assert a is b
