"""Authorized scope validation for AURA Security Assessment.

Only allows reconnaissance against explicitly authorized targets.
Blocks all access to external/third-party IP ranges by default.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set
from urllib.parse import urlparse


LOCALHOST_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

BLOCKED_DOMAINS = {
    "hackerone.com",
    "hackerone.io",
    "bugcrowd.com",
    "synack.com",
    "yeswehack.com",
    "intigriti.com",
    "zerodium.com",
    "exploitee.rs",
}


@dataclass
class ScopeRule:
    """A single scope rule for an authorized target."""
    target: str
    target_type: str
    allowed: bool = True
    rationale: str = ""

    def matches(self, candidate: str) -> bool:
        """Check if candidate matches this scope rule."""
        if self.target_type == "domain":
            candidate_host = urlparse(candidate).hostname or candidate
            return candidate_host == self.target or candidate_host.endswith(f".{self.target}")
        if self.target_type == "cidr":
            try:
                net = ipaddress.ip_network(self.target, strict=False)
                addr = ipaddress.ip_address(urlparse(candidate).hostname or candidate)
                return addr in net
            except ValueError:
                return False
        if self.target_type == "ip":
            try:
                return ipaddress.ip_address(urlparse(candidate).hostname or candidate) == ipaddress.ip_address(self.target)
            except ValueError:
                return False
        if self.target_type == "url":
            return candidate.startswith(self.target)
        return False


@dataclass
class ScopePolicy:
    """Manages authorized scope for security assessments."""
    rules: List[ScopeRule] = field(default_factory=list)
    dry_run: bool = True
    max_requests_per_minute: int = 60
    allowed_methods: Set[str] = field(default_factory=lambda: {"GET", "HEAD", "OPTIONS"})
    allow_localhost: bool = True

    def add_target(self, target: str, target_type: str, rationale: str = "") -> None:
        """Add an authorized target to scope."""
        self.rules.append(ScopeRule(
            target=target,
            target_type=target_type,
            allowed=True,
            rationale=rationale,
        ))

    def is_authorized(self, target: str) -> bool:
        """Check if a target is within authorized scope."""
        if not self.rules:
            if self.allow_localhost and self._is_localhost(target):
                return True
            return False

        for rule in self.rules:
            if rule.matches(target):
                return rule.allowed

        if self.allow_localhost and self._is_localhost(target):
            return True

        return False

    def _is_localhost(self, target: str) -> bool:
        """Check if target is localhost."""
        host = urlparse(target).hostname or target
        try:
            addr = ipaddress.ip_address(host)
            for net in LOCALHOST_NETWORKS:
                if addr in net:
                    return True
            return False
        except ValueError:
            return host in ("localhost", "localhost.localdomain")

    def is_external(self, target: str) -> bool:
        """Check if target points to an external/third-party domain."""
        host = urlparse(target).hostname or target
        for blocked in BLOCKED_DOMAINS:
            if host == blocked or host.endswith(f".{blocked}"):
                return True
        return False

    def validate_request(self, target: str, method: str = "GET") -> tuple[bool, str]:
        """Validate a request against scope policy.

        Returns (allowed, reason).
        """
        if self.is_external(target):
            return False, f"External target '{target}' is blocked by policy"

        if method.upper() not in self.allowed_methods:
            return False, f"Method {method} not allowed (permitted: {self.allowed_methods})"

        if not self.is_authorized(target):
            return False, f"Target '{target}' is not in authorized scope"

        if self.dry_run:
            return True, "DRY RUN: authorized but not executed"

        return True, "Authorized"


def load_scope_from_env(env_path: Optional[str] = None) -> ScopePolicy:
    """Load scope policy from environment configuration."""
    policy = ScopePolicy()

    env_file = Path(env_path) if env_path else Path(".env.security")
    if not env_file.exists():
        env_file = Path(".env")

    if env_file.exists():
        import os
        from pathlib import Path as P

        content = P(env_file).read_text(encoding="utf-8", errors="ignore")
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("SECURITY_ALLOW_"):
                key, _, value = line.partition("=")
                target = value.strip().strip("'\"")
                if target:
                    target_type = "domain" if re.match(r"^[a-z]+\.[a-z]+", target) else "cidr"
                    policy.add_target(
                        target=target,
                        target_type=target_type,
                        rationale=f"From {key}",
                    )
            elif line.startswith("SECURITY_DRY_RUN="):
                val = line.split("=", 1)[1].strip().lower()
                policy.dry_run = val in ("true", "1", "yes")

    return policy


def default_policy() -> ScopePolicy:
    """Create a default policy that only allows localhost."""
    return ScopePolicy(
        rules=[],
        dry_run=True,
        max_requests_per_minute=60,
        allowed_methods={"GET", "HEAD", "OPTIONS"},
        allow_localhost=True,
    )
