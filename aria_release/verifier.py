"""TUF-style metadata verification and checksum integrity."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class MetadataVerifier:
    """Verifies TUF-style signed metadata chain."""

    def __init__(self, metadata_dir: Path) -> None:
        self.metadata_dir = Path(metadata_dir)
        self.root: dict = {}
        self.root_key: Optional[str] = None
        self._load_root()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def verify_metadata(self, metadata_type: str, data: dict) -> bool:
        """Verify a piece of TUF metadata.

        Checks:
        1. Signature is present
        2. Signature matches the root key (if available)
        3. Timestamp is monotonically increasing
        """
        if not data:
            logger.warning("Empty metadata for %s", metadata_type)
            return False

        # Check signature
        signature = data.get("signature")
        if not signature:
            logger.warning("No signature in %s metadata", metadata_type)
            return False

        if self.root_key:
            if not self._verify_signature(signature, data):
                logger.warning("Signature verification failed for %s", metadata_type)
                return False

        # Check timestamp monotonicity
        if metadata_type == "timestamp":
            if not self._check_monotonic_timestamp(data):
                logger.warning("Timestamp rollback detected")
                return False

        return True

    def verify_targets(self, targets_data: dict, expected_files: list[str]) -> dict[str, bool]:
        """Verify that all expected files are present in targets."""
        results = {}
        for filepath in expected_files:
            results[filepath] = filepath in targets_data.get("targets", {})
        return results

    def verify_checksum(self, file_path: Path, expected_sha256: str) -> bool:
        """Verify a file's SHA256 checksum."""
        return verify_checksum(file_path, expected_sha256)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _load_root(self) -> None:
        """Load the root.json trust anchor."""
        root_path = self.metadata_dir / "root.json"
        if not root_path.exists():
            logger.warning("root.json not found at %s", root_path)
            return

        try:
            with open(root_path) as f:
                self.root = json.load(f)
            self.root_key = self.root.get("keys", {}).get("root", {}).get("keyval", {}).get("public", "")
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load root.json: %s", exc)

    def _verify_signature(self, signature: str, data: dict) -> bool:
        """Verify a signature against the root key.

        Uses HMAC-style verification for simplicity. In production,
        this would use RSA/Ed25519 with cryptography library.
        """
        if not self.root_key:
            return True  # Can't verify without key, assume OK

        try:
            # Exclude the signature field itself from the message
            data_for_hash = {k: v for k, v in data.items() if k != "signature"}
            message = json.dumps(data_for_hash, sort_keys=True, separators=(",", ":"))
            expected = hashlib.sha256(
                (self.root_key + message).encode()
            ).hexdigest()
            return signature == expected
        except Exception:
            return False

    def _check_monotonic_timestamp(self, data: dict) -> bool:
        """Ensure timestamp version is monotonically increasing."""
        version = data.get("version", 0)
        last_path = self.metadata_dir / "last_timestamp_version.txt"

        if last_path.exists():
            try:
                last = int(last_path.read_text().strip())
                if version <= last:
                    return False
            except (ValueError, OSError):
                pass

        # Record this version
        try:
            last_path.write_text(str(version))
        except OSError:
            pass
        return True


def verify_checksum(file_path: Path, expected_sha256: str) -> bool:
    """Verify a file's SHA256 checksum."""
    if not expected_sha256:
        return True  # No checksum to verify against

    if not file_path.exists():
        return False

    sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        return sha256.hexdigest() == expected_sha256
    except OSError as exc:
        logger.warning("Checksum read failed: %s", exc)
        return False


def compute_checksum(file_path: Path) -> str:
    """Compute SHA256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()