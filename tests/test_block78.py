"""BLOQUE 78 - Local Decentralized P2P Mesh unit tests."""

from __future__ import annotations

import pytest

from backend.network.mesh import (
    MeshNode,
    MeshOrchestrator,
    MeshPacket,
    P2PMeshEngine,
    SwarmStateSnapshot,
    get_mesh_orchestrator,
    reset_mesh_orchestrator,
)


def test_mesh_packet_roundtrip():
    key = b"0" * 32
    payload = b"hello mesh"
    enc = MeshPacket.encode(payload, key, "alpha", "beta", msg_type="sync", seq=7)
    assert enc.startswith(b"AURAMESH")
    pkt = MeshPacket.decode(enc, key)
    assert pkt is not None
    assert pkt.src_node_id == "alpha"
    assert pkt.dst_node_id == "beta"
    assert pkt.msg_type == "sync"
    assert pkt.seq == 7
    assert pkt.payload == payload


def test_mesh_packet_tampered():
    key = b"1" * 32
    enc = MeshPacket.encode(b"x", key, "a", "b")
    bad = bytearray(enc)
    bad[-1] ^= 0xFF
    assert MeshPacket.decode(bytes(bad), key) is None


def test_mesh_packet_wrong_key():
    k1 = b"2" * 32
    k2 = b"3" * 32
    enc = MeshPacket.encode(b"x", k1, "a", "b")
    assert MeshPacket.decode(enc, k2) is None


def test_swarm_snapshot_merge():
    a = SwarmStateSnapshot(
        node_id="a",
        version=1,
        knowledge={"k": 1},
        tasks=[{"id": "t1", "v": 1}],
        directives=[{"id": "d1"}],
    )
    b = SwarmStateSnapshot(
        node_id="b",
        version=2,
        knowledge={"k2": 2},
        tasks=[{"id": "t2", "v": 2}],
        directives=[{"id": "d2"}],
    )
    m = a.merge(b)
    assert m.knowledge == {"k": 1, "k2": 2}
    ids = {t["id"] for t in m.tasks}
    assert ids == {"t1", "t2"}
    ids = {d["id"] for d in m.directives}
    assert ids == {"d1", "d2"}
    assert m.version == 3


def test_swarm_snapshot_json_roundtrip():
    s = SwarmStateSnapshot(node_id="x", version=3, knowledge={"a": 1})
    raw = s.to_json()
    s2 = SwarmStateSnapshot.from_json(raw)
    assert s2 is not None
    assert s2.node_id == "x"
    assert s2.version == 3
    assert s2.knowledge == {"a": 1}


def test_engine_encode_decode():
    e = P2PMeshEngine(node_id="n1", shared_secret="shared")
    enc = e.send_packet(b"payload", dst="n2", msg_type="hello")
    pkt = e.decode_packet(enc)
    assert pkt is not None
    assert pkt.src_node_id == "n1"
    assert pkt.dst_node_id == "n2"
    assert pkt.payload == b"payload"
    assert e.packets_sent == 1
    assert e.packets_received == 1


def test_engine_receive_bad():
    e = P2PMeshEngine(node_id="n1", shared_secret="s")
    assert e.decode_packet(b"garbage") is None
    assert e.packets_received == 0


def test_engine_state_update_and_sync():
    a = P2PMeshEngine(node_id="a", shared_secret="s")
    b = P2PMeshEngine(node_id="b", shared_secret="s")
    a.update_state(knowledge={"x": 1}, tasks=[{"id": "t1"}])
    b.update_state(knowledge={"y": 2}, tasks=[{"id": "t2"}])
    merged = a.sync_with(b)
    assert merged.knowledge == {"x": 1, "y": 2}
    assert {t["id"] for t in merged.tasks} == {"t1", "t2"}
    assert a.sync_rounds == 1


def test_orchestrator_add_remove_node():
    orch = MeshOrchestrator()
    n = MeshNode(node_id="node-1", host="127.0.0.1", port=48178)
    orch.add_node(n)
    assert orch.get_node("node-1") is not None
    assert len(orch.list_nodes()) == 1
    assert orch.remove_node("node-1") is True
    assert orch.get_node("node-1") is None
    assert orch.remove_node("node-1") is False


def test_orchestrator_discover():
    orch = MeshOrchestrator()
    added = orch.discover(
        [
            MeshNode(node_id="a"),
            MeshNode(node_id="b"),
            MeshNode(node_id="a"),  # dup
        ]
    )
    assert added == 2
    assert len(orch.list_nodes()) == 2


def test_singleton_reset():
    a = get_mesh_orchestrator()
    b = get_mesh_orchestrator()
    assert a is b
    reset_mesh_orchestrator()
    c = get_mesh_orchestrator()
    assert c is not a


def test_engine_status():
    e = P2PMeshEngine(node_id="s", shared_secret="k")
    e.register_peer(MeshNode(node_id="p1"))
    st = e.status()
    assert st["node_id"] == "s"
    assert st["peers"] == 1
    assert st["discovered"] == 1
