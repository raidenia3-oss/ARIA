"""Gemini CLI provider via subprocess.

FASE 1: un solo proveedor, Gemini CLI (npm: @google/gemini-cli).
El nucleo del proveedor vive en provider.py; quota.py maneja el presupuesto
diario y el cooldown; redact.py limpia los prompts salientes antes de llegar
al CLI. Nada de esto estima cuota: todo lo que se reporta es medido o
configurable via fuente documentada.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.agents.llm_cli.quota import QuotaManager, get_quota_manager
from backend.agents.llm_cli.redact import redact_prompt, redaction_report


PROVIDER_NAME = "official_cli"
CLI_BINARY = "gemini"
DEFAULT_TIMEOUT_S = 120.0
DEFAULT_MAX_OUTPUT_BYTES = 2 * 1024 * 1024

_SUBPROCESS_ENV_ALLOW = (
    "PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP",
    "HOME", "USERPROFILE", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "TERM",
    "SHELL", "FORCE_COLOR", "NO_COLOR", "CI", "NODE_ENV", "NODE_PATH",
    "NPM_CONFIG_PREFIX", "PYTHONPATH", "PYTHONUTF8", "PYTHONIOENCODING",
    "AURA_GEMINI_CLI_DAILY_LIMIT", "AURA_GEMINI_CLI_COOLDOWN",
    "AURA_GEMINI_CLI_QUOTA_STATE",
)

READ_ONLY_APPROVAL_MODE = "plan"
OUTPUT_FORMAT_JSON = "json"
OUTPUT_FORMAT_TEXT = "text"


@dataclass
class CLICallResult:
    """Structured result of a single CLI invocation.

    The CLI output is treated as UNTRUSTED at the consumption point.
    """

    success: bool = False
    provider: str = PROVIDER_NAME
    model: Optional[str] = None
    output: str = ""
    truncated: bool = False
    exit_code: Optional[int] = None
    duration_ms: float = 0.0
    error: Optional[str] = None
    unavailable: bool = False
    read_only: bool = False
    redaction: Dict[str, int] = field(default_factory=dict)
    quota_state: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success, "provider": self.provider,
            "model": self.model, "output": self.output,
            "truncated": self.truncated, "exit_code": self.exit_code,
            "duration_ms": self.duration_ms, "error": self.error,
            "unavailable": self.unavailable, "read_only": self.read_only,
            "redaction": self.redaction, "quota_state": self.quota_state,
        }


def _build_env(extra=None):
    """Build a minimal subprocess env from the allowlist.

    Any *_API_KEY in the parent env is deliberately excluded.
    """
    out = {}
    for key in _SUBPROCESS_ENV_ALLOW:
        if key in os.environ:
            out[key] = os.environ[key]
    if extra:
        for k, v in extra.items():
            if k in _SUBPROCESS_ENV_ALLOW:
                out[k] = v
    return out


def _has_api_key_env(env):
    for key in env:
        if key.upper().endswith("_API_KEY") or key.upper() == "API_KEY":
            return True
    return False


def _binary_available():
    return shutil.which(CLI_BINARY) is not None


def _truncate_output(raw, cap):
    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception:
        text = raw.decode("latin-1", errors="replace")
    if len(raw) > cap:
        return text[:cap], True
    return text, False


def _parse_cli_output(raw, fmt):
    if fmt != OUTPUT_FORMAT_JSON:
        return raw
    try:
        data = json.loads(raw)
    except Exception:
        return raw
    try:
        if isinstance(data, dict):
            for key in ("response", "output", "result", "text", "answer"):
                if isinstance(data.get(key), str):
                    return data[key]
            msg = data.get("message")
            if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                return msg["content"]
            if isinstance(msg, str):
                return msg
            return json.dumps(data, ensure_ascii=False)
        if isinstance(data, str):
            return data
    except Exception:
        pass
    return raw


class GeminiCLIService:
    """Subprocess-based Gemini CLI provider.

    One call at a time (single Lock). No shell=True: args are a list. The
    subprocess runs in an empty temp cwd with a stripped env allowlist that
    excludes any *_API_KEY. Output is capped and flagged as truncated when
    the cap is hit. The CLI output is treated as UNTRUSTED.
    """

    def __init__(
        self,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
        quota: Optional[QuotaManager] = None,
        cli_binary: str = CLI_BINARY,
    ) -> None:
        self.timeout_s = timeout_s
        self.max_output_bytes = max_output_bytes
        self.quota = quota or get_quota_manager()
        self.cli_binary = cli_binary
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return _binary_available()

    def _check_unavailable(self) -> Optional[str]:
        if not _binary_available():
            return (
                f"Gemini CLI binary '{self.cli_binary}' not found on PATH. "
                f"Install with: npm install -g @google/gemini-cli"
            )
        return None

    def _build_args(
        self,
        prompt: str,
        model: Optional[str],
        read_only: bool,
        output_format: str = OUTPUT_FORMAT_JSON,
    ) -> List[str]:
        """Build the argv list. No invented flags: every flag here is in
        docs/gemini-cli-help.txt."""
        args: List[str] = [self.cli_binary]
        if read_only:
            args.extend(["--approval-mode", READ_ONLY_APPROVAL_MODE])
        args.extend(["--output-format", output_format])
        if model:
            args.extend(["--model", model])
        args.append(prompt)
        return args

    def _run_raw(
        self,
        prompt: str,
        model: Optional[str],
        read_only: bool,
        output_format: str = OUTPUT_FORMAT_JSON,
        timeout_s: Optional[float] = None,
    ) -> CLICallResult:
        """Execute the subprocess with no quota/lock handling."""
        start = time.perf_counter()
        unavailable = self._check_unavailable()
        if unavailable:
            return CLICallResult(
                success=False, error=unavailable, unavailable=True,
                duration_ms=(time.perf_counter() - start) * 1000.0,
            )

        env = _build_env()
        args = self._build_args(prompt, model, read_only, output_format)

        with tempfile.TemporaryDirectory(prefix="aura_gemini_cli_") as cwd:
            try:
                proc = subprocess.run(
                    args, cwd=cwd, env=env, capture_output=True,
                    timeout=timeout_s or self.timeout_s, shell=False,
                )
            except subprocess.TimeoutExpired:
                return CLICallResult(
                    success=False,
                    error=f"CLI timed out after {timeout_s or self.timeout_s}s",
                    exit_code=None,
                    duration_ms=(time.perf_counter() - start) * 1000.0,
                )
            except FileNotFoundError as exc:
                return CLICallResult(
                    success=False, error=f"CLI binary not found: {exc}",
                    unavailable=True,
                    duration_ms=(time.perf_counter() - start) * 1000.0,
                )
            except OSError as exc:
                return CLICallResult(
                    success=False,
                    error=f"OS error launching CLI: {exc}",
                    duration_ms=(time.perf_counter() - start) * 1000.0,
                )

            duration_ms = (time.perf_counter() - start) * 1000.0
            stdout = proc.stdout or b""
            stderr = proc.stderr or b""

            if proc.returncode != 0:
                text, truncated = _truncate_output(stderr or stdout, self.max_output_bytes)
                return CLICallResult(
                    success=False, output=text, truncated=truncated,
                    exit_code=proc.returncode, duration_ms=duration_ms,
                    error=f"CLI exited with code {proc.returncode}",
                )

            text, truncated = _truncate_output(stdout, self.max_output_bytes)
            parsed = _parse_cli_output(text, output_format)
            return CLICallResult(
                success=True, output=parsed, truncated=truncated,
                exit_code=proc.returncode, duration_ms=duration_ms,
                read_only=read_only,
            )

    def invoke(
        self,
        prompt: str,
        model: Optional[str] = None,
        read_only: bool = False,
        output_format: str = OUTPUT_FORMAT_JSON,
        timeout_s: Optional[float] = None,
    ) -> CLICallResult:
        """Invoke the CLI with quota + lock + redaction."""
        # 1. Redact the outgoing prompt (input-side sanitization).
        redacted = redact_prompt(prompt)
        report = redaction_report(prompt)

        # 2. Quota check (measured counter, never estimates remaining).
        allowed, reason = self.quota.can_call()
        quota_state = self.quota.state()
        if not allowed:
            return CLICallResult(
                success=False, error=reason, unavailable=False,
                read_only=read_only, redaction=report, quota_state=quota_state,
            )
        with self._lock:
            result = self._run_raw(redacted, model, read_only, output_format, timeout_s)
            self.quota.record_call(success=result.success)
            result.redaction = report
            result.quota_state = self.quota.state()
            return result

    def state(self) -> Dict[str, Any]:
        return {
            "provider": PROVIDER_NAME,
            "available": self.available,
            "quota": self.quota.state(),
        }


_service_instance: Optional[GeminiCLIService] = None


def get_gemini_cli_service() -> GeminiCLIService:
    global _service_instance
    if _service_instance is None:
        _service_instance = GeminiCLIService()
    return _service_instance


def reset_gemini_cli_service() -> None:
    global _service_instance
    _service_instance = None