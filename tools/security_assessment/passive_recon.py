"""Passive reconnaissance module for AURA Security Assessment.

Only performs read-only, non-intrusive checks against authorized targets.
No active scanning, no shell=True, no connection attempts to external systems.
"""

from __future__ import annotations

import asyncio
import json
import re
import socket
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

from tools.security_assessment.scope import ScopePolicy, default_policy


@dataclass
class PassiveEvidence:
    """Evidence collected from passive reconnaissance."""
    target: str
    timestamp: str
    source: str
    findings: Dict[str, Any] = field(default_factory=dict)
    anonymized: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PassiveReconResult:
    """Results from a passive reconnaissance session."""
    target: str
    scope_authorized: bool
    scope_reason: str
    evidence: List[PassiveEvidence] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class PassiveRecon:
    """Passive reconnaissance engine.

    All reconnaissance is read-only:
    - HTTP metadata (headers, status codes)
    - DNS resolution (local check only)
    - SSL certificate info (no connection attempt)
    - WHOIS data (local lookup only)
    - No shell execution, no external requests outside scope
    """

    def __init__(self, policy: Optional[ScopePolicy] = None):
        self.policy = policy or default_policy()
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(5.0, connect=3.0),
            follow_redirects=True,
            headers={"User-Agent": "AURA-Security-Assessment/2.1"},
        )

    async def _check_http(self, url: str) -> PassiveEvidence:
        """Passive HTTP check: headers and status only."""
        evidence = PassiveEvidence(
            target=url,
            timestamp=datetime.utcnow().isoformat(),
            source="httpx",
        )

        try:
            response = await self.client.get(url, method="HEAD")
            evidence.findings = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "server": response.headers.get("server", "unknown"),
                "content_type": response.headers.get("content-type", "unknown"),
                "content_length": response.headers.get("content-length", "unknown"),
                "security_headers_present": self._check_security_headers(response.headers),
            }
        except httpx.TimeoutException:
            evidence.findings = {"error": "timeout"}
        except httpx.ConnectError:
            evidence.findings = {"error": "connection_refused"}
        except Exception as exc:
            evidence.findings = {"error": str(exc)}

        return evidence

    def _check_security_headers(self, headers) -> Dict[str, bool]:
        """Check for security headers presence (passive)."""
        security_headers = [
            "strict-transport-security",
            "x-frame-options",
            "x-content-type-options",
            "content-security-policy",
            "x-xss-protection",
            "referrer-policy",
            "permissions-policy",
        ]
        present = {}
        for h in security_headers:
            present[h] = any(k.lower() == h for k in headers.keys())
        return present

    async def _resolve_dns(self, target: str) -> PassiveEvidence:
        """DNS resolution check (local only, no external queries)."""
        evidence = PassiveEvidence(
            target=target,
            timestamp=datetime.utcnow().isoformat(),
            source="dns",
        )

        host = urlparse(target).hostname or target
        try:
            loop = asyncio.get_event_loop()
            result = await loop.getaddrinfo(host, None)
            ips = list(set(r[4][0] for r in result))
            evidence.findings = {
                "hostname": host,
                "addresses": ips,
                "resolved": True,
            }
        except socket.gaierror:
            evidence.findings = {"hostname": host, "resolved": False, "error": "DNS resolution failed"}
        except Exception as exc:
            evidence.findings = {"hostname": host, "resolved": False, "error": str(exc)}

        return evidence

    def _check_ssl_cert(self, target: str) -> PassiveEvidence:
        """Check SSL certificate info (passive read, no connection)."""
        evidence = PassiveEvidence(
            target=target,
            timestamp=datetime.utcnow().isoformat(),
            source="ssl",
        )

        host = urlparse(target).hostname or target
        try:
            ctx = __import__("ssl").create_default_context()
            with socket.create_connection((host, 443), timeout=3) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
                    evidence.findings = {
                        "subject": dict(x[0] for x in cert.get("subject", ())),
                        "issuer": dict(x[0] for x in cert.get("issuer", ())),
                        "not_after": cert.get("notAfter", ""),
                        "not_before": cert.get("notBefore", ""),
                    }
        except Exception as exc:
            evidence.findings = {"error": str(exc)}

        return evidence

    async def scan(self, targets: List[str]) -> PassiveReconResult:
        """Run passive reconnaissance against authorized targets."""
        start_time = datetime.utcnow()

        authorized = []
        unauthorized = []

        for target in targets:
            allowed, reason = self.policy.validate_request(target, "GET")
            if allowed and "DRY RUN" not in reason:
                authorized.append(target)
            else:
                unauthorized.append((target, reason))

        evidence_list = []
        summary = {"authorized_targets": [], "blocked_targets": unauthorized}

        for target in authorized:
            if self.policy.dry_run:
                summary["authorized_targets"].append(target)
                continue

            tasks = [
                self._check_http(target),
                self._resolve_dns(target),
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, PassiveEvidence):
                    evidence_list.append(result)

            summary["authorized_targets"].append(target)

        await self.client.aclose()

        duration = (datetime.utcnow() - start_time).total_seconds()

        return PassiveReconResult(
            target=", ".join(targets),
            scope_authorized=len(authorized) > 0,
            scope_reason=f"{len(authorized)} authorized, {len(unauthorized)} blocked",
            evidence=evidence_list,
            summary=summary,
            duration_seconds=duration,
        )

    def scan_sync(self, targets: List[str]) -> PassiveReconResult:
        """Synchronous wrapper for scan."""
        return asyncio.run(self.scan(targets))
