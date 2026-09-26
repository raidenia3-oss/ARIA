"""Device authentication for AURA ↔ AME communication.

Provides device registration, pairing, token rotation, and revocation.
Tokens are never stored in logs. Only masked representations are used.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import time
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from pathlib import Path
import logging

logger = logging.getLogger("AURADeviceAuth")

_TOKEN_TTL_SECONDS = 3600
_TOKEN_REFRESH_THRESHOLD = 0.75
_DATA_DIR = Path(os.environ.get(
    "AURA_DATA_DIR",
    os.path.join(os.path.dirname(__file__), "..", "data"),
))

STATUSES = {"active", "revoked", "pending", "expired"}
PERMISSIONS = {"chat", "execute", "delegate", "notifications", "config"}


@dataclass
class DeviceSession:
    device_id: str
    token_hash: str
    issued_at: float
    expires_at: float
    last_used: float
    permissions: List[str]
    status: str = "active"
    device_name: str = ""
    approved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "last_used": self.last_used,
            "permissions": self.permissions,
            "status": self.status,
            "device_name": self.device_name,
            "approved": self.approved,
            "token_masked": _mask(self.token_hash[:8]) if self.token_hash else "[none]",
        }

    @property
    def token_hash_value(self) -> str:
        return self.token_hash


def _mask(s: str) -> str:
    if not s or len(s) <= 4:
        return "****"
    return f"{s[:2]}****{s[-2:]}"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _generate_token() -> str:
    return secrets.token_urlsafe(32)


def _load_sessions(data_dir_override: Optional[Path] = None) -> Dict[str, DeviceSession]:
    data_dir = data_dir_override or _DATA_DIR
    path = data_dir / "device_sessions.json"
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text())
        sessions = {}
        for dev_id, data in raw.items():
            sessions[dev_id] = DeviceSession(
                device_id=data["device_id"],
                token_hash=data["token_hash"],
                issued_at=data["issued_at"],
                expires_at=data["expires_at"],
                last_used=data.get("last_used", data["issued_at"]),
                permissions=data.get("permissions", ["chat"]),
                status=data.get("status", "active"),
                device_name=data.get("device_name", ""),
                approved=data.get("approved", False),
            )
        return sessions
    except Exception as e:
        logger.warning("Failed to load device sessions: %s", e)
        return {}


def _save_sessions(sessions: Dict[str, DeviceSession], data_dir_override: Optional[Path] = None) -> None:
    data_dir = data_dir_override or _DATA_DIR
    path = data_dir / "device_sessions.json"
    data_dir.mkdir(parents=True, exist_ok=True)
    data = {dev_id: asdict(s) for dev_id, s in sessions.items()}
    path.write_text(json.dumps(data, indent=2))


class DeviceAuthManager:
    _instance: Optional["DeviceAuthManager"] = None

    def __init__(self) -> None:
        self._sessions: Dict[str, DeviceSession] = {}
        self._load()

    @classmethod
    def get_instance(cls) -> "DeviceAuthManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _data_dir(self) -> Path:
        return Path(os.environ.get(
            "AURA_DATA_DIR",
            os.path.join(os.path.dirname(__file__), "..", "data"),
        ))

    def _sessions_path(self) -> Path:
        return self._data_dir() / "device_sessions.json"

    def _load(self) -> None:
        self._sessions = _load_sessions(data_dir_override=self._data_dir())

    def _save(self) -> None:
        _save_sessions(self._sessions, data_dir_override=self._data_dir())

    def register_device(self, device_id: str, device_name: str = "") -> Dict[str, Any]:
        """Register a new device. Returns a token that the client must use for auth."""
        now = time.time()
        token = _generate_token()
        token_hash = _hash_token(token)

        session = DeviceSession(
            device_id=device_id,
            token_hash=token_hash,
            issued_at=now,
            expires_at=now + _TOKEN_TTL_SECONDS,
            last_used=now,
            permissions=["chat", "execute"],
            status="pending",
            device_name=device_name,
            approved=False,
        )
        self._sessions[device_id] = session
        self._save()
        logger.info("Device registered: %s (pending approval)", _mask(device_id))
        return {
            "device_id": device_id,
            "token": token,
            "expires_in": _TOKEN_TTL_SECONDS,
            "status": "pending",
        }

    def approve_device(self, device_id: str, permissions: Optional[List[str]] = None) -> bool:
        """Approve a pending device."""
        session = self._sessions.get(device_id)
        if not session:
            return False
        session.approved = True
        session.status = "active"
        if permissions is not None:
            session.permissions = [p for p in permissions if p in PERMISSIONS]
        self._save()
        logger.info("Device approved: %s", _mask(device_id))
        return True

    def issue_token(self, device_id: str) -> Optional[str]:
        """Issue a new token for an approved device."""
        session = self._sessions.get(device_id)
        if not session or not session.approved:
            return None
        token = _generate_token()
        now = time.time()
        session.token_hash = _hash_token(token)
        session.issued_at = now
        session.expires_at = now + _TOKEN_TTL_SECONDS
        session.last_used = now
        session.status = "active"
        self._save()
        logger.info("Token issued for device: %s", _mask(device_id))
        return token

    def refresh_token(self, device_id: str, current_token: str) -> Optional[Dict[str, Any]]:
        """Refresh a token if past the refresh threshold."""
        session = self._sessions.get(device_id)
        if not session:
            return None
        expected_hash = _hash_token(current_token)
        if session.token_hash != expected_hash:
            logger.warning("Invalid token for device: %s", _mask(device_id))
            return None
        now = time.time()
        if now > session.expires_at:
            session.status = "expired"
            self._save()
            return None
        token_lifetime = session.expires_at - session.issued_at
        refresh_threshold = session.issued_at + token_lifetime * _TOKEN_REFRESH_THRESHOLD
        if now < refresh_threshold:
            return {
                "token": current_token,
                "expires_in": int(session.expires_at - now),
                "refreshed": False,
            }
        new_token = self.issue_token(device_id)
        if new_token:
            return {
                "token": new_token,
                "expires_in": _TOKEN_TTL_SECONDS,
                "refreshed": True,
            }
        return None

    def validate_token(self, device_id: str, token: str) -> bool:
        """Validate a token. Marks expired tokens as 'expired'."""
        session = self._sessions.get(device_id)
        if not session:
            return False
        if session.status != "active":
            return False
        if not session.approved:
            return False
        expected_hash = _hash_token(token)
        if session.token_hash != expected_hash:
            return False
        if time.time() > session.expires_at:
            session.status = "expired"
            self._save()
            return False
        return True

    def revoke_device(self, device_id: str) -> bool:
        """Revoke a device's access."""
        session = self._sessions.get(device_id)
        if not session:
            return False
        session.status = "revoked"
        self._save()
        logger.info("Device revoked: %s", _mask(device_id))
        return True

    def logout_device(self, device_id: str) -> bool:
        """Logout a device — expire its token."""
        session = self._sessions.get(device_id)
        if not session:
            return False
        session.status = "expired"
        self._save()
        logger.info("Device logged out: %s", _mask(device_id))
        return True

    def list_devices(self) -> List[Dict[str, Any]]:
        """List all devices with sanitized info."""
        return [s.to_dict() for s in self._sessions.values()]

    def get_device_info(self, device_id: str) -> Optional[Dict[str, Any]]:
        session = self._sessions.get(device_id)
        return session.to_dict() if session else None

    def cleanup_expired(self) -> int:
        """Remove expired/expired sessions."""
        now = time.time()
        expired = [
            dev_id for dev_id, s in self._sessions.items()
            if s.status == "expired" or now > s.expires_at
        ]
        for dev_id in expired:
            del self._sessions[dev_id]
        if expired:
            self._save()
        return len(expired)
