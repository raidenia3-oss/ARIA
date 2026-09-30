"""Verification utilities for plugin marketplace.

Provides checksum and signature verification.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def verify_checksum(data: bytes | str, expected: str) -> bool:
    """Verify SHA256 checksum of data.

    Args:
        data: The data to verify (bytes or str).
        expected: Expected SHA256 hex digest.

    Returns:
        True if checksum matches, False otherwise.
    """
    if not expected:
        return True  # No checksum = skip verification
    if isinstance(data, str):
        data = data.encode()
    actual = hashlib.sha256(data).hexdigest()
    return actual == expected


def verify_file_checksum(file_path, expected: str) -> bool:
    """Verify SHA256 checksum of a file."""
    if not expected:
        return True
    path = Path(file_path)
    if not path.exists():
        return False
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest() == expected


def verify_signature(data: dict[str, Any], signature: str) -> bool:
    """Verify a registry signature.

    Uses HMAC-SHA256 with a shared secret for simplicity.
    Production would use RSA/Ed25519 with TUF-style keys.

    Args:
        data: The data that was signed.
        signature: The signature to verify (hex-encoded HMAC).

    Returns:
        True if signature is valid.
    """
    import os
    import hmac

    secret = os.environ.get("ARIA_REGISTRY_SECRET", "aria-dev-secret-change-me")
    message = json.dumps(data, sort_keys=True, separators=(",", ":"))
    expected = hmac.new(
        secret.encode(), message.encode(), hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature.strip())