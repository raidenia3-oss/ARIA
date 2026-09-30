"""Post-setup validation.

Every check is read-only and time-boxed. The goal is an honest answer to "is
ARIA operational?", not a green checkmark: a check that cannot run reports
itself as SKIPPED with the reason, never as OK.
"""

from __future__ import annotations

import json
import socket
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .detector import EnvironmentDetector, read_env_keys
from .model import StepResult, Tier

HTTP_TIMEOUT_S = 3.0


@dataclass
class Check:
    """One named validation with a tier and a short description."""

    name: str
    tier: Tier
    description: str


# The validation contract. `run_all` walks exactly this list, which is what
# makes `--validate` and the setup report consistent with each other.
CHECKS: tuple[Check, ...] = (
    Check("python_version", Tier.CORE, "interpreter is 3.11+"),
    Check("imports", Tier.CORE, "core modules import cleanly"),
    Check("database", Tier.CORE, "aura.db is readable and migrated"),
    Check("directories", Tier.CORE, "required directories exist"),
    Check("env_files", Tier.CORE, "env files are readable"),
    Check("gitignore", Tier.CORE, "secrets and databases are git-ignored"),
    Check("git_repo", Tier.RUNTIME, "repository is initialised"),
    Check("node", Tier.RUNTIME, "Node available for the v5 toolchain"),
    Check("ollama", Tier.RUNTIME, "Ollama reachable with at least one model"),
    Check("axum_health", Tier.RUNTIME, "Axum backend answers /health"),
    Check("fastapi_health", Tier.RUNTIME, "FastAPI backend answers /health"),
    Check("discord_token", Tier.OPTIONAL, "Discord token configured"),
    Check("github_token", Tier.OPTIONAL, "GitHub token configured"),
    Check("credentials", Tier.OPTIONAL, "no credential exposure"),
)


