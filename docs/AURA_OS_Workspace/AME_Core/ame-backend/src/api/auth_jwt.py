"""Auth helper for JWT validation."""

import os
import time
from typing import Optional
import jwt  # PyJWT

JWT_SECRET = os.getenv("JWT_SECRET", "ame-bridge-jwt-secret-key-change-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRES_MINUTES = int(os.getenv("JWT_EXPIRES_MINUTES", "60"))


def create_token(payload: dict, expires_minutes: Optional[int] = None) -> str:
    """Create a signed JWT token."""
    exp = time.time() + (expires_minutes or JWT_EXPIRES_MINUTES) * 60
    payload = dict(payload)
    payload.setdefault("exp", exp)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and verify a JWT token."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
