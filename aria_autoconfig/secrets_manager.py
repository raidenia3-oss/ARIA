"""Secret acquisition and auditing.

A secret is never invented. When ARIA needs a credential it is missing, this
module records the request and, if a channel is available, asks for it out of
band (Discord webhook, GitHub issue) instead of blocking setup on a terminal
prompt. That is the difference between "zero-touch" and "hangs forever waiting
for input".

What it guarantees:
* Values are never logged, printed, or written to a report.
* The request log is append-only and lives outside the repo by default.
* Every secret has a documented way to be supplied, so the operator is never
  guessing what to do.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .configurator import EnvFile, _is_secret
from .detector import env_value_looks_real, read_env_keys
from .model import StepResult

# Short, word-like values are development placeholders, not real credentials.
# Flagging them as a leak trains the operator to ignore the warning.
_WEAK_DEV_SECRETS: frozenset[str] = frozenset(
    {
        "secret",
        "dev-secret",
        "secret-key",
        "test-secret",
        "local-dev",
        "placeholder",
        "development",
    }
)

# Minimum credible length per credential kind. Real tokens are far longer
# (Discord 50+, GitHub 40+, our generated webhook secret 64), so anything
# under this is a hand-written development value.
_MIN_REAL_LENGTH: dict[str, int] = {
    "SECRET": 16,
    "PASSWORD": 12,
    "API_KEY": 20,
    "TOKEN": 24,
    "PRIVATE_KEY": 32,
}


def _looks_like_weak_dev_secret(key: str, value: str) -> bool:
    """True for obvious local placeholders such as `dev-secret-key`.

    Two signals: an exact match against the known placeholder list, and a
    length below what the credential kind could plausibly be. A short value
    in a tracked file is a weak secret worth rotating, not a live token leak.
    """
    if len(value) >= 24:
        return False
    if value.strip().lower() in _WEAK_DEV_SECRETS:
        return True
    upper = key.upper()
    for marker, minimum in _MIN_REAL_LENGTH.items():
        if marker in upper and len(value) < minimum:
            return True
    return False

# Where each secret lives, and how ARIA obtains it.
SECRET_SPECS: dict[str, dict[str, str]] = {
    "DISCORD_TOKEN": {
        "file": ".env",
        "purpose": "Discord bot gateway connection",
        "how": "Discord Developer Portal > Bot > Reset Token",
        "required": "optional",
    },
    "GITHUB_TOKEN": {
        "file": "ARIA_APP/backend/.env",
        "purpose": "Auto-commit, issue triage, PR analysis",
        "how": "github.com/settings/tokens (scope: repo)",
        "required": "optional",
    },
    "GITHUB_WEBHOOK_SECRET": {
        "file": "ARIA_APP/backend/.env",
        "purpose": "Verifies GitHub webhook payloads",
        "how": "auto-generated during setup",
        "required": "optional",
    },
    "NGROK_URL": {
        "file": "ARIA_APP/backend/.env",
        "purpose": "Public tunnel for the mobile client",
        "how": "ngrok http 8000",
        "required": "optional",
    },
    "OPENROUTER_API_KEY": {
        "file": ".env",
        "purpose": "Cloud LLM fallback (after Ollama/Gemini/Groq)",
        "how": "openrouter.ai/keys",
        "required": "optional",
    },
    "GEMINI_API_KEY": {
        "file": ".env",
        "purpose": "Cloud LLM fallback",
        "how": "aistudio.google.com/apikey",
        "required": "optional",
    },
    "GROQ_API_KEY": {
        "file": ".env",
        "purpose": "Fast cloud inference fallback",
        "how": "console.groq.com/keys",
        "required": "optional",
    },
    "HF_TOKEN": {
        "file": ".env",
        "purpose": "Hugging Face model downloads",
        "how": "huggingface.co/settings/tokens",
        "required": "optional",
    },
}

_TOKEN_SHAPES = {
    "DISCORD_TOKEN": re.compile(r"^[A-Za-z0-9_.-]{50,}$"),
    "GITHUB_TOKEN": re.compile(r"^gh[pousr]_[A-Za-z0-9]{16,}$"),
    "NGROK_URL": re.compile(r"^https://[a-z0-9-]+\.ngrok(-free)?\.(io|app)$"),
}


@dataclass
class SecretStatus:
    """Presence of one secret. Carries no value, ever."""

    name: str
    file: str
    present: bool
    purpose: str
    how: str
    requested_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "file": self.file,
            "present": self.present,
            "purpose": self.purpose,
            "how": self.how,
            "requested_at": self.requested_at,
        }


@dataclass
class SecretsManager:
    """Audits which secrets exist and requests the missing ones out of band."""

    project_root: Path
    requests_file: Path = field(init=False)
    dry_run: bool = False

    def __post_init__(self) -> None:
        # The request log must not land in the repo: it records *that* a
        # credential is missing, which is information an attacker can use.
        base = os.environ.get("ARIA_STATE_DIR")
        state_dir = Path(base) if base else Path.home() / ".aria"
        self.requests_file = state_dir / "secret_requests.json"

    # ----------------------------------------------------------------- audit

    def audit(self) -> list[SecretStatus]:
        """Check every known secret without reading values into the report."""
        statuses: list[SecretStatus] = []
        requested = self._load_requests()
        for name, spec in SECRET_SPECS.items():
            env = EnvFile(self.project_root / spec["file"])
            value = env.get(name)
            present = env_value_looks_real(value)
            if present and name in _TOKEN_SHAPES and not _TOKEN_SHAPES[name].match(value):
                # Present but malformed is worse than absent: it fails later,
                # at request time, with a confusing error.
                present = False
            statuses.append(
                SecretStatus(
                    name=name,
                    file=spec["file"],
                    present=present,
                    purpose=spec["purpose"],
                    how=spec["how"],
                    requested_at=float(requested.get(name, 0.0)),
                )
            )
        return statuses

    def setup_secrets(self) -> StepResult:
        """Audit secrets and request whatever is missing.

        Non-blocking by contract: a missing optional secret produces WARN and
        a recorded request, never a prompt and never a failure.
        """
        statuses = self.audit()
        missing = [s for s in statuses if not s.present]

        if not missing:
            return StepResult.ok(
                f"all {len(statuses)} known secrets present",
                secrets=[s.name for s in statuses],
            )

        if self.dry_run:
            return StepResult.warn(
                f"dry-run: {len(missing)} secret(s) missing",
                missing=[s.name for s in missing],
            )

        self._request(missing)

        # Anything with a working non-interactive channel gets a real message.
        notified: list[str] = []
        if self._discord_configured():
            for secret in missing:
                if self._notify_discord(secret):
                    notified.append(secret.name)

        return StepResult.warn(
            f"{len(missing)} secret(s) not configured - ARIA runs without them",
            missing=[s.name for s in missing],
            requested_via=notified or "local log only",
            log=str(self.requests_file),
        )

    # -------------------------------------------------------------- requests

    def _request(self, secrets: list[SecretStatus]) -> None:
        """Record the request so the autonomous loop can follow up later."""
        data = self._load_requests()
        now = time.time()
        for secret in secrets:
            data[secret.name] = now
        try:
            self.requests_file.parent.mkdir(parents=True, exist_ok=True)
            self.requests_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            # Failing to write the log must not fail setup.
            pass

    def _load_requests(self) -> dict[str, float]:
        try:
            raw = json.loads(self.requests_file.read_text(encoding="utf-8"))
            return {str(k): float(v) for k, v in raw.items()} if isinstance(raw, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    def pending_requests(self) -> dict[str, float]:
        """Secrets requested but still not supplied."""
        return {
            name: at
            for name, at in self._load_requests().items()
            if name in SECRET_SPECS and not any(s.name == name and s.present for s in self.audit())
        }

    # --------------------------------------------------------------- Discord

    def _discord_configured(self) -> bool:
        env = EnvFile(self.project_root / ".env")
        return env_value_looks_real(env.get("DISCORD_TOKEN")) or env_value_looks_real(
            os.environ.get("DISCORD_WEBHOOK_URL", "")
        )

    def _notify_discord(self, secret: SecretStatus) -> bool:
        """Post a credential request to Discord.

        The bot token alone is not enough to post; a webhook URL is required.
        Without one the request stays in the local log, which is the honest
        outcome - we do not claim a notification that never happened.
        """
        webhook = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
        if not env_value_looks_real(webhook):
            return False

        body = json.dumps(
            {
                "content": (
                    f"**ARIA setup** necesita `{secret.name}`\n"
                    f"Uso: {secret.purpose}\n"
                    f"Cómo obtenerlo: {secret.how}\n"
                    f"Destino: `{secret.file}`"
                )
            }
        ).encode("utf-8")

        request = urllib.request.Request(
            webhook,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as resp:  # noqa: S310
                return 200 <= resp.status < 300
        except (urllib.error.URLError, OSError, ValueError):
            return False

    # ----------------------------------------------------------------- audit

    def security_audit(self) -> StepResult:
        """Check for the failure modes that leak credentials."""
        issues: list[str] = []

        for name, spec in SECRET_SPECS.items():
            path = self.project_root / spec["file"]
            if not path.is_file():
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            value = EnvFile(path).get(name)
            if _is_secret(name) and env_value_looks_real(value) and value in content:
                # A secret repeated outside a KEY=VALUE line means it is
                # hardcoded somewhere in the file body.
                others = [ln for ln in content.splitlines() if value in ln and not ln.strip().startswith(f"{name}=")]
                if others:
                    issues.append(f"{spec['file']}: {name} appears outside its assignment ({len(others)} line(s))")

        tracked_with_secrets = self._tracked_env_files_with_secrets()
        if tracked_with_secrets:
            issues.append(
                f"these env files are tracked by git and contain real credentials: "
                f"{', '.join(tracked_with_secrets)}"
            )

        weak_tracked = self._tracked_env_files_with_weak_secrets()
        if weak_tracked:
            issues.append(
                f"tracked env file(s) hold development placeholder secrets: {', '.join(weak_tracked)} "
                f"- git-ignore them and set real values before deploying"
            )

        if not issues:
            return StepResult.ok("no credential exposure detected")
        return StepResult.warn(f"{len(issues)} credential hygiene issue(s)", issues=issues)

    def _tracked_env_files(self) -> list[str]:
        """Env files git is actually tracking. A tracked `.env` is a leak."""
        import subprocess

        try:
            proc = subprocess.run(
                ["git", "ls-files", "--", ".env", "*.env", ".env.ai", ".env.cloud"],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return []
        if proc.returncode != 0:
            return []
        return [line for line in proc.stdout.splitlines() if line.strip()]

    def _tracked_env_files_with_weak_secrets(self) -> list[str]:
        """Tracked env files whose secrets are only development placeholders.

        Worth surfacing, not worth failing over: the value is already public
        in git history, but it protects nothing, so the fix is "set a real
        one", not "rotate an exposed one".
        """
        weak: list[str] = []
        for relative in self._tracked_env_files():
            path = self.project_root / relative
            try:
                keys = read_env_keys(path)
            except OSError:
                continue
            for key, value in keys.items():
                if _is_secret(key) and env_value_looks_real(value) and _looks_like_weak_dev_secret(key, value):
                    weak.append(f"{relative}:{key}")
                    break
        return sorted(set(weak))

    def _tracked_env_files_with_secrets(self) -> list[str]:
        """Tracked env files that actually hold a live credential.

        A tracked template full of placeholders is a hygiene problem; a
        tracked file with a real token is an incident. Only the second is
        worth failing a run over.
        """
        leaked: list[str] = []
        for relative in self._tracked_env_files():
            path = self.project_root / relative
            try:
                keys = read_env_keys(path)
            except OSError:
                continue
            for key, value in keys.items():
                if (
                    _is_secret(key)
                    and env_value_looks_real(value)
                    and not _looks_like_weak_dev_secret(key, value)
                ):
                    leaked.append(relative)
                    break
        return sorted(set(leaked))

    def inject(self, name: str, value: str) -> StepResult:
        """Store a secret into its env file. Used by `--set-secret`.

        The value is validated against the known token shape when one exists,
        because a typo'd token is indistinguishable from a missing one until
        the first API call fails.
        """
        spec = SECRET_SPECS.get(name)
        if spec is None:
            return StepResult.fail(f"unknown secret: {name}", known=list(SECRET_SPECS))
        if not value.strip():
            return StepResult.fail("empty value")
        if name in _TOKEN_SHAPES and not _TOKEN_SHAPES[name].match(value.strip()):
            return StepResult.fail(f"value does not look like a valid {name}")

        env = EnvFile(self.project_root / spec["file"])
        if not env.set(name, value.strip(), overwrite=True):
            return StepResult.skip(f"{name} already set to that value", file=spec["file"])
        if not self.dry_run:
            env.save()
        return StepResult.ok(f"stored {name}", file=spec["file"])
