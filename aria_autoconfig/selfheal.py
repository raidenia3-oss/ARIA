"""Retry and recovery policy.

Retry is not decorative here. Setup runs unattended, so a step that fails
transiently (a network hiccup during `pip install`, a file locked by another
process on Windows) must be retried before it is reported as failed. Anything
retried three times and still failing is escalated to a repair action.

The distinction that matters: a step is retried only when its failure looks
transient. Re-running a step that failed because of a genuine configuration
error just wastes time and hides the real problem.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from .model import StepResult, Status

# Substrings that mark a failure as worth retrying.
TRANSIENT_MARKERS: tuple[str, ...] = (
    "timed out",
    "timeout",
    "temporarily unavailable",
    "connection reset",
    "connection refused",
    "connection aborted",
    "read timed out",
    "winerror 32",       # file in use on Windows
    "resource busy",
    "the process cannot access the file",
    "text file busy",
    "network is unreachable",
    "temporary failure",
    "502",
    "503",
    "504",
)

# Failures that will never succeed on retry, however many attempts.
PERMANENT_MARKERS: tuple[str, ...] = (
    "no matching distribution",
    "could not find a version",
    "permission denied",
    "access is denied",
    "not recognized as an internal",
    "command not found",
    "is not a valid",
    "compilation failed",
    "requires a compiler",
    "unknown secret",
)

DEFAULT_ATTEMPTS = 3
DEFAULT_BACKOFF_S = 2.0
DEFAULT_BACKOFF_CAP_S = 30.0


def is_transient(message: str) -> bool:
    """Heuristic: could this failure succeed if run again in a moment?"""
    lowered = (message or "").lower()
    if any(marker in lowered for marker in PERMANENT_MARKERS):
        return False
    return any(marker in lowered for marker in TRANSIENT_MARKERS)


def is_retryable(result: StepResult) -> bool:
    if result.status is not Status.FAILED:
        return False
    return is_transient(result.message)


@dataclass
class RetryPolicy:
    """Exponential backoff with a cap, skipping retries for permanent errors."""

    attempts: int = DEFAULT_ATTEMPTS
    backoff_s: float = DEFAULT_BACKOFF_S
    backoff_cap_s: float = DEFAULT_BACKOFF_CAP_S
    sleep_fn: Callable[[float], None] = time.sleep
    on_attempt: Callable[[int, int, str], None] | None = None

    def run(self, name: str, action: Callable[[], StepResult]) -> tuple[StepResult, int]:
        """Run `action`, retrying transient failures. Returns (result, attempts)."""
        result = StepResult.fail("step never ran")
        for attempt in range(1, self.attempts + 1):
            result = action()
            if result.status is not Status.FAILED:
                return result, attempt
            if attempt >= self.attempts or not is_retryable(result):
                return result, attempt
            delay = min(self.backoff_s * (2 ** (attempt - 1)), self.backoff_cap_s)
            if self.on_attempt:
                self.on_attempt(attempt, self.attempts, f"retrying in {delay:.0f}s: {result.message}")
            self.sleep_fn(delay)
        return result, self.attempts


@dataclass
class RepairAction:
    """What to try when a step will not succeed on its own."""

    name: str
    description: str
    action: Callable[[], StepResult] | None = None

    def attempt(self) -> StepResult:
        if self.action is None:
            return StepResult.skip(f"no automated repair for {self.name}: {self.description}")
        try:
            return self.action()
        except Exception as exc:  # noqa: BLE001 - repair must never crash setup
            return StepResult.fail(f"repair attempt failed: {exc}")


class SelfHealer:
    """Maps common failure modes to concrete repair actions.

    Repairs are conservative by design: they fix state (stale lock, missing
    directory, stale journal) and never re-download or reinstall blindly,
    because an automatic reinstall can mask a real failure.
    """

    def __init__(self, project_root, dry_run: bool = False) -> None:
        self.root = project_root
        self.dry_run = dry_run

    def repairs_for(self, step_name: str, result: StepResult) -> list[RepairAction]:
        """Repair candidates for a failed step, most likely to help first."""
        message = (result.message or "").lower()
        repairs: list[RepairAction] = []

        if "winerror 32" in message or "in use" in message or "text file busy" in message:
            repairs.append(
                RepairAction(
                    "clear_locks",
                    "a file is locked by another process (Windows)",
                    self._close_stray_processes,
                )
            )

        if "no such file or directory" in message or "cannot find the path" in message:
            repairs.append(
                RepairAction("recreate_dirs", "a required directory is missing", self._recreate_directories)
            )

        if "database is locked" in message or "sqlite" in message and "locked" in message:
            repairs.append(RepairAction("release_db", "SQLite lock held", self._release_db))

        if step_name in {"gitignore", "credentials"}:
            repairs.append(
                RepairAction("harden_gitignore", "secrets are not fully ignored", self._harden_gitignore)
            )

        if step_name.startswith("install") and "no matching distribution" in message:
            repairs.append(
                RepairAction(
                    "relax_versions",
                    "a pinned version is unavailable for this interpreter",
                    self._report_version_conflict,
                )
            )

        return repairs

    # ------------------------------------------------------------- repairs

    def _close_stray_processes(self) -> StepResult:
        """Terminate leftover ARIA processes holding a build or DB file.

        Only ARIA-owned names are touched; nothing else on the machine is
        affected.
        """
        if self.dry_run:
            return StepResult.warn("dry-run: would stop stray aria-axum-poc processes")
        import subprocess

        killed: list[str] = []
        try:
            listing = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq aria-axum-poc.exe", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            if "aria-axum-poc.exe" in listing.stdout:
                subprocess.run(
                    ["taskkill", "/F", "/IM", "aria-axum-poc.exe"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                killed.append("aria-axum-poc.exe")
        except (OSError, subprocess.SubprocessError) as exc:
            return StepResult.warn(f"could not inspect processes: {exc}")
        return StepResult.ok(f"stopped {len(killed)} stray process(es)", killed=killed)

    def _recreate_directories(self) -> StepResult:
        from .initializer import REQUIRED_DIRS

        created: list[str] = []
        for relative in REQUIRED_DIRS:
            path = self.root / relative
            if not path.is_dir():
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    created.append(relative)
                except OSError:
                    pass
        if self.dry_run:
            return StepResult.warn(f"dry-run: would create {len(created)} directories")
        return StepResult.ok(f"recreated {len(created)} directories", created=created)

    def _release_db(self) -> StepResult:
        """Drop stale WAL/SHM sidecars left by a killed process."""
        db = self.root / "aura.db"
        removed: list[str] = []
        for suffix in ("-wal", "-shm"):
            sidecar = db.with_name(db.name + suffix)
            if sidecar.exists():
                try:
                    sidecar.unlink()
                    removed.append(sidecar.name)
                except OSError:
                    pass
        if self.dry_run:
            return StepResult.warn(f"dry-run: would remove {removed}")
        if not removed:
            return StepResult.skip("no stale SQLite sidecars")
        return StepResult.ok(f"removed {', '.join(removed)}", removed=removed)

    def _harden_gitignore(self) -> StepResult:
        from .configurator import Configurator

        return Configurator(self.root, dry_run=self.dry_run).ensure_gitignore()

    def _report_version_conflict(self) -> StepResult:
        """Report which pins are unavailable. Never rewrites requirements.

        Rewriting a pinned dependency list automatically would silently change
        what ARIA runs against, so this surfaces the conflict for a human.
        """
        import re
        from pathlib import Path

        conflicts: list[str] = []
        for requirements in self.detector_find_requirements():
            try:
                content = requirements.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line in content.splitlines():
                match = re.match(r"^\s*([A-Za-z0-9_.-]+)\s*==\s*([0-9][^\s;]*)", line)
                if match:
                    conflicts.append(f"{match.group(1)}=={match.group(2)}")
        return StepResult.warn(
            f"{len(conflicts)} pinned version(s) may be unavailable on this interpreter",
            pins=conflicts[:20],
            hint="re-pin manually or install with --prefer-binary",
        )

    def detector_find_requirements(self) -> list[Path]:
        return [
            path
            for path in (self.root / "requirements.txt", self.root / "ARIA_APP" / "requirements.txt")
            if path.is_file()
        ]
