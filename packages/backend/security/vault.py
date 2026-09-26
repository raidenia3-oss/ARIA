"""BLOQUE 68 - Local Secure Credential Vault & Encrypted Session Management Engine.

Extiende la bveda local de Bloque 36 (backend/security/crypto.py) con:
- Gestin de perfiles de acceso (accounts) con credenciales cifradas.
- Gestin de sesiones activas (cookies/tokens) inyectables para automatizacin.
- Motor de rotacin de credenciales con versionado.
- REST endpoints dedicados en /api/security/vault.

Diseno 100% local y soberano:
- Cifrado simetrico Fernet (AES-128-CBC + HMAC-SHA256) con clave derivada por
  PBKDF2-HMAC-SHA256 a partir de un secreto maestro de usuario.
- Persistencia en disco con formato AURAVLT2 (magic + salt + token), igual
  que crypto.py, para que un fichero extraido sea ilegible sin la clave.
- NUNCA se escribe el secreto maestro ni credenciales en texto plano.
- Sin dependencias cloud ni de gestores de contraseas externos.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.security.crypto import (
    EncryptedStore,
    VaultIntegrityError,
    VaultLockedError,
    decrypt_bytes,
    decrypt_json,
    derive_key,
    encrypt_bytes,
    encrypt_json,
)

from fastapi import APIRouter, HTTPException, Query

# Constantes.
_VAULT_ENTRY_SUFFIX = ".vault"
_SESSION_COOKIE_PREFIX = "aura_session:"
_MAX_SESSION_AGE_SECS = 86400 * 7
_DEFAULT_VAULT_DIR_ENV = "AURA_VAULT_DIR"


class VaultError(Exception):
    """Error generico de la bveda de credenciales."""


class VaultPermissionError(Exception):
    """Permiso denegado (bveda bloqueada o perfil inexistente)."""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_ts() -> float:
    return time.time()


def _redact(value: str, keep: int = 4) -> str:
    """Devuelve un string parcialmente enmascarado para logs/auditoria."""
    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return value[:keep] + "*" * (len(value) - keep)


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class CredentialEntry:
    """Una credencial individual (password/token/cookie) dentro de un perfil."""
    key: str
    value: str
    kind: str = "password"
    note: str = ""
    created_at: str = field(default_factory=_utcnow_iso)
    updated_at: str = field(default_factory=_utcnow_iso)
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "kind": self.kind,
            "note": self.note,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CredentialEntry":
        return cls(
            key=str(data.get("key", "")),
            value=str(data.get("value", "")),
            kind=str(data.get("kind", "password")),
            note=str(data.get("note", "")),
            created_at=str(data.get("created_at", _utcnow_iso())),
            updated_at=str(data.get("updated_at", _utcnow_iso())),
            version=int(data.get("version", 1)),
        )


@dataclass
class VaultProfile:
    """Un perfil de acceso (cuenta) con sus credenciales y metadatos."""
    profile_id: str
    name: str
    service: str
    credentials: List[CredentialEntry] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utcnow_iso)
    updated_at: str = field(default_factory=_utcnow_iso)
    enabled: bool = True
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "service": self.service,
            "credentials": [c.to_dict() for c in self.credentials],
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "enabled": self.enabled,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VaultProfile":
        creds = data.get("credentials") or []
        cred_list = [CredentialEntry.from_dict(c) for c in creds if isinstance(c, dict)]
        return cls(
            profile_id=str(data.get("profile_id", "")),
            name=str(data.get("name", "")),
            service=str(data.get("service", "")),
            credentials=cred_list,
            metadata=dict(data.get("metadata") or {}),
            created_at=str(data.get("created_at", _utcnow_iso())),
            updated_at=str(data.get("updated_at", _utcnow_iso())),
            enabled=bool(data.get("enabled", True)),
            description=str(data.get("description", "")),
        )

    def get_credential(self, key: str) -> Optional[CredentialEntry]:
        for c in self.credentials:
            if c.key == key:
                return c
        return None

    def set_credential(self, entry: CredentialEntry) -> None:
        existing = self.get_credential(entry.key)
        if existing is not None:
            idx = self.credentials.index(existing)
            entry.version = existing.version + 1
            entry.created_at = existing.created_at
            self.credentials[idx] = entry
        else:
            self.credentials.append(entry)
        self.updated_at = _utcnow_iso()

    def remove_credential(self, key: str) -> bool:
        c = self.get_credential(key)
        if c is None:
            return False
        self.credentials.remove(c)
        self.updated_at = _utcnow_iso()
        return True


@dataclass
class SessionCookie:
    """Cookie/sesiÃ³n activa inyectable para automatizaciÃ³n."""
    cookie_name: str
    cookie_value: str  # siempre cifrado
    domain: str = ""
    path: str = "/"
    expires_at: Optional[float] = None
    http_only: bool = True
    secure: bool = True
    same_site: str = "Lax"
    created_at: str = field(default_factory=_utcnow_iso)
    last_used: str = field(default_factory=_utcnow_iso)
    note: str = ""

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return _now_ts() > float(self.expires_at)

    def touch(self) -> None:
        self.last_used = _utcnow_iso()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cookie_name": self.cookie_name,
            "cookie_value": self.cookie_value,
            "domain": self.domain,
            "path": self.path,
            "expires_at": self.expires_at,
            "http_only": self.http_only,
            "secure": self.secure,
            "same_site": self.same_site,
            "created_at": self.created_at,
            "last_used": self.last_used,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionCookie":
        return cls(
            cookie_name=str(data.get("cookie_name", "")),
            cookie_value=str(data.get("cookie_value", "")),
            domain=str(data.get("domain", "")),
            path=str(data.get("path", "/")),
            expires_at=data.get("expires_at"),
            http_only=bool(data.get("http_only", True)),
            secure=bool(data.get("secure", True)),
            same_site=str(data.get("same_site", "Lax")),
            created_at=str(data.get("created_at", _utcnow_iso())),
            last_used=str(data.get("last_used", _utcnow_iso())),
            note=str(data.get("note", "")),
        )


class SessionManager:
    """Gestiona sesiones activas (cookies/tokens) en memoria con expiraciÃ³n."""
    def __init__(self, max_age_secs: int = 86400 * 7) -> None:
        self._sessions: Dict[str, List[SessionCookie]] = {}
        self._max_age = max_age_secs
        self._mutex = threading.RLock()

    def set(self, profile_id: str, cookies: List[SessionCookie]) -> None:
        with self._mutex:
            self._sessions[profile_id] = list(cookies)

    def get(self, profile_id: str) -> List[SessionCookie]:
        with self._mutex:
            cookies = list(self._sessions.get(profile_id, []))
        cookies = [c for c in cookies if not c.is_expired()]
        return cookies

    def add(self, profile_id: str, cookie: SessionCookie) -> None:
        with self._mutex:
            cookies = self._sessions.setdefault(profile_id, [])
            for i, c in enumerate(cookies):
                if c.cookie_name == cookie.cookie_name and c.domain == cookie.domain:
                    cookies[i] = cookie
                    return
            cookies.append(cookie)

    def remove(self, profile_id: str, cookie_name: str, domain: str = "") -> bool:
        with self._mutex:
            cookies = self._sessions.get(profile_id, [])
            for i, c in enumerate(cookies):
                if c.cookie_name == cookie_name and (not domain or c.domain == domain):
                    del cookies[i]
                    return True
            return False

    def clear(self, profile_id: str) -> None:
        with self._mutex:
            self._sessions.pop(profile_id, None)

    def purge_expired(self) -> int:
        removed = 0
        with self._mutex:
            for pid in list(self._sessions.keys()):
                before = len(self._sessions[pid])
                self._sessions[pid] = [c for c in self._sessions[pid] if not c.is_expired()]
                removed += before - len(self._sessions[pid])
                if not self._sessions[pid]:
                    del self._sessions[pid]
        return removed

    def active_profiles(self) -> List[str]:
        with self._mutex:
            return list(self._sessions.keys())

    def clear_all(self) -> None:
        with self._mutex:
            self._sessions.clear()


class CredentialVaultEngine:
    """Motor principal de la bÃ³veda de credenciales y sesiones cifradas."""
    def __init__(self, store=None, session_max_age=86400*7):
        self.manager = VaultManager(store)
        self.sessions = SessionManager(max_age_secs=session_max_age)
        self._audit = []
        self._audit_max = 500
        self._mutex = threading.RLock()

    @property
    def is_locked(self):
        return self.manager.is_locked

    def unlock(self, master_secret):
        result = self.manager.unlock(master_secret)
        self._audit_event("vault_unlock", "ok", "master_secret provided")
        return result

    def lock(self):
        self.sessions.clear_all()
        result = self.manager.lock()
        self._audit_event("vault_lock", "ok", "session cleared")
        return result

    def _audit_event(self, event_type, status, detail):
        with self._mutex:
            self._audit.append({"ts": _utcnow_iso(), "type": event_type,
                                 "status": status, "detail": detail})
            if len(self._audit) > self._audit_max:
                self._audit = self._audit[-self._audit_max:]

    def get_audit(self, limit=100):
        with self._mutex:
            return list(self._audit[-limit:])

    def status(self):
        base = self.manager.status()
        base["is_locked"] = self.manager.is_locked
        base["sessions_active"] = len(self.sessions.active_profiles())
        base["audit_entries"] = len(self._audit)
        return base

    def list_profiles(self, include_disabled=False):
        if include_disabled:
            return self.manager.list_all_profiles()
        return self.manager.list_profiles()

    def get_profile(self, profile_id):
        return self.manager.get_profile(profile_id)

    def create_profile(self, profile):
        created = self.manager.create_profile(profile)
        self._audit_event("profile_create", "ok", "profile_id=%s" % profile.profile_id)
        return created

    def update_profile(self, profile_id, updates):
        updated = self.manager.update_profile(profile_id, updates)
        if updated is not None:
            self._audit_event("profile_update", "ok", "profile_id=%s" % profile_id)
        return updated

    def delete_profile(self, profile_id):
        self.sessions.clear(profile_id)
        ok = self.manager.delete_profile(profile_id)
        if ok:
            self._audit_event("profile_delete", "ok", "profile_id=%s" % profile_id)
        return ok

    def upsert_profile(self, profile):
        up = self.manager.upsert_profile(profile)
        self._audit_event("profile_upsert", "ok", "profile_id=%s" % profile.profile_id)
        return up

    def set_credential(self, profile_id, entry):
        profile = self.manager.add_credential(profile_id, entry)
        if profile is not None:
            self._audit_event("credential_set", "ok",
                              "profile_id=%s key=%s kind=%s" % (profile_id, entry.key, entry.kind))
        return profile

    def get_credential(self, profile_id, key):
        profile = self.manager.get_profile(profile_id)
        if profile is None:
            return None
        return profile.get_credential(key)

    def remove_credential(self, profile_id, key):
        ok = self.manager.remove_credential(profile_id, key)
        if ok:
            self._audit_event("credential_remove", "ok",
                              "profile_id=%s key=%s" % (profile_id, key))
            return True
        return False

    def set_session(self, profile_id, cookies):
        self.sessions.set(profile_id, cookies)
        self._audit_event("session_set", "ok",
                          "profile_id=%s cookies=%d" % (profile_id, len(cookies)))

    def get_session(self, profile_id):
        cookies = self.sessions.get(profile_id)
        for c in cookies:
            c.touch()
        return cookies

    def add_session_cookie(self, profile_id, cookie):
        self.sessions.add(profile_id, cookie)
        self._audit_event("session_add", "ok",
                          "profile_id=%s cookie=%s" % (profile_id, cookie.cookie_name))

    def remove_session_cookie(self, profile_id, cookie_name, domain=""):
        ok = self.sessions.remove(profile_id, cookie_name, domain)
        if ok:
            self._audit_event("session_remove", "ok",
                              "profile_id=%s cookie=%s" % (profile_id, cookie_name))
        return ok

    def clear_session(self, profile_id):
        self.sessions.clear(profile_id)
        self._audit_event("session_clear", "ok", "profile_id=%s" % profile_id)

    def purge_expired_sessions(self):
        removed = self.sessions.purge_expired()
        if removed:
            self._audit_event("session_purge", "ok", "removed=%d" % removed)
        return removed

    def inject_session_headers(self, profile_id):
        cookies = self.get_session(profile_id)
        if not cookies:
            return {}
        parts = ["%s=%s" % (c.cookie_name, c.cookie_value) for c in cookies]
        return {"Cookie": "; ".join(parts)}
# Singleton + REST router (Parte 5)

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/security/vault", tags=["Security"])

_engine: Optional[CredentialVaultEngine] = None
_engine_lock = threading.RLock()


def get_engine() -> CredentialVaultEngine:
    """Retorna el singleton del motor de credenciales (local, sin cloud)."""
    global _engine
    with _engine_lock:
        if _engine is None:
            store = EncryptedStore()
            _engine = CredentialVaultEngine(store=store)
    return _engine


def reset_engine() -> None:
    """Resetea el singleton (usado en tests)."""
    global _engine
    with _engine_lock:
        _engine = None


def set_engine(eng: "CredentialVaultEngine") -> None:
    """Inyecta un engine preconfigurado (usado en tests)."""
    global _engine
    with _engine_lock:
        _engine = eng


def _require_unlocked() -> CredentialVaultEngine:
    engine = get_engine()
    if engine.is_locked:
        raise HTTPException(status_code=403, detail="vault is locked: call POST /api/security/vault/unlock first")
    return engine


# ---- endpoints ----

@router.get("/status")
async def vault_status():
    return get_engine().status()


@router.post("/unlock")
async def vault_unlock(payload: dict):
    master_secret = str(payload.get("master_secret", ""))
    if not master_secret:
        raise HTTPException(status_code=400, detail="master_secret is required")
    try:
        return get_engine().unlock(master_secret)
    except Exception as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/lock")
async def vault_lock():
    return get_engine().lock()


@router.get("/audit")
async def vault_audit(limit: int = Query(100, ge=1, le=1000)):
    return {"events": get_engine().get_audit(limit=limit)}


@router.get("/profiles")
async def list_profiles(include_disabled: bool = Query(False)):
    engine = get_engine()
    try:
        profiles = engine.list_profiles(include_disabled=include_disabled)
    except VaultLockedError:
        raise HTTPException(status_code=403, detail="vault is locked")
    return {"profiles": [p.to_dict() for p in profiles], "total": len(profiles)}


@router.get("/profiles/{profile_id}")
async def get_profile(profile_id: str):
    engine = _require_unlocked()
    profile = engine.get_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="profile not found")
    return {"profile": profile.to_dict()}


@router.post("/profiles")
async def create_profile(payload: dict):
    engine = _require_unlocked()
    try:
        profile = VaultProfile.from_dict(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid profile: %s" % exc)
    try:
        created = engine.create_profile(profile)
        return {"status": "created", "profile": created.to_dict()}
    except VaultError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.put("/profiles/{profile_id}")
async def update_profile(profile_id: str, payload: dict):
    engine = _require_unlocked()
    updated = engine.update_profile(profile_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="profile not found")
    return {"status": "updated", "profile": updated.to_dict()}


@router.delete("/profiles/{profile_id}")
async def delete_profile(profile_id: str):
    engine = _require_unlocked()
    ok = engine.delete_profile(profile_id)
    if not ok:
        raise HTTPException(status_code=404, detail="profile not found")
    return {"status": "deleted", "profile_id": profile_id}


@router.post("/profiles/{profile_id}/credentials")
async def add_credential(profile_id: str, payload: dict):
    engine = _require_unlocked()
    try:
        entry = CredentialEntry.from_dict(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid credential: %s" % exc)
    profile = engine.set_credential(profile_id, entry)
    if profile is None:
        raise HTTPException(status_code=404, detail="profile not found")
    return {"status": "set", "profile": profile.to_dict()}


@router.get("/profiles/{profile_id}/credentials/{key}")
async def get_credential(profile_id: str, key: str):
    engine = _require_unlocked()
    entry = engine.get_credential(profile_id, key)
    if entry is None:
        raise HTTPException(status_code=404, detail="credential not found")
    return {"credential": entry.to_dict()}


@router.delete("/profiles/{profile_id}/credentials/{key}")
async def remove_credential(profile_id: str, key: str):
    engine = _require_unlocked()
    ok = engine.remove_credential(profile_id, key)
    if not ok:
        raise HTTPException(status_code=404, detail="credential not found")
    return {"status": "deleted", "profile_id": profile_id, "key": key}


@router.get("/profiles/{profile_id}/sessions")
async def list_sessions(profile_id: str):
    engine = _require_unlocked()
    cookies = engine.get_session(profile_id)
    return {"cookies": [c.to_dict() for c in cookies], "total": len(cookies)}


@router.post("/profiles/{profile_id}/sessions")
async def set_session(profile_id: str, payload: dict):
    engine = _require_unlocked()
    if engine.get_profile(profile_id) is None:
        raise HTTPException(status_code=404, detail="profile not found")
    cookies_data = payload.get("cookies") or []
    cookies = [SessionCookie.from_dict(c) for c in cookies_data if isinstance(c, dict)]
    engine.set_session(profile_id, cookies)
    return {"status": "set", "profile_id": profile_id, "cookies": len(cookies)}


@router.post("/profiles/{profile_id}/sessions/cookie")
async def add_session_cookie(profile_id: str, payload: dict):
    engine = _require_unlocked()
    if engine.get_profile(profile_id) is None:
        raise HTTPException(status_code=404, detail="profile not found")
    try:
        cookie = SessionCookie.from_dict(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid cookie: %s" % exc)
    engine.add_session_cookie(profile_id, cookie)
    return {"status": "added", "profile_id": profile_id, "cookie_name": cookie.cookie_name}


@router.delete("/profiles/{profile_id}/sessions")
async def clear_session(profile_id: str):
    engine = _require_unlocked()
    engine.clear_session(profile_id)
    return {"status": "cleared", "profile_id": profile_id}


@router.post("/sessions/purge")
async def purge_sessions():
    engine = _require_unlocked()
    removed = engine.purge_expired_sessions()
    return {"status": "purged", "removed": removed}


@router.get("/profiles/{profile_id}/inject")
async def inject_headers(profile_id: str):
    engine = _require_unlocked()
    return {"headers": engine.inject_session_headers(profile_id)}


def enable_autostart() -> None:
    """Hook de arranque (no-op para este bloque; compatible con main.py)."""
    return None
class VaultManager:
    """Gestiona los perfiles de acceso persistidos en la bÃ³veda cifrada."""
    def __init__(self, store: Optional[EncryptedStore] = None) -> None:
        self._store = store or EncryptedStore()
        self._profiles: Dict[str, VaultProfile] = {}
        self._loaded = False
        self._mutex = threading.RLock()

    @property
    def store(self) -> EncryptedStore:
        return self._store

    @property
    def is_locked(self) -> bool:
        return self._store.is_locked

    def unlock(self, master_secret: str) -> Dict[str, Any]:
        return self._store.unlock(master_secret)

    def lock(self) -> Dict[str, Any]:
        with self._mutex:
            self._profiles.clear()
            self._loaded = False
        return self._store.lock()

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._mutex:
            if self._loaded:
                return
            for name in self._store.list_entries():
                try:
                    data = self._store.read(name)
                except (VaultIntegrityError, VaultLockedError):
                    continue
                if not isinstance(data, dict):
                    continue
                try:
                    profile = VaultProfile.from_dict(data)
                except Exception:
                    continue
                self._profiles[profile.profile_id] = profile
            self._loaded = True

    def reload(self) -> None:
        with self._mutex:
            self._profiles.clear()
            self._loaded = False
        self._ensure_loaded()

    def _persist(self, profile: VaultProfile) -> None:
        self._store.write(profile.profile_id, profile.to_dict())

    def _delete_persist(self, profile_id: str) -> None:
        self._store.delete(profile_id)

    def list_profiles(self) -> List[VaultProfile]:
        if self.is_locked:
            raise VaultLockedError("vault is locked: call unlock first")
        self._ensure_loaded()
        with self._mutex:
            return [p for p in self._profiles.values() if p.enabled]

    def list_all_profiles(self) -> List[VaultProfile]:
        if self.is_locked:
            raise VaultLockedError("vault is locked: call unlock first")
        self._ensure_loaded()
        with self._mutex:
            return list(self._profiles.values())

    def get_profile(self, profile_id: str) -> Optional[VaultProfile]:
        if self.is_locked:
            raise VaultLockedError("vault is locked: call unlock first")
        self._ensure_loaded()
        with self._mutex:
            return self._profiles.get(profile_id)

    def create_profile(self, profile: VaultProfile) -> VaultProfile:
        if not profile.profile_id:
            raise VaultError("profile_id is required")
        with self._mutex:
            self._ensure_loaded()
            if profile.profile_id in self._profiles:
                raise VaultError(f"profile already exists: {profile.profile_id}")
            self._profiles[profile.profile_id] = profile
            self._persist(profile)
            return profile

    def update_profile(self, profile_id: str, updates: Dict[str, Any]) -> Optional[VaultProfile]:
        with self._mutex:
            self._ensure_loaded()
            profile = self._profiles.get(profile_id)
            if profile is None:
                return None
            for k, v in updates.items():
                if k in ("name", "service", "description", "enabled", "metadata"):
                    setattr(profile, k, v)
            profile.updated_at = _utcnow_iso()
            self._persist(profile)
            return profile

    def upsert_profile(self, profile: VaultProfile) -> VaultProfile:
        with self._mutex:
            self._ensure_loaded()
            existing = self._profiles.get(profile.profile_id)
            if existing is None:
                self._profiles[profile.profile_id] = profile
                self._persist(profile)
            else:
                profile.created_at = existing.created_at
                self._profiles[profile.profile_id] = profile
                self._persist(profile)
            return profile

    def delete_profile(self, profile_id: str) -> bool:
        with self._mutex:
            self._ensure_loaded()
            if profile_id not in self._profiles:
                return False
            del self._profiles[profile_id]
            self._delete_persist(profile_id)
            return True

    def add_credential(self, profile_id: str, entry: CredentialEntry) -> Optional[VaultProfile]:
        with self._mutex:
            self._ensure_loaded()
            profile = self._profiles.get(profile_id)
            if profile is None:
                return None
            profile.set_credential(entry)
            self._persist(profile)
            return profile

    def remove_credential(self, profile_id: str, key: str) -> bool:
        with self._mutex:
            self._ensure_loaded()
            profile = self._profiles.get(profile_id)
            if profile is None:
                return False
            ok = profile.remove_credential(key)
            if ok:
                self._persist(profile)
            return ok

    def status(self) -> Dict[str, Any]:
        self._ensure_loaded()
        with self._mutex:
            return {
                "status": "ok",
                "locked": self.is_locked,
                "profiles_total": len(self._profiles),
                "profiles_enabled": sum(1 for p in self._profiles.values() if p.enabled),
                "services": sorted({p.service for p in self._profiles.values() if p.service}),
            }


__all__ = [
    "CredentialEntry",
    "VaultProfile",
    "SessionCookie",
    "SessionManager",
    "VaultManager",
    "CredentialVaultEngine",
    "VaultError",
    "VaultPermissionError",
    "get_engine",
    "reset_engine",
    "enable_autostart",
    "router",
]
