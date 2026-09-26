"""BLOQUE 90 - Sovereign Cryptographic Identity & Zero-Trust Auth Engine.
Local identity issuer, ED25519 key pairs, payload signing/verification,
ephemeral key rotation, zero-trust policy decisions. 100% offline.

Re-exports all public symbols from identity_engine (the canonical implementation).
"""

from __future__ import annotations

from backend.security.identity_engine import (
    NodeIdentity,
    SovereignCert,
    SignedPayload,
    SovereignIdentityEngine,
    get_identity_engine,
    reset_identity_engine,
    STORE_SUBDIR,
    KEY_SUFFIX,
    PUB_SUFFIX,
    CERT_SUFFIX,
    EPHEMERAL_TTL_S,
    MAX_EPHEMERAL,
    MAX_NODES,
    MIN_ROLE_SCORE,
)

__all__ = [
    'NodeIdentity',
    'SovereignCert',
    'SignedPayload',
    'SovereignIdentityEngine',
    'get_identity_engine',
    'reset_identity_engine',
    'STORE_SUBDIR',
    'KEY_SUFFIX',
    'PUB_SUFFIX',
    'CERT_SUFFIX',
    'EPHEMERAL_TTL_S',
    'MAX_EPHEMERAL',
    'MAX_NODES',
    'MIN_ROLE_SCORE',
]
