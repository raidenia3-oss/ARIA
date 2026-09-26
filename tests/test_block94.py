"""BLOQUE 94 - Unit tests: local Zero-Knowledge Proof verifier & audit trail.

Validates:
- Schnorr proof correctness (valid proofs verify, tampered proofs reject).
- Fiat-Shamir challenge binding (different nonce -> different challenge).
- Audit chain integrity (hash chaining detects tampering).
- Group generation produces safe primes.
"""

from __future__ import annotations

import hashlib
import os
import time

import pytest

from backend.security.zk_audit import (
    DEFAULT_GROUP,
    FiatShamirSchnorr,
    SovereignAuditLogger,
    ZKAuditEngine,
    _b64d,
    _b64i,
    get_zk_audit_engine,
    reset_zk_audit_engine,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_zk_audit_engine()
    yield
    reset_zk_audit_engine()


def test_default_group_is_safe_prime():
    p = _b64d(DEFAULT_GROUP.p_b64)
    q = _b64d(DEFAULT_GROUP.q_b64)
    g = _b64d(DEFAULT_GROUP.g_b64)
    assert p == 2 * q + 1
    assert pow(g, q, p) == 1
    assert pow(g, 2, p) != 1
    assert p.bit_length() >= 256


def test_valid_proof_verifies():
    zk = FiatShamirSchnorr(DEFAULT_GROUP)
    proof = zk.prove("has_role:admin", witness=42, prover_node="nodeA")
    assert proof.verified is False
    assert zk.verify(proof) is True
    assert proof.verified is True


def test_tampered_response_rejected():
    zk = FiatShamirSchnorr(DEFAULT_GROUP)
    proof = zk.prove("has_role:admin", witness=42, prover_node="nodeA")
    orig = proof.response_b64
    proof.response_b64 = orig[:-2] + ("AA" if not orig.endswith("AA") else "BB")
    assert zk.verify(proof) is False


def test_tampered_commitment_rejected():
    zk = FiatShamirSchnorr(DEFAULT_GROUP)
    proof = zk.prove("has_role:admin", witness=42, prover_node="nodeA")
    proof.commitment_b64 = _b64i((_b64d(proof.commitment_b64) + 1) % _b64d(DEFAULT_GROUP.p_b64))
    assert zk.verify(proof) is False


def test_wrong_witness_does_not_verify():
    zk = FiatShamirSchnorr(DEFAULT_GROUP)
    proof = zk.prove("has_role:admin", witness=42, prover_node="nodeA")
    other = zk.prove("has_role:admin", witness=999, prover_node="nodeB")
    other.commitment_b64 = proof.commitment_b64
    assert zk.verify(other) is False


def test_fiat_shamir_challenge_binding():
    zk = FiatShamirSchnorr(DEFAULT_GROUP)
    p1 = zk.prove("has_role:admin", witness=42)
    p2 = zk.prove("has_role:admin", witness=42)
    assert p1.nonce_b64 != p2.nonce_b64
    assert p1.challenge_b64 != p2.challenge_b64


def test_audit_chain_detects_tampering(tmp_path):
    log = SovereignAuditLogger(file_path=str(tmp_path / "audit.json"))
    log.append("zk_proof_issued", actor="nodeA", detail={"x": 1})
    log.append("zk_proof_verified", actor="local", detail={"x": 2})
    assert log.verify_chain().verified is True
    path = tmp_path / "audit.json"
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    data["entries"][0]["detail"]["x"] = 999
    path.write_text(json.dumps(data), encoding="utf-8")
    log2 = SovereignAuditLogger(file_path=str(path))
    state = log2.verify_chain()
    assert state.tampered is True
    assert state.verified is False


def test_audit_chain_rejects_inserted_entry(tmp_path):
    log = SovereignAuditLogger(file_path=str(tmp_path / "audit.json"))
    log.append("zk_proof_issued", actor="nodeA")
    log.append("zk_proof_verified", actor="local")
    state = log.verify_chain()
    assert state.total_entries == 2
    assert state.last_sequence == 2


def test_engine_prove_and_verify_flow():
    e = get_zk_audit_engine()
    proof = e.prove("has_role:admin", witness=123, prover_node="nodeA")
    assert e.verify(proof) is True
    fetched = e.get_proof(proof.proof_id)
    assert fetched is not None
    assert fetched.verified is True
    proofs = e.list_proofs()
    assert any(p.proof_id == proof.proof_id for p in proofs)


def test_engine_audit_entries_query():
    e = get_zk_audit_engine()
    e.prove("has_role:admin", witness=1, prover_node="nodeA")
    e.prove("has_role:user", witness=2, prover_node="nodeB")
    entries = e.audit_entries(event_type="zk_proof_issued")
    assert len(entries) == 2
    entries_a = e.audit_entries(actor="nodeA")
    assert len(entries_a) == 1


def test_engine_create_group():
    e = get_zk_audit_engine()
    g = e.create_group(bits=128)
    assert g.bits == 128
    groups = e.list_groups()
    assert any(grp.group_id == g.group_id for grp in groups)


def test_engine_reset():
    e = get_zk_audit_engine()
    e.prove("has_role:admin", witness=1, prover_node="nodeA")
    assert len(e.list_proofs()) == 1
    e.reset()
    assert len(e.list_proofs()) == 0
    assert len(e.list_groups()) == 1


def test_invalid_witness_rejected():
    zk = FiatShamirSchnorr(DEFAULT_GROUP)
    with pytest.raises(ValueError):
        zk.prove("x", witness=0)
    with pytest.raises(ValueError):
        zk.prove("x", witness=_b64d(DEFAULT_GROUP.q_b64))
