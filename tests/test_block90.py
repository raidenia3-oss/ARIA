"""BLOQUE 90 - unit tests for sovereign identity engine (local, ED25519)."""

import pytest

from backend.security.identity_engine import (
    SovereignIdentityEngine,
    get_identity_engine,
    reset_identity_engine,
)


def test_register_creates_keypair():
    reset_identity_engine()
    e = SovereignIdentityEngine()
    n = e.register(label="nodo-a", role="peer")
    assert n.node_id and n.pubkey_b64
    assert e.get(n.node_id) is not None
    reset_identity_engine()


def test_sign_and_verify_roundtrip():
    reset_identity_engine()
    e = SovereignIdentityEngine()
    n = e.register(label="nodo-a")
    sp = e.sign(n.node_id, {"msg": "hola", "x": 1})
    assert sp.signature_base64
    assert e.verify(sp) is True
    sp.payload["msg"] = "modificado"
    assert e.verify(sp) is False
    reset_identity_engine()


def test_unregistered_cannot_sign():
    reset_identity_engine()
    e = SovereignIdentityEngine()
    with pytest.raises(ValueError):
        e.sign("nope", {"a": 1})
    reset_identity_engine()


def test_verify_rejects_unknown_sender():
    reset_identity_engine()
    e = SovereignIdentityEngine()
    sp = {"sender": "ghost", "payload": {"a": 1}, "signature_base64": "x"}
    assert e.verify(sp) is False
    reset_identity_engine()


def test_issue_cert_and_list():
    reset_identity_engine()
    e = SovereignIdentityEngine()
    n = e.register(label="nodo-a")
    c = e.issue_cert(n.node_id, role="peer")
    assert c.subject_node == n.node_id
    assert len(e.list_certs()) == 1
    reset_identity_engine()


def test_ephemeral_issue_validate_revoke():
    reset_identity_engine()
    e = SovereignIdentityEngine()
    n = e.register(label="nodo-a")
    rec = e.issue_ephemeral(n.node_id, scope="swarm")
    assert e.validate_ephemeral(rec["token"], n.node_id, "swarm") is True
    assert e.validate_ephemeral("wrong", n.node_id, "swarm") is False
    assert e.revoke_ephemeral(n.node_id) is True
    assert e.validate_ephemeral(rec["token"], n.node_id, "swarm") is False
    reset_identity_engine()


def test_ephemeral_wrong_scope():
    reset_identity_engine()
    e = SovereignIdentityEngine()
    n = e.register(label="nodo-a")
    rec = e.issue_ephemeral(n.node_id, scope="swarm")
    assert e.validate_ephemeral(rec["token"], n.node_id, "other") is False
    reset_identity_engine()


def test_rotate_key():
    reset_identity_engine()
    e = SovereignIdentityEngine()
    n = e.register(label="nodo-a")
    old_b64 = n.pubkey_b64
    sp = e.sign(n.node_id, {"msg": "pre"})
    assert e.verify(sp) is True
    e.rotate(n.node_id)
    n2 = e.get(n.node_id)
    assert n2.pubkey_b64 != old_b64
    sp2 = e.sign(n.node_id, {"msg": "post"})
    assert e.verify(sp2) is True
    reset_identity_engine()


def test_singleton():
    reset_identity_engine()
    assert get_identity_engine() is get_identity_engine()
    reset_identity_engine()


def test_reset_clears_state():
    reset_identity_engine()
    e = get_identity_engine()
    e.register(label="nodo-a")
    assert e.status()["nodes"] >= 1
    e.reset()
    assert e.status()["nodes"] == 0
    reset_identity_engine()


def test_verify_bytes_helper():
    reset_identity_engine()
    e = SovereignIdentityEngine()
    n = e.register(label="nodo-a")
    import base64

    from backend.security.identity_engine import _load_private, _signing_payload

    priv = _load_private(n.node_id)
    data = _signing_payload({"hello": "world"})
    sig = base64.urlsafe_b64encode(priv.sign(data)).decode("ascii")
    assert e.verify_bytes(n.node_id, data, sig) is True
    assert e.verify_bytes(n.node_id, b"tampered", sig) is False
    reset_identity_engine()
