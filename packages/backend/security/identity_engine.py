"""BLOQUE 90 - Sovereign Identity & Zero-Trust Auth (local, ED25519)."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

STORE_SUBDIR = "backend/security_state/identities"
KEY_SUFFIX = ".ed25519.private.pem"
PUB_SUFFIX = ".ed25519.public.pem"
CERT_SUFFIX = ".cert.json"
EPHEMERAL_TTL_S = 600.0
MAX_EPHEMERAL = 50
MAX_NODES = 2000
MIN_ROLE_SCORE = 0.6


@dataclass
class NodeIdentity:
    node_id: str = ""
    label: str = ""
    role: str = "peer"
    pubkey_bytes: bytes = b""
    pubkey_b64: str = ""
    created_at: float = 0.0
    last_seen: float = 0.0
    trust_score: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "label": self.label,
            "role": self.role,
            "pubkey_b64": self.pubkey_b64,
            "created_at": self.created_at,
            "last_seen": self.last_seen,
            "trust_score": round(self.trust_score, 3),
            "offline_only": True,
        }


@dataclass
class SovereignCert:
    cert_id: str = ""
    signing_node: str = ""
    subject_node: str = ""
    issued_at: float = 0.0
    expires_at: float = 0.0
    role: str = "peer"
    rotation_count: int = 0
    serial: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cert_id": self.cert_id,
            "signing_node": self.signing_node,
            "subject_node": self.subject_node,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "role": self.role,
            "rotation_count": self.rotation_count,
            "serial": self.serial,
            "offline_only": True,
        }


@dataclass
class SignedPayload:
    payload_id: str = ""
    sender: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    signature_base64: str = ""
    created_at: float = 0.0
    verified: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "payload_id": self.payload_id,
            "sender": self.sender,
            "payload": self.payload,
            "signature_base64": self.signature_base64,
            "created_at": self.created_at,
            "verified": self.verified,
            "offline_only": True,
        }


def _kdf_key(node_id: str, salt: Optional[bytes] = None) -> bytes:
    if salt is None:
        salt = secrets.token_bytes(16)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=390_000)
    return kdf.derive(node_id.encode("utf-8"))


def _pubkey_b64(pubkey: ed25519.Ed25519PublicKey) -> str:
    return base64.urlsafe_b64encode(
        pubkey.public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
    ).decode("ascii")


def _store_dir() -> Path:
    d = Path(STORE_SUBDIR)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _key_path(node_id: str) -> Path:
    return _store_dir() / f"{node_id}{KEY_SUFFIX}"


def _pub_path(node_id: str) -> Path:
    return _store_dir() / f"{node_id}{PUB_SUFFIX}"


def _cert_path(node_id: str) -> Path:
    return _store_dir() / f"{node_id}{CERT_SUFFIX}"


def _generate_keypair() -> ed25519.Ed25519PrivateKey:
    return ed25519.Ed25519PrivateKey.generate()


def _save_keypair(priv: ed25519.Ed25519PrivateKey, node_id: str) -> None:
    pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    _key_path(node_id).write_bytes(pem)
    _pub_path(node_id).write_bytes(pub)


def _load_private(node_id: str) -> Optional[ed25519.Ed25519PrivateKey]:
    p = _key_path(node_id)
    if not p.exists():
        return None
    return serialization.load_pem_private_key(p.read_bytes(), password=None)


def _load_public(node_id: str) -> Optional[ed25519.Ed25519PublicKey]:
    p = _pub_path(node_id)
    if not p.exists():
        return None
    return serialization.load_pem_public_key(p.read_bytes())


def _signing_payload(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


class SovereignIdentityEngine:
    """Local ED25519 identity issuer + zero-trust signer/verifier."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._nodes: Dict[str, NodeIdentity] = {}
        self._certs: Dict[str, SovereignCert] = {}
        self._ephemeral: Dict[str, Dict[str, Any]] = {}
        self._watchers: List[Callable[[Dict[str, Any]], None]] = []
        self._load_state()

    def _load_state(self) -> None:
        d = _store_dir()
        for p in d.glob(f"*{CERT_SUFFIX}"):
            try:
                cert = SovereignCert(**json.loads(p.read_text(encoding="utf-8")))
                self._certs[cert.cert_id] = cert
                if cert.subject_node and cert.subject_node not in self._nodes:
                    pub = _load_public(cert.subject_node)
                    if pub is not None:
                        self._nodes[cert.subject_node] = NodeIdentity(
                            node_id=cert.subject_node,
                            label=cert.subject_node,
                            role=cert.role,
                            pubkey_b64=_pubkey_b64(pub),
                            created_at=cert.issued_at,
                            last_seen=time.time(),
                            trust_score=1.0,
                        )
            except Exception:
                continue

    def _emit(self, evt: Dict[str, Any]) -> None:
        with self._lock:
            cbs = list(self._watchers)
        for cb in cbs:
            try:
                cb(evt)
            except Exception:
                pass

    def on_event(self, cb: Callable[[Dict[str, Any]], None]) -> None:
        with self._lock:
            self._watchers.append(cb)

    def register(self, label: str = "", role: str = "peer",
                 force: bool = False) -> NodeIdentity:
        node_id = uuid.uuid4().hex[:16]
        with self._lock:
            if len(self._nodes) >= MAX_NODES and not force:
                raise ValueError("max nodes reached")
            priv = _generate_keypair()
            _save_keypair(priv, node_id)
            pub = priv.public_key()
            ident = NodeIdentity(
                node_id=node_id,
                label=label or node_id,
                role=role,
                pubkey_b64=_pubkey_b64(pub),
                created_at=time.time(),
                last_seen=time.time(),
                trust_score=1.0,
            )
            self._nodes[node_id] = ident
        self._emit({"type": "node_registered", **ident.to_dict()})
        return ident

    def get(self, node_id: str) -> Optional[NodeIdentity]:
        with self._lock:
            return self._nodes.get(node_id)

    def list_nodes(self, limit: int = 100) -> List[NodeIdentity]:
        with self._lock:
            items = sorted(self._nodes.values(), key=lambda n: n.last_seen, reverse=True)
            return items[:max(1, min(500, limit))]

    def touch(self, node_id: str) -> bool:
        with self._lock:
            n = self._nodes.get(node_id)
            if n is None:
                return False
            n.last_seen = time.time()
            return True

    def issue_cert(self, subject_node: str, signing_node: str = "local",
                   role: str = "peer", ttl_s: float = 86400.0) -> SovereignCert:
        if subject_node not in self._nodes:
            raise ValueError("node not registered")
        now = time.time()
        cert = SovereignCert(
            cert_id=uuid.uuid4().hex[:12],
            signing_node=signing_node,
            subject_node=subject_node,
            issued_at=now,
            expires_at=now + max(60.0, float(ttl_s)),
            role=role,
            rotation_count=0,
            serial=secrets.token_hex(8),
        )
        with self._lock:
            self._certs[cert.cert_id] = cert
            _cert_path(subject_node).write_text(
                json.dumps(cert.to_dict()), encoding="utf-8")
        self._emit({"type": "cert_issued", **cert.to_dict()})
        return cert

    def list_certs(self, limit: int = 100) -> List[SovereignCert]:
        with self._lock:
            items = sorted(self._certs.values(), key=lambda c: c.issued_at, reverse=True)
            return items[:max(1, min(500, limit))]

    def sign(self, node_id: str, payload: Dict[str, Any],
             include_pubkey: bool = True) -> SignedPayload:
        priv = _load_private(node_id)
        if priv is None:
            raise ValueError("node not registered")
        body = dict(payload)
        if include_pubkey:
            body["pubkey_b64"] = _pubkey_b64(priv.public_key())
        body["node_id"] = node_id
        body["ts"] = time.time()
        data = _signing_payload(body)
        sig = priv.sign(data)
        sp = SignedPayload(
            payload_id=uuid.uuid4().hex[:12],
            sender=node_id,
            payload=body,
            signature_base64=base64.urlsafe_b64encode(sig).decode("ascii"),
            created_at=time.time(),
            verified=False,
        )
        self._emit({"type": "payload_signed", **sp.to_dict()})
        return sp

    def verify(self, signed: Any) -> bool:
        if isinstance(signed, dict):
            signed = SignedPayload(**signed)
        node = self.get(signed.sender)
        if node is None:
            pub = _load_public(signed.sender)
            if pub is None:
                return False
            try:
                raw = base64.urlsafe_b64decode(signed.signature_base64)
                pub.verify(raw, _signing_payload(signed.payload))
                signed.verified = True
                return True
            except Exception:
                return False
        try:
            raw = base64.urlsafe_b64decode(signed.signature_base64)
            pub = serialization.load_pem_public_key(
                _pub_path(signed.sender).read_bytes())
            pub.verify(raw, _signing_payload(signed.payload))
            signed.verified = True
            return True
        except Exception:
            return False

    def verify_bytes(self, node_id: str, message: bytes,
                     signature_b64: str) -> bool:
        pub = _load_public(node_id)
        if pub is None:
            return False
        try:
            raw = base64.urlsafe_b64decode(signature_b64)
            pub.verify(raw, message)
            return True
        except Exception:
            return False

    def rotate(self, node_id: str) -> NodeIdentity:
        with self._lock:
            if node_id not in self._nodes:
                raise ValueError("node not registered")
        priv = _generate_keypair()
        _save_keypair(priv, node_id)
        pub = priv.public_key()
        with self._lock:
            old = self._nodes[node_id]
            old.pubkey_b64 = _pubkey_b64(pub)
            old.last_seen = time.time()
            for c in list(self._certs.values()):
                if c.subject_node == node_id:
                    c.rotation_count += 1
                    _cert_path(node_id).write_text(
                        json.dumps(c.to_dict()), encoding="utf-8")
        self._emit({"type": "key_rotated", "node_id": node_id,
                    "rotation_count": old.trust_score and 0 or 0})
        return old

    def issue_ephemeral(self, node_id: str, scope: str = "swarm",
                        ttl_s: float = EPHEMERAL_TTL_S) -> Dict[str, Any]:
        if node_id not in self._nodes:
            raise ValueError("node not registered")
        now = time.time()
        token = secrets.token_urlsafe(32)
        rec = {"token": token, "node_id": node_id, "scope": scope,
               "created_at": now, "expires_at": now + max(60.0, float(ttl_s)),
               "offline_only": True}
        with self._lock:
            self._ephemeral[node_id] = rec
            if len(self._ephemeral) > MAX_EPHEMERAL:
                oldest = min(self._ephemeral.items(), key=lambda kv: kv[1]["created_at"])
                del self._ephemeral[oldest[0]]
        self._emit({"type": "ephemeral_issued", **rec})
        return rec

    def validate_ephemeral(self, token: str, node_id: str,
                           scope: Optional[str] = None) -> bool:
        with self._lock:
            rec = self._ephemeral.get(node_id)
        if rec is None or rec["token"] != token:
            return False
        if rec["expires_at"] < time.time():
            return False
        if scope is not None and rec["scope"] != scope:
            return False
        return True

    def revoke_ephemeral(self, node_id: str) -> bool:
        with self._lock:
            if node_id in self._ephemeral:
                del self._ephemeral[node_id]
                return True
        return False

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {"nodes": len(self._nodes), "certs": len(self._certs),
                    "ephemeral": len(self._ephemeral),
                    "offline_only": True, "algorithm": "ed25519"}

    def reset(self) -> None:
        with self._lock:
            self._nodes.clear()
            self._certs.clear()
            self._ephemeral.clear()
        for p in list(_store_dir().glob("*")):
            try:
                p.unlink()
            except Exception:
                pass


_G: Optional[SovereignIdentityEngine] = None
_L = threading.Lock()


def get_identity_engine() -> SovereignIdentityEngine:
    global _G
    with _L:
        if _G is None:
            _G = SovereignIdentityEngine()
        return _G


def reset_identity_engine() -> None:
    global _G
    with _L:
        _G = None