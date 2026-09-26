"""Evidence collection and anonymization for AURA Security Assessment.

Ensures all collected evidence is anonymized before storage.
Never stores raw IP addresses, hostnames, or credentials.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
HOSTNAME_PATTERN = re.compile(r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}\b")


@dataclass
class AnonymizedEvidence:
    """Evidence with sensitive data removed/anonymized."""
    original_hash: str
    anonymized_content: Dict[str, Any]
    anonymization_applied: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


class EvidenceCollector:
    """Collects and anonymizes security evidence.

    All evidence is anonymized before storage:
    - IPs are hashed (SHA-256 truncated to 16 hex chars)
    - Hostnames are tokenized (hash prefix)
    - Email addresses are removed
    - Credentials are stripped
    """

    def __init__(self, hash_salt: str = "aura-security-assessment"):
        self.hash_salt = hash_salt
        self._collected: List[AnonymizedEvidence] = []

    def _hash(self, value: str) -> str:
        """Hash a sensitive value for anonymization."""
        h = hashlib.sha256(f"{self.hash_salt}:{value}".encode()).hexdigest()
        return h[:16]

    def _redact_email(self, text: str) -> str:
        """Remove email addresses from text."""
        return EMAIL_PATTERN.sub("[EMAIL_REDACTED]", text)

    def _redact_credentials(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove credential fields from a dict."""
        credential_keys = {
            "password", "passwd", "secret", "api_key", "apikey",
            "token", "authorization", "auth", "cookie", "session",
            "private_key", "access_key", "secret_key",
        }
        redacted = {}
        for k, v in data.items():
            if any(ck in k.lower() for ck in credential_keys):
                redacted[k] = "[REDACTED]"
            elif isinstance(v, dict):
                redacted[k] = self._redact_credentials(v)
            elif isinstance(v, str):
                redacted[k] = self._redact_email(v)
            else:
                redacted[k] = v
        return redacted

    def _anonymize(self, data: Any, path: str = "") -> Any:
        """Recursively anonymize sensitive data in any structure."""
        if isinstance(data, str):
            result = data
            anonymizations = []

            if IP_PATTERN.search(result):
                result = IP_PATTERN.sub(lambda m: f"ip-{self._hash(m.group())}", result)
                anonymizations.append("ip_hashed")

            result = self._redact_email(result)
            if "[EMAIL_REDACTED]" in result:
                anonymizations.append("email_redacted")

            if HOSTNAME_PATTERN.search(result):
                result = HOSTNAME_PATTERN.sub(
                    lambda m: f"host-{self._hash(m.group())}.com",
                    result,
                )
                anonymizations.append("hostname_hashed")

            if anonymizations:
                return result, anonymizations
            return result, []

        if isinstance(data, dict):
            result = {}
            all_anonymizations = []
            for k, v in data.items():
                val, anon = self._anonymize(v, f"{path}.{k}")
                result[k] = val
                all_anonymizations.extend(anon)
            return result, all_anonymizations

        if isinstance(data, list):
            result = []
            all_anonymizations = []
            for i, item in enumerate(data):
                val, anon = self._anonymize(item, f"{path}[{i}]")
                result.append(val)
                all_anonymizations.extend(anon)
            return result, all_anonymizations

        return data, []

    def collect(self, evidence: Dict[str, Any], source: str = "unknown") -> AnonymizedEvidence:
        """Collect and anonymize evidence.

        Args:
            evidence: Raw evidence data
            source: Where the evidence came from

        Returns:
            AnonymizedEvidence with all sensitive data removed
        """
        content = dict(evidence)
        content["source"] = source

        content = self._redact_credentials(content)

        anonymized_content, anonymizations = self._anonymize(content)

        original_str = json_dumps(anonymized_content)
        original_hash = self._hash(original_str)

        record = AnonymizedEvidence(
            original_hash=original_hash,
            anonymized_content=anonymized_content,
            anonymization_applied=anonymizations if anonymizations else ["none_applied"],
        )

        self._collected.append(record)
        return record

    def get_all(self) -> List[AnonymizedEvidence]:
        """Get all collected anonymized evidence."""
        return self._collected

    def clear(self) -> None:
        """Clear all collected evidence."""
        self._collected.clear()

    def export_json(self, path: str) -> None:
        """Export all evidence to a JSON file."""
        import json
        from pathlib import Path
        data = [ev.to_dict() for ev in self._collected]
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


def json_dumps(data: Any) -> str:
    """Safe JSON serialization for hashing."""
    import json
    return json.dumps(data, sort_keys=True, default=str)
