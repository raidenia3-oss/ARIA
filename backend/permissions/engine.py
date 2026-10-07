"""Permission engine for AURA agent tools.

Adopted from tama96 (MIT) and coucou (MIT, Mochi character excluded):
- Kill switch maestro (allow_all toggle)
- allow/deny por herramienta
- risk tiers con prompt obligatorio
- fail-closed: sin config, todo deny
- config en ~/.aura/permissions.json
- Modo "ask": aprobación humana con request_id, hash args, TTL 120s, single-use
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("AURA.Permissions")

# Risk tiers: safe -> low -> medium -> high -> critical
RISK_ORDER = ["safe", "low", "medium", "high", "critical"]
RISK_INDEX = {r: i for i, r in enumerate(RISK_ORDER)}

# Ask mode constants
ASK_TTL_SECONDS = 120
ASK_CLEANUP_INTERVAL = 300


@dataclass
class ToolPermission:
    """Permission rule for a single tool."""
    tool: str
    allow: bool = False
    risk: str = "safe"
    require_confirm: bool = False
    max_calls_per_minute: Optional[int] = None
    allowed_args: Optional[Dict[str, List[str]]] = None  # arg -> allowed values
    explicitly_denied: bool = False  # deny wins over allow


@dataclass
class PermissionConfig:
    """Full permission configuration."""
    allow_all: bool = False  # Kill switch - bypass all checks
    default_allow: bool = False  # Fail-closed: False = deny by default
    tools: Dict[str, ToolPermission] = field(default_factory=dict)
    risk_threshold: str = "medium"  # Tools above this require confirm
    global_rate_limit: Optional[int] = None  # calls per minute across all tools
    auth_token_hash: Optional[str] = None  # sha256 hash of auth token for approve/deny

    def get_tool_perm(self, tool: str) -> ToolPermission:
        return self.tools.get(tool, ToolPermission(tool=tool))

    def tool_allowed(self, tool: str, risk: str) -> bool:
        """Check if tool is allowed considering risk tier."""
        if self.allow_all:
            return True
        perm = self.get_tool_perm(tool)
        if not perm.allow:
            return False
        if RISK_INDEX.get(risk, 0) > RISK_INDEX.get(self.risk_threshold, 2):
            return False
        return True

    def tool_requires_confirm(self, tool: str, risk: str) -> bool:
        """Check if tool execution requires user confirmation."""
        if self.allow_all:
            return False
        perm = self.get_tool_perm(tool)
        if perm.require_confirm:
            return True
        return RISK_INDEX.get(risk, 0) > RISK_INDEX.get(self.risk_threshold, 2)


@dataclass
class AskRequest:
    """Pending human approval request."""
    request_id: str
    tool: str
    risk: str
    args_hash: str  # sha256 of canonical args
    args_canonical: str  # JSON string for audit (no secrets)
    created_at: float
    expires_at: float
    decided: bool = False
    decision: Optional[bool] = None  # True=approve, False=deny
    decided_at: Optional[float] = None
    decided_by: Optional[str] = None  # token hash for audit


class PermissionEngine:
    """Fail-closed permission engine for agent tool execution."""

    CONFIG_PATH = Path.home() / ".aura" / "permissions.json"
    ASK_STORE_PATH = Path.home() / ".aura" / "ask_requests.json"

    def __init__(self, config: Optional[PermissionConfig] = None):
        self.config = config or self._load_config()
        # Apply default policy if no tools configured
        if not self.config.tools:
            self._apply_default_policy()
        self._call_counts: Dict[str, List[float]] = {}
        self._ask_requests: Dict[str, AskRequest] = {}
        self._ask_lock = threading.RLock()
        self._load_ask_store()
        self._start_ask_cleanup()

    def _apply_default_policy(self) -> None:
        """Apply the 13-tool default policy:
        - 11 read-only tools = allow (safe)
        - 2 write tools = ask (medium, require_confirm)
        """
        readonly_tools = [
            ("notes.markdown.render_heading", "safe"),
            ("notes.sys.timestamp", "safe"),
            ("numeric.compute.average", "safe"),
            ("numeric.compute.clamp", "safe"),
            ("numeric.compute.percent", "safe"),
            ("research.engine.status", "safe"),
            ("research.missions.get", "safe"),
            ("research.missions.list", "safe"),
            ("text.utils.count_words", "safe"),
            ("text.utils.slugify", "safe"),
            ("text.utils.split_lines", "safe"),
        ]
        for tool, risk in readonly_tools:
            self.config.tools[tool] = ToolPermission(tool=tool, allow=True, risk=risk)

        write_tools = [
            ("notes.local.write", "medium"),
            ("research.missions.start", "medium"),
        ]
        for tool, risk in write_tools:
            self.config.tools[tool] = ToolPermission(
                tool=tool, allow=True, risk=risk, require_confirm=True
            )
        self.save_config()

    @classmethod
    def _load_config(cls) -> PermissionConfig:
        """Load config from ~/.aura/permissions.json. Fail-closed defaults."""
        try:
            if cls.CONFIG_PATH.exists():
                with open(cls.CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                tools_data = data.get("tools") or {}
                return PermissionConfig(
                    allow_all=data.get("allow_all", False),
                    default_allow=data.get("default_allow", False),
                    risk_threshold=data.get("risk_threshold", "medium"),
                    global_rate_limit=data.get("global_rate_limit"),
                    auth_token_hash=data.get("auth_token_hash"),
                    tools={
                        name: ToolPermission(
                            tool=name,
                            allow=rule.get("allow", False),
                            risk=rule.get("risk", "safe"),
                            require_confirm=rule.get("require_confirm", False),
                            max_calls_per_minute=rule.get("max_calls_per_minute"),
                            allowed_args=rule.get("allowed_args"),
                            explicitly_denied=rule.get("explicitly_denied", False),
                        )
                        for name, rule in tools_data.items()
                    },
                )
        except Exception as exc:
            logger.warning("Failed to load permissions config: %s", exc)
        return PermissionConfig()

    def save_config(self) -> None:
        """Persist current config to disk."""
        self.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "allow_all": self.config.allow_all,
            "default_allow": self.config.default_allow,
            "risk_threshold": self.config.risk_threshold,
            "global_rate_limit": self.config.global_rate_limit,
            "auth_token_hash": self.config.auth_token_hash,
            "tools": {
                name: {
                    "allow": perm.allow,
                    "risk": perm.risk,
                    "require_confirm": perm.require_confirm,
                    "max_calls_per_minute": perm.max_calls_per_minute,
                    "allowed_args": perm.allowed_args,
                    "explicitly_denied": perm.explicitly_denied,
                }
                for name, perm in self.config.tools.items()
            },
        }
        with open(self.CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _canonical_args(self, args: Optional[Dict[str, Any]]) -> str:
        """Create canonical JSON string for hashing (sorted keys, no secrets)."""
        if not args:
            return "{}"
        # Redact potential secrets in args for audit log
        safe_args = {}
        for k, v in args.items():
            kl = k.lower()
            if any(s in kl for s in ("token", "password", "secret", "key", "auth", "credential")):
                safe_args[k] = "[REDACTED]"
            else:
                safe_args[k] = v
        return json.dumps(safe_args, sort_keys=True, separators=(",", ":"))

    def _args_hash(self, args: Optional[Dict[str, Any]]) -> str:
        """SHA256 of canonical args."""
        canon = self._canonical_args(args)
        return hashlib.sha256(canon.encode()).hexdigest()

    def check(
        self,
        tool: str,
        risk: str = "safe",
        args: Optional[Dict[str, Any]] = None,
        require_user_confirm: bool = False,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Check if tool execution is permitted.

        Returns: (allowed, reason_if_denied, request_id_if_ask)
        - allowed=True, reason=None, request_id=None → proceed
        - allowed=False, reason=str, request_id=None → hard deny
        - allowed=False, reason=str, request_id=str → ask mode (pending approval)
        """
        # Kill switch
        if self.config.allow_all:
            return True, None, None

        perm = self.config.get_tool_perm(tool)

        # Explicit deny (deny wins over allow)
        if perm.explicitly_denied:
            return False, f"tool '{tool}' explicitly denied", None

        # Default deny (fail-closed)
        if not perm.allow and not self.config.default_allow:
            return False, f"tool '{tool}' not in allowlist (fail-closed)", None

        # Explicit deny (allow=False but not explicitly_denied)
        if not perm.allow:
            return False, f"tool '{tool}' explicitly denied", None

        # Risk threshold - if exceeded, require confirmation (ask mode) instead of hard deny
        risk_exceeds = RISK_INDEX.get(risk, 0) > RISK_INDEX.get(self.config.risk_threshold, 2)

        # Arg allowlist
        if perm.allowed_args and args:
            for arg_name, allowed_values in perm.allowed_args.items():
                if arg_name in args and str(args[arg_name]) not in allowed_values:
                    return False, f"argument '{arg_name}' value not in allowlist for tool '{tool}'", None

        # Rate limit per tool
        if perm.max_calls_per_minute:
            if not self._check_rate_limit(tool, perm.max_calls_per_minute):
                return False, f"tool '{tool}' rate limit exceeded ({perm.max_calls_per_minute}/min)", None

        # Global rate limit
        if self.config.global_rate_limit:
            if not self._check_rate_limit("_global", self.config.global_rate_limit):
                return False, f"global rate limit exceeded ({self.config.global_rate_limit}/min)", None

        # Confirmation required → ASK mode
        needs_confirm = require_user_confirm or perm.require_confirm or risk_exceeds
        if needs_confirm:
            request_id = self._create_ask_request(tool, risk, args)
            return False, f"tool '{tool}' requires human approval (risk: {risk})", request_id

        return True, None, None

    def _create_ask_request(self, tool: str, risk: str, args: Optional[Dict[str, Any]]) -> str:
        """Create a pending approval request. Returns request_id."""
        request_id = str(uuid.uuid4())
        now = time.time()
        args_hash = self._args_hash(args)
        args_canon = self._canonical_args(args)

        req = AskRequest(
            request_id=request_id,
            tool=tool,
            risk=risk,
            args_hash=args_hash,
            args_canonical=args_canon,
            created_at=now,
            expires_at=now + ASK_TTL_SECONDS,
        )

        with self._ask_lock:
            self._ask_requests[request_id] = req
            self._save_ask_store()

        logger.info("ASK request created: %s for tool=%s risk=%s", request_id, tool, risk)
        return request_id

    def approve_request(self, request_id: str, token: str, approve: bool = True) -> Tuple[bool, str]:
        """
        Approve or deny a pending request. Requires valid auth token.
        Returns: (success, message)
        """
        # Verify token against stored hash using constant-time comparison
        if self.config.auth_token_hash is None:
            return False, "no auth token configured (set auth_token_hash in config)"
        provided_hash = hashlib.sha256(token.encode()).hexdigest()
        if not hmac.compare_digest(self.config.auth_token_hash, provided_hash):
            logger.warning("Invalid auth token provided for request %s", request_id)
            return False, "invalid auth token"

        with self._ask_lock:
            req = self._ask_requests.get(request_id)
            if not req:
                return False, "request not found"
            if req.decided:
                return False, "request already decided"
            if time.time() > req.expires_at:
                return False, "request expired"

            req.decided = True
            req.decision = approve
            req.decided_at = time.time()
            # Store truncated hash for audit (never plaintext)
            req.decided_by = provided_hash[:16]
            self._save_ask_store()

        action = "approved" if approve else "denied"
        logger.info("ASK request %s %s by token=%s", request_id, action, provided_hash[:16])
        return True, f"request {action}"

    def get_ask_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get ask request details for polling."""
        with self._ask_lock:
            req = self._ask_requests.get(request_id)
            if not req:
                return None
            return {
                "request_id": req.request_id,
                "tool": req.tool,
                "risk": req.risk,
                "args_hash": req.args_hash,
                "args_canonical": req.args_canonical,
                "created_at": req.created_at,
                "expires_at": req.expires_at,
                "decided": req.decided,
                "decision": req.decision,
                "decided_at": req.decided_at,
                "decided_by": req.decided_by,
            }

    def wait_for_approval(self, request_id: str, timeout: float = ASK_TTL_SECONDS) -> Tuple[bool, Optional[str]]:
        """
        Block until request is decided or expires.
        Returns: (approved, reason_if_denied)
        """
        start = time.time()
        while time.time() - start < timeout:
            with self._ask_lock:
                req = self._ask_requests.get(request_id)
                if not req:
                    return False, "request not found"
                if req.decided:
                    if req.decision:
                        return True, None
                    return False, "request denied by human"
                if time.time() > req.expires_at:
                    return False, "request expired (TTL)"
            time.sleep(0.5)
        return False, "timeout waiting for approval"

    def verify_args_hash(self, request_id: str, args: Optional[Dict[str, Any]]) -> bool:
        """Verify that args hash matches the approved request (single-use enforcement)."""
        with self._ask_lock:
            req = self._ask_requests.get(request_id)
            if not req or not req.decided or not req.decision:
                return False
            return req.args_hash == self._args_hash(args)

    def _check_rate_limit(self, key: str, limit: int) -> bool:
        """Sliding window rate limit check."""
        now = time.time()
        window_start = now - 60.0
        timestamps = self._call_counts.get(key, [])
        recent = [t for t in timestamps if t > window_start]
        if len(recent) >= limit:
            return False
        recent.append(now)
        self._call_counts[key] = recent
        return True

    def record_call(self, tool: str) -> None:
        """Record a successful tool call for rate limiting."""
        now = time.time()
        if tool not in self._call_counts:
            self._call_counts[tool] = []
        self._call_counts[tool].append(now)

    def allow_tool(self, tool: str, risk: str = "safe", require_confirm: bool = False, **kwargs) -> None:
        """Add or update a tool permission rule. Does not override explicit deny."""
        existing = self.config.tools.get(tool)
        if existing and existing.explicitly_denied:
            logger.warning("Tool '%s' is explicitly denied; allow_tool ignored", tool)
            return
        self.config.tools[tool] = ToolPermission(
            tool=tool,
            allow=True,
            risk=risk,
            require_confirm=require_confirm,
            max_calls_per_minute=kwargs.get("max_calls_per_minute"),
            allowed_args=kwargs.get("allowed_args"),
            explicitly_denied=False,
        )
        self.save_config()

    def deny_tool(self, tool: str) -> None:
        """Explicitly deny a tool. Deny wins over allow."""
        if tool in self.config.tools:
            self.config.tools[tool].allow = False
            self.config.tools[tool].explicitly_denied = True
        else:
            self.config.tools[tool] = ToolPermission(tool=tool, allow=False, explicitly_denied=True)
        self.save_config()

    def set_risk_threshold(self, risk: str) -> None:
        """Set global risk threshold."""
        if risk in RISK_ORDER:
            self.config.risk_threshold = risk
            self.save_config()

    def set_allow_all(self, enabled: bool) -> None:
        """Master kill switch - use with extreme caution."""
        self.config.allow_all = enabled
        self.save_config()
        logger.warning("PERMISSION KILL SWITCH %s", "ENABLED" if enabled else "DISABLED")

    def set_auth_token(self, token: str) -> None:
        """Set the auth token for approve/deny operations. Stores sha256 hash."""
        self.config.auth_token_hash = hashlib.sha256(token.encode()).hexdigest()
        self.save_config()
        logger.warning("AUTH TOKEN UPDATED (hash stored)")

    def get_effective_permissions(self) -> Dict[str, Any]:
        """Get effective permissions for UI/debugging."""
        return {
            "allow_all": self.config.allow_all,
            "default_allow": self.config.default_allow,
            "risk_threshold": self.config.risk_threshold,
            "global_rate_limit": self.config.global_rate_limit,
            "auth_token_configured": self.config.auth_token_hash is not None,
            "tools": {
                name: {
                    "allow": perm.allow,
                    "risk": perm.risk,
                    "require_confirm": perm.require_confirm,
                    "max_calls_per_minute": perm.max_calls_per_minute,
                    "allowed_args": perm.allowed_args,
                    "explicitly_denied": perm.explicitly_denied,
                }
                for name, perm in self.config.tools.items()
            },
        }

    # --- Ask persistence ---

    def _load_ask_store(self) -> None:
        """Load pending ask requests from disk."""
        try:
            if self.ASK_STORE_PATH.exists():
                with open(self.ASK_STORE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                now = time.time()
                for item in data.get("requests", []):
                    req = AskRequest(
                        request_id=item["request_id"],
                        tool=item["tool"],
                        risk=item["risk"],
                        args_hash=item["args_hash"],
                        args_canonical=item["args_canonical"],
                        created_at=item["created_at"],
                        expires_at=item["expires_at"],
                        decided=item.get("decided", False),
                        decision=item.get("decision"),
                        decided_at=item.get("decided_at"),
                        decided_by=item.get("decided_by"),
                    )
                    # Only keep unexpired undecided requests
                    if not req.decided and req.expires_at > now:
                        self._ask_requests[req.request_id] = req
        except Exception as exc:
            logger.warning("Failed to load ask store: %s", exc)

    def _save_ask_store(self) -> None:
        """Persist ask requests to disk."""
        try:
            self.ASK_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "requests": [
                    {
                        "request_id": req.request_id,
                        "tool": req.tool,
                        "risk": req.risk,
                        "args_hash": req.args_hash,
                        "args_canonical": req.args_canonical,
                        "created_at": req.created_at,
                        "expires_at": req.expires_at,
                        "decided": req.decided,
                        "decision": req.decision,
                        "decided_at": req.decided_at,
                        "decided_by": req.decided_by,
                    }
                    for req in self._ask_requests.values()
                ]
            }
            with open(self.ASK_STORE_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.warning("Failed to save ask store: %s", exc)

    def _start_ask_cleanup(self) -> None:
        """Background cleanup of expired ask requests."""
        def cleanup():
            while True:
                time.sleep(ASK_CLEANUP_INTERVAL)
                try:
                    now = time.time()
                    with self._ask_lock:
                        expired = [
                            rid for rid, req in self._ask_requests.items()
                            if req.expires_at < now
                        ]
                        for rid in expired:
                            del self._ask_requests[rid]
                        if expired:
                            self._save_ask_store()
                except Exception:
                    pass
        t = threading.Thread(target=cleanup, daemon=True)
        t.start()

    # --- Audit ---

    def audit(self) -> Dict[str, Any]:
        """Return audit log without secrets."""
        with self._ask_lock:
            return {
                "config": self.get_effective_permissions(),
                "rate_limits": {
                    tool: len([t for t in timestamps if t > time.time() - 60])
                    for tool, timestamps in self._call_counts.items()
                },
                "pending_asks": len([r for r in self._ask_requests.values() if not r.decided]),
                "decided_asks": len([r for r in self._ask_requests.values() if r.decided]),
                "recent_decisions": [
                    {
                        "request_id": req.request_id,
                        "tool": req.tool,
                        "decision": req.decision,
                        "decided_at": req.decided_at,
                        "decided_by": req.decided_by,
                        "args_hash": req.args_hash,
                    }
                    for req in sorted(
                        [r for r in self._ask_requests.values() if r.decided],
                        key=lambda x: x.decided_at or 0,
                        reverse=True
                    )[:20]
                ],
            }


# Global singleton
_engine: Optional[PermissionEngine] = None


def get_permission_engine() -> PermissionEngine:
    """Get global permission engine instance."""
    global _engine
    if _engine is None:
        _engine = PermissionEngine()
    return _engine


def reset_permission_engine() -> None:
    """Reset global instance (for testing)."""
    global _engine
    _engine = None