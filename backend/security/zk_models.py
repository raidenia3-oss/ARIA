"""BLOQUE 94 - Data models for local Zero-Knowledge Proof verification.

Implements the data structures used by the ZKP verifier and the sovereign
immutable audit trail.  All objects are plain dataclasses so they can be
serialized to JSON for REST/WebSocket transport without any external
dependency.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Zero-Knowledge Proof models
# ---------------------------------------------------------------------------

@dataclass
class ZKProof:
    """A Schnorr-style non-interactive zero-knowledge proof (Fiat-Shamir).

    The proof certifies that the prover knows a secret ``witness`` such that
    ``g**witness == commitment`` modulo the group prime ``p``.  The witness
    itself never leaves the prover.
    """

    proof_id: str = ""
    statement: str = ""          # human-readable claim, e.g. "has_role:admin"
    commitment_b64: str = ""     # g**witness mod p (public commitment)
    nonce_b64: str = ""          # g**random mod p (ephemeral, Fiat-Shamir)
    challenge_b64: str = ""      # Fiat-Shamir derived challenge
    response_b64: str = ""       # random + challenge*witness mod q
    group_id: str = ""           # identifier of the prime group used
    created_at: float = 0.0
    verified: bool = False
    verifier_node: str = ""
    offline_only: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "statement": self.statement,
            "commitment_b64": self.commitment_b64,
            "nonce_b64": self.nonce_b64,
            "challenge_b64": self.challenge_b64,
            "response_b64": self.response_b64,
            "group_id": self.group_id,
            "created_at": self.created_at,
            "verified": self.verified,
            "verifier_node": self.verifier_node,
            "offline_only": self.offline_only,
        }


@dataclass
class ZKGroup:
    """A discrete-logarithm group used for ZK proofs (safe prime)."""

    group_id: str = ""
    p_b64: str = ""
    q_b64: str = ""
    g_b64: str = ""
    bits: int = 0
    created_at: float = 0.0
    offline_only: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_id": self.group_id,
            "p_b64": self.p_b64,
            "q_b64": self.q_b64,
            "g_b64": self.g_b64,
            "bits": self.bits,
            "created_at": self.created_at,
            "offline_only": self.offline_only,
        }


# ---------------------------------------------------------------------------
# Sovereign immutable audit trail models
# ---------------------------------------------------------------------------

@dataclass
class AuditEntry:
    """A single immutable, hashed, chained audit record."""

    entry_id: str = ""
    sequence: int = 0
    timestamp: float = 0.0
    event_type: str = ""           # e.g. "zk_proof_issued", "zk_proof_verified"
    actor: str = ""                # node id or "local"
    target: str = ""
    detail: Dict[str, Any] = field(default_factory=dict)
    prev_hash: str = ""            # SHA-256 of the previous entry
    entry_hash: str = ""           # SHA-256 of this entry (includes prev_hash)
    signature_b64: str = ""        # optional ED25519 signature of the hash
    offline_only: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "actor": self.actor,
            "target": self.target,
            "detail": self.detail,
            "prev_hash": self.prev_hash,
            "entry_hash": self.entry_hash,
            "signature_b64": self.signature_b64,
            "offline_only": self.offline_only,
        }


@dataclass
class AuditChainState:
    """Compact summary of the audit chain integrity."""

    total_entries: int = 0
    last_sequence: int = 0
    last_hash: str = ""
    root_hash: str = ""
    verified: bool = False
    tampered: bool = False
    offline_only: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_entries": self.total_entries,
            "last_sequence": self.last_sequence,
            "last_hash": self.last_hash,
            "root_hash": self.root_hash,
            "verified": self.verified,
            "tampered": self.tampered,
            "offline_only": self.offline_only,
        }


# ---------------------------------------------------------------------------
# REST request/response envelopes
# ---------------------------------------------------------------------------

@dataclass
class ZKProofRequest:
    statement: str = ""
    witness: int = 0
    group_id: str = ""
    prover_node: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "statement": self.statement,
            "witness": self.witness,
            "group_id": self.group_id,
            "prover_node": self.prover_node,
        }


@dataclass
class ZKVerifyRequest:
    proof: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"proof": self.proof}


@dataclass
class AuditQueryRequest:
    event_type: str = ""
    actor: str = ""
    limit: int = 50
    offset: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "actor": self.actor,
            "limit": self.limit,
            "offset": self.offset,
        }