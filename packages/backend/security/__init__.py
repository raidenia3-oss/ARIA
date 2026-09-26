"""AURA Security — capa de cifrado local (Bloque 36), bóveda de credenciales (Bloque 68)
y motor de mitigación de amenazas adversariales (Bloque 87)."""

from backend.security.crypto import (
    EncryptedStore,
    VaultIntegrityError,
    VaultLockedError,
    decrypt_bytes,
    decrypt_json,
    derive_key,
    encrypt_bytes,
    encrypt_json,
    get_default_store,
)
from backend.security.vault import (
    CredentialEntry,
    CredentialVaultEngine,
    SessionCookie,
    SessionManager,
    VaultError,
    VaultManager,
    VaultPermissionError,
    VaultProfile,
    enable_autostart,
    get_engine,
    reset_engine,
)
from backend.security.mitigation import (
    BehavioralAnomalyDetector,
    DefenseEngine,
    QuarantineRecord,
    SecurityEvent,
    ThreatAlert,
    get_defense_engine,
    reset_defense_engine,
)
from backend.security.identity_engine import (
    NodeIdentity,
    SovereignCert,
    SovereignIdentityEngine,
    SignedPayload,
    get_identity_engine,
    reset_identity_engine,
)
from backend.security.zk_audit import (
    AuditEntry,
    FiatShamirSchnorr,
    SovereignAuditLogger,
    ZKAuditEngine,
    ZKProof,
    get_zk_audit_engine,
    reset_zk_audit_engine,
)

__all__ = [
    "EncryptedStore",
    "VaultIntegrityError",
    "VaultLockedError",
    "decrypt_bytes",
    "decrypt_json",
    "derive_key",
    "encrypt_bytes",
    "encrypt_json",
    "get_default_store",
    "CredentialEntry",
    "CredentialVaultEngine",
    "SessionCookie",
    "SessionManager",
    "VaultError",
    "VaultManager",
    "VaultPermissionError",
    "VaultProfile",
    "enable_autostart",
    "get_engine",
    "reset_engine",
    "BehavioralAnomalyDetector",
    "DefenseEngine",
    "QuarantineRecord",
    "SecurityEvent",
    "ThreatAlert",
    "get_defense_engine",
    "reset_defense_engine",
    "NodeIdentity",
    "SovereignCert",
    "SovereignIdentityEngine",
    "SignedPayload",
    "get_identity_engine",
    "reset_identity_engine",
    "ZKAuditEngine",
    "ZKProof",
    "FiatShamirSchnorr",
    "AuditEntry",
    "SovereignAuditLogger",
    "get_zk_audit_engine",
    "reset_zk_audit_engine",
]

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