class Validator:
    """Runs the declared checks and reports each outcome."""

    def __init__(self, detector: EnvironmentDetector, dry_run: bool = False) -> None:
        self.detector = detector
        self.root: Path = Path(detector.project_root)
        self.dry_run = dry_run

    def validate_all(self, tiers: list[str] | None = None) -> dict[str, StepResult]:
        """Run every applicable check. Returns name -> result."""
        selected = set(tiers) if tiers else {t.value for t in Tier}
        results: dict[str, StepResult] = {}
        for check in CHECKS:
            if check.tier.value not in selected:
                continue
            handler = getattr(self, f"_check_{check.name}", None)
            if handler is None:
                results[check.name] = StepResult.fail(f"no handler for check {check.name}")
                continue
            try:
                results[check.name] = handler()
            except Exception as exc:  # noqa: BLE001 - a crashing check is a failed check
                results[check.name] = StepResult.fail(f"{check.__class__.__name__}: {exc}")
        return results

    # ----------------------------------------------------------------- core

    def _check_python_version(self) -> StepResult:
        major, minor = sys.version_info[:2]
        if (major, minor) < (3, 11):
            return StepResult.fail(f"Python {major}.{minor} found, 3.11+ required")
        return StepResult.ok(f"Python {major}.{minor}", venv=sys.prefix != getattr(sys, "base_prefix", sys.prefix))

    def _check_imports(self) -> StepResult:
        required = ["fastapi", "uvicorn", "pydantic", "dotenv", "requests", "httpx", "aiohttp", "sqlite3"]
        missing: list[str] = []
        for module in required:
            try:
                __import__(module)
            except ImportError:
                missing.append(module)
        if missing:
            return StepResult.fail(f"missing modules: {', '.join(missing)}", missing=missing)
        return StepResult.ok(f"{len(required)} core modules import cleanly")

    def _check_database(self) -> StepResult:
        db = self.root / "aura.db"
        if not db.is_file():
            return StepResult.fail("aura.db does not exist", database=str(db))
        try:
            connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=10)
            integrity = connection.execute("PRAGMA quick_check(1)").fetchone()
            tables = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            connection.close()
        except sqlite3.Error as exc:
            return StepResult.fail(f"database unreadable: {exc}", database=str(db))

        if not integrity or integrity[0] != "ok":
            return StepResult.fail(f"integrity check failed: {integrity}", database=str(db))
        required = {"conversations", "messages", "memories", "tasks"}
        missing = sorted(required - tables)
        if missing:
            return StepResult.warn(f"missing tables: {', '.join(missing)}", database=str(db))
        return StepResult.ok(f"{len(tables)} tables, integrity ok", database=str(db))

    def _check_directories(self) -> StepResult:
        from .initializer import REQUIRED_DIRS

        missing = [d for d in REQUIRED_DIRS if not (self.root / d).is_dir()]
        if missing:
            return StepResult.warn(f"{len(missing)} missing: {', '.join(missing[:5])}", missing=missing)
        return StepResult.ok(f"all {len(REQUIRED_DIRS)} directories present")

    def _check_env_files(self) -> StepResult:
        from .configurator import Configurator

        problems: list[str] = []
        found = 0
        for relative in Configurator.TARGETS:
            path = self.root / relative
            if not path.is_file():
                problems.append(f"{relative} missing")
                continue
            found += 1
            keys = read_env_keys(path)
            if not keys:
                problems.append(f"{relative} has no keys")
        if problems:
            return StepResult.warn("; ".join(problems), problems=problems)
        return StepResult.ok(f"{found} env files readable")

    def _check_gitignore(self) -> StepResult:
        gitignore = self.root / ".gitignore"
        if not gitignore.is_file():
            return StepResult.fail("no .gitignore")
        content = gitignore.read_text(encoding="utf-8", errors="replace")
        missing = [p for p in (".env", "*.db", ".venv/") if p not in content]
        if missing:
            return StepResult.warn(f"missing patterns: {', '.join(missing)}", missing=missing)
        return StepResult.ok(".gitignore covers .env, *.db and .venv/")

    # -------------------------------------------------------------- runtime

    def _check_git_repo(self) -> StepResult:
        if not (self.root / ".git").exists():
            return StepResult.fail("not a git repository")
        try:
            proc = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(self.root),
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return StepResult.fail(f"git unusable: {exc}")
        if proc.returncode != 0:
            return StepResult.warn("git repository has no commits yet")
        return StepResult.ok(f"branch {proc.stdout.strip()}")

    def _check_node(self) -> StepResult:
        if not self.detector.detect().node_installed:
            return StepResult.skip("Node not installed (only needed for the v5 toolchain)")
        env = self.detector.detect()
        return StepResult.ok(env.node_version or "Node present")

    def _check_ollama(self) -> StepResult:
        env = self.detector.detect()
        if not env.ollama_running:
            return StepResult.warn(
                "Ollama not running - ARIA falls back to the rule-based provider",
                install="https://ollama.com/download",
            )
        if not env.ollama_models:
            return StepResult.warn("Ollama is up but has no models", hint="ollama pull dolphin-2_6-phi-2")
        return StepResult.ok(f"{len(env.ollama_models)} model(s): {', '.join(env.ollama_models[:3])}")

    # ------------------------------------------------------------- services

    def _check_axum_health(self) -> StepResult:
        return self._http_check("axum", "http://127.0.0.1:8002/health", expect_keys=("status",))

    def _check_fastapi_health(self) -> StepResult:
        # The two backends have moved between 8000 and 8001 during the
        # migration, so probe both and report whichever answers.
        for port in (8000, 8001):
            result = self._http_check("fastapi", f"http://127.0.0.1:{port}/health", port=port)
            if result.status.is_terminal_ok:
                return result
        return StepResult.warn("FastAPI not answering on 8000 or 8001", hint="start_backend.bat")

    def _http_check(
        self,
        name: str,
        url: str,
        expect_keys: tuple[str, ...] = (),
        port: int | None = None,
    ) -> StepResult:
        """GET a health endpoint. Unreachable is WARN, not FAIL.

        Backends are started separately from setup; a down service is a
        configuration state, not a broken install.
        """
        try:
            with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT_S) as resp:  # noqa: S310
                if resp.status != 200:
                    return StepResult.warn(f"{name} returned HTTP {resp.status}", url=url)
                payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            return StepResult.warn(f"{name} returned HTTP {exc.code}", url=url)
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
            where = f"port {port}" if port else url
            return StepResult.skip(f"{name} not running on {where}", url=url)

        if not isinstance(payload, dict):
            return StepResult.warn(f"{name} returned a non-object response", url=url)
        missing = [key for key in expect_keys if key not in payload]
        if missing:
            return StepResult.warn(f"{name} response missing {', '.join(missing)}", url=url)

        status = str(payload.get("status", "unknown"))
        if status not in ("ok", "healthy", "ok "):
            return StepResult.warn(f"{name} reports status={status}", url=url, payload=_safe(payload))
        return StepResult.ok(f"{name} healthy on {port or url}", payload=_safe(payload))

    # ------------------------------------------------------------- optional

    def _check_discord_token(self) -> StepResult:
        from .configurator import EnvFile
        from .detector import env_value_looks_real

        env = EnvFile(self.root / ".env")
        if env_value_looks_real(env.get("DISCORD_TOKEN")):
            return StepResult.ok("Discord token configured")
        return StepResult.skip("Discord not configured (optional)")

    def _check_github_token(self) -> StepResult:
        from .configurator import EnvFile
        from .detector import env_value_looks_real

        env = EnvFile(self.root / "ARIA_APP" / "backend" / ".env")
        if env_value_looks_real(env.get("GITHUB_TOKEN")):
            return StepResult.ok("GitHub token configured")
        return StepResult.skip("GitHub not configured (optional)")

    def _check_credentials(self) -> StepResult:
        """Credential hygiene.

        A *tracked* env file holding a real credential is a live leak: it is
        already in git history, so `.gitignore` does not help. That is FAIL,
        not WARN. Cosmetic issues (a missing pattern, a stale lock) stay WARN.
        """
        from .secrets_manager import SecretsManager

        result = SecretsManager(self.root, dry_run=self.dry_run).security_audit()
        issues = list(result.details.get("issues", []))
        tracked = [issue for issue in issues if "tracked by git" in issue]
        cosmetic = [issue for issue in issues if issue not in tracked]

        if tracked:
            return StepResult.fail(
                f"{len(tracked)} credential leak(s) in tracked files - rotate the exposed secrets",
                issues=tracked,
                hint="git rm --cached the file, then rotate the exposed credentials",
            )
        if cosmetic:
            hint = None
            if any("placeholder" in issue for issue in cosmetic):
                hint = "tracked env files hold development placeholders; set real values before deploying"
            return StepResult.warn(f"{len(cosmetic)} hygiene issue(s)", issues=cosmetic, hint=hint)
        return StepResult.ok("no credential exposure detected")

    # ---------------------------------------------------------------- ports

    def scan_ports(self) -> dict[str, bool]:
        """Which ARIA ports are bound right now."""
        from .detector import SERVICE_PORTS

        results: dict[str, bool] = {}
        for name, port in SERVICE_PORTS.items():
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.6):
                    results[name] = True
            except OSError:
                results[name] = False
        return results


def _safe(payload: dict) -> dict:
    """Drop anything that looks like a credential before it reaches a report."""
    from .configurator import _is_secret

    return {k: v for k, v in payload.items() if not _is_secret(str(k))}
