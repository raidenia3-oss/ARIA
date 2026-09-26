"""Security manager for AURA."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import jwt
from cryptography.fernet import Fernet

from backend.database import SessionLocal
from backend.models import APIKey as APIKeyModel
from backend.models import SecurityEvent as SecurityEventModel


class SecurityLevel(str, Enum):
    PUBLIC = "public"
    USER = "user"
    ADMIN = "admin"
    SYSTEM = "system"


class RateLimitType(str, Enum):
    GLOBAL = "global"
    USER = "user"
    ENDPOINT = "endpoint"
    ADAPTIVE = "adaptive"


@dataclass
class APIKey:
    key_id: str
    key_hash: str
    user_id: str
    created_at: str
    last_used: Optional[str]
    expires_at: Optional[str]
    permissions: List[str]
    rate_limit: int
    is_active: bool


@dataclass
class SecurityEvent:
    event_type: str
    timestamp: str
    ip_address: str
    user_id: Optional[str]
    endpoint: str
    status: str
    reason: Optional[str]
    severity: str


class EncryptionManager:
    def __init__(self, master_key: Optional[str] = None) -> None:
        if master_key:
            self.cipher = Fernet(master_key.encode())
        else:
            self.cipher = Fernet(Fernet.generate_key())

    def encrypt(self, data: str) -> str:
        if not data:
            return ""
        return self.cipher.encrypt(data.encode()).decode()

    def decrypt(self, encrypted_data: str) -> str:
        if not encrypted_data:
            return ""
        return self.cipher.decrypt(encrypted_data.encode()).decode()

    def hash_password(self, password: str) -> str:
        salt = secrets.token_hex(16)
        hash_obj = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
        return f"{salt}${hash_obj.hex()}"

    def verify_password(self, password: str, hash_stored: str) -> bool:
        salt, hash_stored_hex = hash_stored.split("$", 1)
        hash_obj = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
        return hmac.compare_digest(hash_obj.hex(), hash_stored_hex)


class RateLimiter:
    def __init__(self) -> None:
        self.limits: Dict[str, List[Tuple[datetime, int]]] = {}
        self.blocked_ips: set = set()

    async def check_rate_limit(
        self,
        key: str,
        limit_type: RateLimitType,
        max_requests: int = 100,
    ) -> Tuple[bool, int]:
        now = datetime.now()
        window_key = f"{limit_type.value}:{key}"

        if window_key not in self.limits:
            self.limits[window_key] = []

        self.limits[window_key] = [
            (ts, cnt)
            for ts, cnt in self.limits[window_key]
            if (now - ts).total_seconds() < 60
        ]

        current_count = sum(cnt for _, cnt in self.limits[window_key])

        if current_count >= max_requests:
            await self._handle_limit_exceeded(key, limit_type)
            return False, 0

        self.limits[window_key].append((now, 1))
        return True, max(0, max_requests - current_count - 1)

    async def _handle_limit_exceeded(self, key: str, limit_type: RateLimitType) -> None:
        if limit_type == RateLimitType.GLOBAL:
            self.blocked_ips.add(key)
            print(f"Security: blocked IP {key}")

    def is_blocked(self, ip: str) -> bool:
        return ip in self.blocked_ips


class DDosDetector:
    def __init__(self) -> None:
        self.request_history: Dict[str, List[datetime]] = {}
        self.threshold = 1000

    async def check_for_ddos(self, ip: str) -> Tuple[bool, str]:
        now = datetime.now()
        if ip not in self.request_history:
            self.request_history[ip] = []

        self.request_history[ip] = [
            ts for ts in self.request_history[ip] if (now - ts).total_seconds() < 60
        ]
        self.request_history[ip].append(now)
        request_count = len(self.request_history[ip])

        if request_count > self.threshold:
            return True, f"Excessive requests: {request_count}/min"

        recent = len([ts for ts in self.request_history[ip] if (now - ts).total_seconds() < 1])
        if recent > 50:
            return True, f"Spike detected: {recent} req/sec"

        return False, ""


class AuthenticationManager:
    def __init__(self, encryption: EncryptionManager) -> None:
        self.encryption = encryption
        self.jwt_secret = secrets.token_urlsafe(32)
        self.mfa_cache: Dict[str, Dict[str, Any]] = {}

    async def generate_jwt(self, user_id: str, expires_in_hours: int = 24) -> str:
        payload = {
            "user_id": user_id,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=expires_in_hours),
        }
        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")

    async def verify_jwt(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            return jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
        except Exception:
            return None

    async def send_mfa_code(self, user_id: str, user_email: str) -> bool:
        code = secrets.randbelow(999999)
        code_str = f"{code:06d}"
        self.mfa_cache[user_id] = {
            "code": code_str,
            "expires": datetime.now() + timedelta(minutes=5),
        }
        print(f"Security: MFA code for {user_email}: {code_str}")
        return True

    async def verify_mfa_code(self, user_id: str, code: str) -> bool:
        if user_id not in self.mfa_cache:
            return False
        cache_data = self.mfa_cache[user_id]
        if datetime.now() > cache_data["expires"]:
            del self.mfa_cache[user_id]
            return False
        is_valid = hmac.compare_digest(code, cache_data["code"])
        if is_valid:
            del self.mfa_cache[user_id]
        return is_valid


class SecurityAuditor:
    def __init__(self, db_session_factory) -> None:
        self.db_session_factory = db_session_factory
        self.alerts_threshold = {
            "failed_login": 5,
            "rate_limit_exceeded": 10,
            "ddos_alert": 1,
        }

    async def log_security_event(self, event: SecurityEvent) -> None:
        db = SessionLocal()
        try:
            row = SecurityEventModel(
                event_type=event.event_type,
                timestamp=datetime.fromisoformat(event.timestamp).timestamp(),
                ip_address=event.ip_address,
                user_id=event.user_id,
                endpoint=event.endpoint,
                status=event.status,
                reason=event.reason,
                severity=event.severity,
            )
            db.add(row)
            db.commit()
        finally:
            db.close()

    async def get_recent_security_events(self, limit: int = 100):
        db = SessionLocal()
        try:
            return (
                db.query(SecurityEventModel)
                .order_by(SecurityEventModel.timestamp.desc())
                .limit(limit)
                .all()
            )
        finally:
            db.close()


class APIKeyManager:
    def __init__(self, encryption: EncryptionManager) -> None:
        self.encryption = encryption

    async def generate_api_key(
        self, user_id: str, name: str, permissions: List[str]
    ) -> str:
        key = secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        api_key = APIKey(
            key_id=secrets.token_hex(8),
            key_hash=key_hash,
            user_id=user_id,
            created_at=datetime.now().isoformat(),
            last_used=None,
            expires_at=(datetime.now() + timedelta(days=90)).isoformat(),
            permissions=permissions,
            rate_limit=1000,
            is_active=True,
        )
        db = SessionLocal()
        try:
            row = APIKeyModel(
                key_id=api_key.key_id,
                key_hash=api_key.key_hash,
                user_id=api_key.user_id,
                created_at=datetime.fromisoformat(api_key.created_at).timestamp(),
                last_used=None,
                expires_at=datetime.fromisoformat(api_key.expires_at).timestamp()
                if api_key.expires_at
                else None,
                permissions=",".join(api_key.permissions),
                rate_limit=api_key.rate_limit,
                is_active=api_key.is_active,
            )
            db.add(row)
            db.commit()
        finally:
            db.close()
        return key

    async def verify_api_key(self, key: str) -> Optional[APIKey]:
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        db = SessionLocal()
        try:
            row = db.query(APIKeyModel).filter(APIKeyModel.key_hash == key_hash).first()
            if not row or not row.is_active:
                return None
            return APIKey(
                key_id=row.key_id,
                key_hash=row.key_hash,
                user_id=row.user_id,
                created_at=datetime.fromtimestamp(row.created_at).isoformat(),
                last_used=datetime.fromtimestamp(row.last_used).isoformat() if row.last_used else None,
                expires_at=datetime.fromtimestamp(row.expires_at).isoformat() if row.expires_at else None,
                permissions=row.permissions.split(","),
                rate_limit=row.rate_limit,
                is_active=row.is_active,
            )
        finally:
            db.close()

    async def rotate_api_key(self, old_key: str) -> Optional[str]:
        key_hash = hashlib.sha256(old_key.encode()).hexdigest()
        db = SessionLocal()
        try:
            row = db.query(APIKeyModel).filter(APIKeyModel.key_hash == key_hash).first()
            if not row:
                return None
            new_key = secrets.token_urlsafe(32)
            new_key_hash = hashlib.sha256(new_key.encode()).hexdigest()
            row.key_hash = new_key_hash
            row.key_id = secrets.token_hex(8)
            row.expires_at = (datetime.now() + timedelta(days=90)).timestamp()
            db.commit()
            return new_key
        finally:
            db.close()


class SecurityManager:
    def __init__(self, db_session_factory) -> None:
        self.db_session_factory = db_session_factory
        self.encryption = EncryptionManager()
        self.rate_limiter = RateLimiter()
        self.ddos_detector = DDosDetector()
        self.auth_manager = AuthenticationManager(self.encryption)
        self.auditor = SecurityAuditor(db_session_factory)
        self.api_key_manager = APIKeyManager(self.encryption)

    async def validate_request(
        self,
        ip: str,
        endpoint: str,
        auth_token: Optional[str] = None,
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        is_ddos, ddos_reason = await self.ddos_detector.check_for_ddos(ip)
        if is_ddos:
            await self.auditor.log_security_event(
                SecurityEvent(
                    event_type="ddos_detected",
                    timestamp=datetime.now().isoformat(),
                    ip_address=ip,
                    user_id=None,
                    endpoint=endpoint,
                    status="blocked",
                    reason=ddos_reason,
                    severity="critical",
                )
            )
            return False, "DDoS detected", {}

        allowed, remaining = await self.rate_limiter.check_rate_limit(
            key=ip, limit_type=RateLimitType.GLOBAL, max_requests=1000
        )
        if not allowed:
            await self.auditor.log_security_event(
                SecurityEvent(
                    event_type="rate_limit_exceeded",
                    timestamp=datetime.now().isoformat(),
                    ip_address=ip,
                    user_id=None,
                    endpoint=endpoint,
                    status="blocked",
                    reason="Rate limit exceeded",
                    severity="warning",
                )
            )
            return False, "Rate limit exceeded", {}

        user_id = None
        if auth_token:
            payload = await self.auth_manager.verify_jwt(auth_token)
            if payload:
                user_id = payload.get("user_id")

        return True, None, {"user_id": user_id, "remaining_requests": remaining}

    async def get_security_dashboard(self) -> Dict[str, Any]:
        recent_events = await self.auditor.get_recent_security_events(limit=50)
        critical_events = [e for e in recent_events if e.severity == "critical"]
        warning_events = [e for e in recent_events if e.severity == "warning"]
        return {
            "total_events_24h": len(recent_events),
            "critical_alerts": len(critical_events),
            "warnings": len(warning_events),
            "blocked_ips": list(self.rate_limiter.blocked_ips),
            "recent_alerts": [
                {
                    "type": e.event_type,
                    "ip": e.ip_address,
                    "endpoint": e.endpoint,
                    "severity": e.severity,
                    "timestamp": datetime.fromtimestamp(e.timestamp).isoformat(),
                }
                for e in critical_events[:10]
            ],
        }
