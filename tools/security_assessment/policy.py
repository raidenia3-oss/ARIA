"""Policy enforcement for AURA Security Assessment.

Enforces dry-run mode, rate limits, and scope blocking.
All active tests require explicit approval via Discord webhook.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse

from tools.security_assessment.scope import ScopePolicy, BLOCKED_DOMAINS, LOCALHOST_NETWORKS

import ipaddress


class Action(str, Enum):
    """Available assessment actions."""
    RECON = "recon"
    HEADERS = "headers"
    DNS = "dns"
    SSL = "ssl"
    SCAN = "scan"
    EXPLOIT = "exploit"  # NEVER allowed


class EnforcementResult:
    """Result of enforcing a policy on an action."""
    def __init__(self, allowed: bool, reason: str, action: Action, target: str):
        self.allowed = allowed
        self.reason = reason
        self.action = action
        self.target = target

    def __bool__(self) -> bool:
        return self.allowed


@dataclass
class RateLimitState:
    """Rate limit tracking per target."""
    requests: List[float] = field(default_factory=list)
    last_request: float = 0.0


class PolicyEnforcer:
    """Enforces security assessment policies.

    Rules:
    1. dry_run=True always — no actions executed without explicit override
    2. Rate limited per target (default 60 req/min)
    3. No external targets (only localhost/allowlist)
    4. No exploit actions ever
    5. All actions logged for audit
    """

    MAX_REQUESTS_PER_MINUTE = 60
    MAX_BURST = 10

    def __init__(self, policy: Optional[ScopePolicy] = None):
        self.policy = policy or ScopePolicy()
        self._rate_limits: Dict[str, RateLimitState] = {}
        self._audit_log: List[Dict] = []

        env_dry = os.getenv("SECURITY_DRY_RUN", "").lower()
        if env_dry in ("true", "1", "yes"):
            self.dry_run = True
        elif env_dry in ("false", "0", "no"):
            self.dry_run = False
        else:
            self.dry_run = self.policy.dry_run
        env_limit = os.getenv("SECURITY_RATE_LIMIT", "")
        if env_limit:
            self.max_requests = int(env_limit)
        else:
            self.max_requests = self.policy.max_requests_per_minute
        self.approval_webhook = os.getenv("DISCORD_APPROVAL_WEBHOOK", "")
        self.approval_required = os.getenv("SECURITY_REQUIRES_APPROVAL", "true").lower() in ("true", "1", "yes")

    def validate(self, action: Action, target: str) -> EnforcementResult:
        """Validate an action against all policies.

        Args:
            action: The action to validate
            target: The target URL/IP

        Returns:
            EnforcementResult with allowed status and reason
        """
        if action == Action.EXPLOIT:
            result = EnforcementResult(
                allowed=False,
                reason="Exploit actions are never allowed",
                action=action,
                target=target,
            )
            self._log(result)
            return result

        is_external = self._is_external_target(target)
        if is_external:
            return EnforcementResult(
                allowed=False,
                reason=f"External target blocked: {target}",
                action=action,
                target=target,
            )

        if not self.policy.is_authorized(target):
            return EnforcementResult(
                allowed=False,
                reason=f"Target not in authorized scope: {target}",
                action=action,
                target=target,
            )

        if not self._check_rate_limit(target):
            result = EnforcementResult(
                allowed=False,
                reason=f"Rate limit exceeded for {target}",
                action=action,
                target=target,
            )
            self._log(result)
            return result

        if self.dry_run:
            result = EnforcementResult(
                allowed=True,
                reason=f"DRY RUN: {action.value} authorized but not executed",
                action=action,
                target=target,
            )
            self._log(result)
            return result

        if self.approval_required and action in (Action.SCAN,):
            result = EnforcementResult(
                allowed=False,
                reason=f"Action '{action.value}' requires manual approval via webhook",
                action=action,
                target=target,
            )
            self._log(result)
            return result

        return EnforcementResult(
            allowed=True,
            reason=f"Authorized: {action.value} on {target}",
            action=action,
            target=target,
        )

    def _is_external_target(self, target: str) -> bool:
        """Check if target is an external/third-party address."""
        host = urlparse(target).hostname or target

        for blocked in BLOCKED_DOMAINS:
            if host == blocked or host.endswith(f".{blocked}"):
                return True

        try:
            addr = ipaddress.ip_address(host)
            for net in LOCALHOST_NETWORKS:
                if addr in net:
                    return False
            return True  # Non-local IP is external
        except ValueError:
            pass

        if self.policy.allow_localhost and self.policy._is_localhost(target):
            return False

        for rule in self.policy.rules:
            if rule.matches(target):
                return False

        return True

    def _check_rate_limit(self, target: str) -> bool:
        """Check and update rate limit for a target."""
        now = time.time()
        state = self._rate_limits.get(target, RateLimitState())

        if state.last_request and (now - state.last_request) > 60:
            state.requests = []

        state.requests = [t for t in state.requests if now - t < 60]

        if len(state.requests) >= self.max_requests:
            return False

        state.requests.append(now)
        state.last_request = now
        self._rate_limits[target] = state
        return True

    def _log(self, result: EnforcementResult) -> None:
        """Log an enforcement decision."""
        self._audit_log.append({
            "timestamp": time.time(),
            "action": result.action.value,
            "target": result.target,
            "allowed": result.allowed,
            "reason": result.reason,
        })

    def get_audit_log(self) -> List[Dict]:
        """Get the audit log of all enforcement decisions."""
        return self._audit_log

    def get_stats(self) -> Dict:
        """Get policy enforcement statistics."""
        total = len(self._audit_log)
        allowed = sum(1 for entry in self._audit_log if entry["allowed"])
        blocked = total - allowed

        return {
            "total_requests": total,
            "allowed": allowed,
            "blocked": blocked,
            "dry_run": self.dry_run,
            "max_requests_per_minute": self.max_requests,
            "approval_required": self.approval_required,
        }

    def request_approval(self, action: Action, target: str, reason: str = "") -> bool:
        """Request manual approval via Discord webhook.

        In dry-run mode, always returns False (no external requests).
        """
        if not self.approval_webhook:
            return not self.dry_run

        # Never make external requests in dry_run mode
        if self.dry_run:
            self._log(EnforcementResult(
                allowed=False,
                reason=f"DRY RUN: approval would be requested via webhook",
                action=action,
                target=target,
            ))
            return False

        try:
            import httpx

            payload = {
                "content": f"🔒 **Security Assessment Approval Required**",
                "embeds": [{
                    "title": "Approval Request",
                    "fields": [
                        {"name": "Action", "value": action.value, "inline": True},
                        {"name": "Target", "value": target, "inline": True},
                        {"name": "Reason", "value": reason or "N/A", "inline": False},
                    ],
                    "color": 0xff9900,
                }],
            }

            response = httpx.post(
                self.approval_webhook,
                json=payload,
                timeout=5.0,
            )

            self._log(EnforcementResult(
                allowed=response.status_code == 204,
                reason=f"Approval webhook response: {response.status_code}",
                action=action,
                target=target,
            ))
            return response.status_code == 204

        except Exception as exc:
            self._log(EnforcementResult(
                allowed=False,
                reason=f"Approval request failed: {exc}",
                action=action,
                target=target,
            ))
            return False


def create_default_policy() -> ScopePolicy:
    """Create the default scope policy for AURA local assessment."""
    policy = ScopePolicy(
        dry_run=True,
        max_requests_per_minute=60,
        allowed_methods={"GET", "HEAD", "OPTIONS"},
        allow_localhost=True,
    )
    policy.add_target(
        target="localhost",
        target_type="domain",
        rationale="Local AURA OS assessment",
    )
    policy.add_target(
        target="127.0.0.1",
        target_type="ip",
        rationale="Local loopback",
    )
    return policy
