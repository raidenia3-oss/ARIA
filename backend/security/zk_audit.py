"""BLOQUE 94 - Local Zero-Knowledge Proof Verifier & Sovereign Audit Trail.

Schnorr-style non-interactive zero-knowledge proof (Fiat-Shamir) over a
safe-prime group, using only the Python standard library plus the already
present ``cryptography`` package for optional ED25519 audit signatures.
Sovereign immutable hashed-chained audit logger writing to a local file.
All operation is 100% local and offline.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.security.zk_models import (
    AuditChainState,
    AuditEntry,
    ZKGroup,
    ZKProof,
)

AUDIT_FILE_ENV = "AURA_AUDIT_FILE"
DEFAULT_AUDIT_FILE = "backend/security_state/audit/zk_audit.json"
DEFAULT_GROUP_BITS = 256

_DEFAULT_P = 142245781911807048275874328736897291082980873754990293789126879187220897173563
_DEFAULT_Q = 71122890955903524137937164368448645541490436877495146894563439593610448586781
_DEFAULT_G = 4

def _int_b64(value: int) -> str:
    nbytes = (value.bit_length() + 7) // 8 or 1
    return base64.urlsafe_b64encode(value.to_bytes(nbytes, "big")).decode("ascii")


DEFAULT_GROUP = ZKGroup(
    group_id="aura-default-256",
    p_b64=_int_b64(_DEFAULT_P),
    q_b64=_int_b64(_DEFAULT_Q),
    g_b64=_int_b64(_DEFAULT_G),
    bits=DEFAULT_GROUP_BITS,
    created_at=0.0,
    offline_only=True,
)


def _b64i(value: int) -> str:
    if value < 0:
        raise ValueError("negative value")
    nbytes = (value.bit_length() + 7) // 8 or 1
    return base64.urlsafe_b64encode(value.to_bytes(nbytes, "big")).decode("ascii")


def _b64d(text: str) -> int:
    return int.from_bytes(base64.urlsafe_b64decode(text.encode("ascii")), "big")


def _mod_inv(a: int, m: int) -> int:
    if m <= 1:
        raise ValueError("modulus must be > 1")
    lm, hm = 1, 0
    low, high = a % m, m
    while low > 1:
        ratio = high // low
        nm = hm - lm * ratio
        new = high - low * ratio
        hm, lm = lm, nm
        high, low = low, new
    return lm % m


def _int_b64(value: int) -> str:
    nbytes = (value.bit_length() + 7) // 8 or 1
    return base64.urlsafe_b64encode(value.to_bytes(nbytes, "big")).decode("ascii")

class FiatShamirSchnorr:
    """Non-interactive Schnorr ZKP over a safe-prime group.

    Prover proves knowledge of ``witness`` such that ``g**witness == commitment``
    modulo ``p``.  The challenge is derived via Fiat-Shamir (hash of group +
    commitment + commitment**random), so no interactive rounds are needed.
    """

    def __init__(self, group: Optional[ZKGroup] = None) -> None:
        self.group = group or DEFAULT_GROUP
        self.p = _b64d(self.group.p_b64)
        self.q = _b64d(self.group.q_b64)
        self.g = _b64d(self.group.g_b64)
        # Sanity check: g must have order q (g**q == 1 mod p, g != 1).
        if pow(self.g, self.q, self.p) != 1 or self.g % self.p == 1:
            raise ValueError("invalid group: generator does not have order q")

    def _fs_challenge(self, commitment: int, nonce: int) -> int:
        """Fiat-Shamir challenge: hash(group||commitment||nonce)."""
        h = hashlib.sha256()
        h.update(self.group.group_id.encode("utf-8"))
        h.update(_b64i(commitment).encode("ascii"))
        h.update(_b64i(nonce).encode("ascii"))
        digest = h.digest()
        return int.from_bytes(digest, "big") % self.q

    def prove(self, statement: str, witness: int,
              prover_node: str = "local") -> ZKProof:
        """Create a ZK proof for ``statement`` using ``witness`` as the secret.

        Schnorr protocol: prover picks random ``r``, sends ``nonce = g**r``,
        receives challenge ``c``, responds ``s = r + c*witness``.  Verifier
        checks ``g**s == nonce * commitment**c``.
        """
        if witness <= 0 or witness >= self.q:
            raise ValueError("witness must be in [1, q-1]")
        random = secrets.randbelow(self.q - 1) + 1
        commitment = pow(self.g, witness, self.p)
        nonce = pow(self.g, random, self.p)
        challenge = self._fs_challenge(commitment, nonce)
        response = (random + challenge * witness) % self.q
        proof = ZKProof(
            proof_id=uuid.uuid4().hex[:12],
            statement=statement,
            commitment_b64=_b64i(commitment),
            nonce_b64=_b64i(nonce),
            challenge_b64=_b64i(challenge),
            response_b64=_b64i(response),
            group_id=self.group.group_id,
            created_at=time.time(),
            verified=False,
            verifier_node=prover_node,
            offline_only=True,
        )
        return proof

    def verify(self, proof: ZKProof) -> bool:
        """Verify a ZK proof without learning the witness."""
        try:
            commitment = _b64d(proof.commitment_b64)
            nonce = _b64d(proof.nonce_b64)
            challenge = _b64d(proof.challenge_b64)
            response = _b64d(proof.response_b64)
        except Exception:
            return False
        if not (1 <= commitment < self.p):
            return False
        if not (1 <= nonce < self.p):
            return False
        if not (0 <= challenge < self.q):
            return False
        if not (1 <= response < self.q):
            return False
        expected = self._fs_challenge(commitment, nonce)
        if expected != challenge:
            proof.verified = False
            return False
        lhs = pow(self.g, response, self.p)
        rhs = (nonce * pow(commitment, challenge, self.p)) % self.p
        ok = lhs == rhs
        proof.verified = ok
        return ok

class SovereignAuditLogger:
    """Immutable, hashed, chained audit logger writing to a local JSON file.

    Each entry stores the SHA-256 of the previous entry, so the chain forms a
    tamper-evident hash chain.  ``verify_chain()`` walks the chain and returns
    True only if every entry_hash matches the recomputed hash and the chain
    is internally consistent.
    """

    def __init__(self, file_path: Optional[str] = None,
                 sign_with_key: Optional[str] = None) -> None:
        self.file_path = Path(file_path or os.getenv(AUDIT_FILE_ENV, DEFAULT_AUDIT_FILE))
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._signing_key = sign_with_key  # optional PEM private key for ED25519
        self._lock = threading.RLock()
        self._entries: List[AuditEntry] = []
        self._watchers: List = []
        self._load()

    def on_event(self, cb) -> None:
        """Register a callback invoked (with the entry dict) on each append."""
        with self._lock:
            self._watchers.append(cb)

    def _emit(self, entry: AuditEntry) -> None:
        with self._lock:
            cbs = list(self._watchers)
        data = entry.to_dict()
        data["type"] = entry.event_type
        for cb in cbs:
            try:
                cb(data)
            except Exception:
                pass

    # -- persistence ----------------------------------------------------------

    def _load(self) -> None:
        if not self.file_path.exists():
            return
        try:
            data = json.loads(self.file_path.read_text(encoding="utf-8"))
            for raw in data.get("entries", []):
                try:
                    self._entries.append(AuditEntry(**raw))
                except Exception:
                    continue
        except Exception:
            self._entries = []

    def _save(self) -> None:
        payload = {"entries": [e.to_dict() for e in self._entries]}
        tmp = self.file_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.file_path)

    # -- chain helpers --------------------------------------------------------

    def _entry_hash(self, entry: AuditEntry) -> str:
        body = {
            "entry_id": entry.entry_id,
            "sequence": entry.sequence,
            "timestamp": entry.timestamp,
            "event_type": entry.event_type,
            "actor": entry.actor,
            "target": entry.target,
            "detail": entry.detail,
            "prev_hash": entry.prev_hash,
        }
        data = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(data).hexdigest()

    def _sign_hash(self, entry_hash: str) -> str:
        if not self._signing_key:
            return ""
        try:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric import ed25519
            priv = serialization.load_pem_private_key(
                self._signing_key.encode("utf-8"), password=None)
            sig = priv.sign(entry_hash.encode("utf-8"))
            return base64.urlsafe_b64encode(sig).decode("ascii")
        except Exception:
            return ""

    # -- public API -----------------------------------------------------------

    def append(self, event_type: str, actor: str = "local", target: str = "",
               detail: Optional[Dict[str, Any]] = None,
               signature_b64: Optional[str] = None) -> AuditEntry:
        with self._lock:
            sequence = (self._entries[-1].sequence + 1) if self._entries else 1
            prev_hash = self._entries[-1].entry_hash if self._entries else (
                hashlib.sha256(b"aura-audit-genesis").hexdigest())
            entry = AuditEntry(
                entry_id=uuid.uuid4().hex[:12],
                sequence=sequence,
                timestamp=time.time(),
                event_type=event_type,
                actor=actor,
                target=target,
                detail=detail or {},
                prev_hash=prev_hash,
                entry_hash="",
                signature_b64=signature_b64 or "",
                offline_only=True,
            )
            entry.entry_hash = self._entry_hash(entry)
            if not entry.signature_b64:
                entry.signature_b64 = self._sign_hash(entry.entry_hash)
            self._entries.append(entry)
            self._save()
            self._emit(entry)
            return entry

    def list_entries(self, event_type: str = "", actor: str = "",
                     limit: int = 50, offset: int = 0) -> List[AuditEntry]:
        with self._lock:
            items = list(self._entries)
        if event_type:
            items = [e for e in items if e.event_type == event_type]
        if actor:
            items = [e for e in items if e.actor == actor]
        return items[offset: offset + max(1, min(500, limit))]

    def verify_chain(self) -> AuditChainState:
        """Walk the chain and detect tampering."""
        with self._lock:
            entries = list(self._entries)
        if not entries:
            return AuditChainState(verified=True, offline_only=True)
        prev_hash = hashlib.sha256(b"aura-audit-genesis").hexdigest()
        ok = True
        for e in entries:
            if e.prev_hash != prev_hash:
                ok = False
                break
            if self._entry_hash(e) != e.entry_hash:
                ok = False
                break
            prev_hash = e.entry_hash
        last = entries[-1]
        return AuditChainState(
            total_entries=len(entries),
            last_sequence=last.sequence,
            last_hash=last.entry_hash,
            root_hash=entries[0].entry_hash,
            verified=ok,
            tampered=not ok,
            offline_only=True,
        )

    def status(self) -> Dict[str, Any]:
        with self._lock:
            state = self.verify_chain()
            return {
                "status": "ok",
                "file": str(self.file_path),
                "exists": self.file_path.exists(),
                "entries": len(self._entries),
                "verified": state.verified,
                "tampered": state.tampered,
                "last_sequence": state.last_sequence,
                "last_hash": state.last_hash,
                "offline_only": True,
            }

    def reset(self) -> None:
        with self._lock:
            self._entries = []
            if self.file_path.exists():
                try:
                    self.file_path.unlink()
                except Exception:
                    pass

class ZKAuditEngine:
    """Master engine: ZKP verifier + sovereign audit logger.

    Exposes:
    - create_group(bits) / list_groups()
    - prove(statement, witness, prover_node)
    - verify(proof)
    - audit.append/list/verify_chain/status/reset
    """

    def __init__(self, audit_file: Optional[str] = None,
                 signing_key: Optional[str] = None) -> None:
        self.zk = FiatShamirSchnorr(DEFAULT_GROUP)
        self.groups: Dict[str, ZKGroup] = {DEFAULT_GROUP.group_id: DEFAULT_GROUP}
        self.audit = SovereignAuditLogger(file_path=audit_file, sign_with_key=signing_key)
        self._lock = threading.RLock()
        self._proofs: Dict[str, ZKProof] = {}

    # -- groups ---------------------------------------------------------------

    def create_group(self, bits: int = DEFAULT_GROUP_BITS) -> ZKGroup:
        """Create a new safe-prime group for ZKP proofs."""
        if bits < 128:
            raise ValueError("bits must be >= 128")
        p, q, g = _generate_safe_prime(bits)
        group = ZKGroup(
            group_id=uuid.uuid4().hex[:12],
            p_b64=_b64i(p), q_b64=_b64i(q), g_b64=_b64i(g),
            bits=bits, created_at=time.time(), offline_only=True,
        )
        with self._lock:
            self.groups[group.group_id] = group
        self.audit.append("zk_group_created", actor="local",
                          detail={"group_id": group.group_id, "bits": bits})
        return group

    def list_groups(self) -> List[ZKGroup]:
        with self._lock:
            return list(self.groups.values())

    def get_group(self, group_id: str) -> Optional[ZKGroup]:
        with self._lock:
            return self.groups.get(group_id)

    # -- proofs ---------------------------------------------------------------

    def prove(self, statement: str, witness: int,
              group_id: str = "", prover_node: str = "local") -> ZKProof:
        group = self.groups.get(group_id) if group_id else DEFAULT_GROUP
        if group is None:
            raise ValueError(f"unknown group: {group_id}")
        zk = FiatShamirSchnorr(group)
        proof = zk.prove(statement, witness=witness, prover_node=prover_node)
        with self._lock:
            self._proofs[proof.proof_id] = proof
        self.audit.append("zk_proof_issued", actor=prover_node,
                          target=proof.proof_id,
                          detail={"statement": statement,
                                  "group_id": group.group_id})
        return proof

    def verify(self, proof: ZKProof) -> bool:
        group = self.groups.get(proof.group_id, DEFAULT_GROUP)
        zk = FiatShamirSchnorr(group)
        ok = zk.verify(proof)
        proof.verified = ok
        with self._lock:
            self._proofs[proof.proof_id] = proof
        self.audit.append("zk_proof_verified", actor="local",
                          target=proof.proof_id,
                          detail={"statement": proof.statement,
                                  "verified": ok})
        return ok

    def get_proof(self, proof_id: str) -> Optional[ZKProof]:
        with self._lock:
            return self._proofs.get(proof_id)

    def list_proofs(self, limit: int = 50) -> List[ZKProof]:
        with self._lock:
            return list(self._proofs.values())[:max(1, min(500, limit))]

    # -- audit ----------------------------------------------------------------

    def audit_status(self) -> Dict[str, Any]:
        return self.audit.status()

    def audit_entries(self, event_type: str = "", actor: str = "",
                      limit: int = 50, offset: int = 0) -> List[AuditEntry]:
        return self.audit.list_entries(event_type=event_type, actor=actor,
                                        limit=limit, offset=offset)

    def audit_verify(self) -> AuditChainState:
        return self.audit.verify_chain()

    def reset(self) -> None:
        with self._lock:
            self._proofs.clear()
            self.groups = {DEFAULT_GROUP.group_id: DEFAULT_GROUP}
        self.audit.reset()

    def on_event(self, cb) -> None:
        """Forward audit trail events to a callback (used by WebSocket)."""
        self.audit.on_event(cb)


def _generate_safe_prime(bits: int) -> Tuple[int, int, int]:
    """Generate a safe prime p = 2*q + 1 with g = 4 as generator."""
    while True:
        q = secrets.randbits(bits - 1) | (1 << (bits - 2)) | 1
        if not _is_prime(q):
            continue
        p = 2 * q + 1
        if not _is_prime(p):
            continue
        g = 4
        if pow(g, q, p) != 1 or pow(g, 2, p) == 1:
            continue
        return p, q, g


def _is_prime(n: int, k: int = 40) -> bool:
    if n < 2:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % p == 0:
            return n == p
    d = n - 1
    r = 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for _ in range(k):
        a = secrets.randbelow(n - 3) + 2
        x = pow(a, d, n)
        if x == 1 or x == n - 1:
            continue
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_G: Optional[ZKAuditEngine] = None
_L = threading.Lock()


def get_zk_audit_engine() -> ZKAuditEngine:
    global _G
    with _L:
        if _G is None:
            _G = ZKAuditEngine()
        return _G


def reset_zk_audit_engine() -> None:
    global _G
    with _L:
        if _G is not None:
            _G.reset()
        _G = None

