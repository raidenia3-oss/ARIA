"""Dependency installation.

Design rules, in order of importance:

1. Never fail the whole setup because one optional wheel failed to build.
   The repo pins heavy native deps (`pyaudio`, `aiortc`, `PySide6`) that need
   compilers and system libraries; on a machine without MSVC or PortAudio a
   hard failure here would make zero-touch setup impossible.
2. Prefer the project interpreter. Everything runs under `sys.executable`
   (the venv), never a bare `pip` that may target a different environment.
3. Separate "install" from "verify". After installing we import the module to
   confirm it actually works, and we report the difference.

Dependencies are declared as tiers so `--tier core` gives a fast, reliable
install and the heavy extras are opt-in.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .detector import EnvironmentDetector
from .model import StepResult, Tier
from .selfheal import is_transient as is_retryable_message

# Only what ARIA cannot boot without. All pure-Python or prebuilt wheels.
CORE_PACKAGES: tuple[str, ...] = (
    "fastapi",
    "uvicorn[standard]",
    "pydantic",
    "python-dotenv",
    "requests",
    "httpx",
    "aiohttp",
    "websockets",
    "sqlalchemy",
    "PyJWT",
    "bcrypt",
    "python-multipart",
)

# Everything needed for the desktop/orb experience, but nothing that needs a
# C toolchain at install time.
RUNTIME_PACKAGES: tuple[str, ...] = (
    "Pillow",
    "pystray",
    "psutil",
    "rich",
)

# Wheels that commonly need a compiler or system library. Installed last, and
# a failure here degrades to WARN instead of FAILED.
OPTIONAL_PACKAGES: tuple[str, ...] = (
    "playwright",
    "pyaudio",
    "aiortc",
    "PySide6",
    "opencv-python",
    "selenium",
    "ccxt",
    "praw",
)

# Import names differ from distribution names.
IMPORT_NAMES: dict[str, str] = {
    "python-dotenv": "dotenv",
    "uvicorn[standard]": "uvicorn",
    "PyJWT": "jwt",
    "python-multipart": "multipart",
    "Pillow": "PIL",
    "PySide6": "PySide6",
    "opencv-python": "cv2",
}

TIER_PACKAGES: dict[str, tuple[str, ...]] = {
    Tier.CORE.value: CORE_PACKAGES,
    Tier.RUNTIME.value: RUNTIME_PACKAGES,
    Tier.OPTIONAL.value: OPTIONAL_PACKAGES,
}

BUILD_TIMEOUT_S = 900


@dataclass
class InstallPlan:
    """What a tier actually needs right now, and what it would do."""

    tier: str
    missing: list[str]
    present: list[str]
    would_install: list[str]


def _import_name(dist: str) -> str:
    return IMPORT_NAMES.get(dist, dist.split("[")[0].replace("-", "_"))


class Installer:
    """Installs Python and Rust dependencies for the detected environment."""

    def __init__(self, detector: EnvironmentDetector, dry_run: bool = False) -> None:
        self.detector = detector
        self.dry_run = dry_run

    # ------------------------------------------------------------------ plans

    def plan(self, tiers: list[str] | None = None) -> list[InstallPlan]:
        """Compute what is missing per tier without installing anything."""
        selected = tiers or [Tier.CORE.value, Tier.RUNTIME.value]
        plans: list[InstallPlan] = []
        for tier in selected:
            packages = TIER_PACKAGES.get(tier, ())
            missing, present = [], []
            for dist in packages:
                (present if self.detector.python_site_packages_ok(_import_name(dist)) else missing).append(dist)
            plans.append(InstallPlan(tier, missing, present, list(missing)))
        return plans

    # -------------------------------------------------------------- execution

    def install_python(self, tier: str) -> StepResult:
        """Install one tier of Python packages. Idempotent by import check."""
        plan = next((p for p in self.plan([tier]) if p.tier == tier), None)
        if plan is None:
            return StepResult.fail(f"unknown tier: {tier}")
        if not plan.missing:
            return StepResult.skip(
                f"all {len(plan.present)} {tier} packages already installed",
                installed=len(plan.present),
            )
        if self.dry_run:
            return StepResult.warn(
                f"dry-run: would install {len(plan.missing)} {tier} packages",
                packages=plan.missing,
            )

        command = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            *plan.missing,
        ]
        code, output = self._pip_install(command)

        still_missing = [d for d in plan.missing if not self.detector.python_site_packages_ok(_import_name(d))]
        if code == 0 and not still_missing:
            return StepResult.ok(
                f"installed {len(plan.missing)} {tier} packages",
                packages=plan.missing,
            )

        if tier == Tier.OPTIONAL.value:
            # A missing native wheel is expected on some hosts; it must not
            # block a working setup. Marked permanent: a wheel that will not
            # build on this machine will not build on the next run either.
            return StepResult.warn(
                f"{len(still_missing)}/{len(plan.missing)} optional packages unavailable",
                permanent=not is_retryable_message(output),
                missing=still_missing,
                tail=output[-400:],
            )
        if code != 0 and not plan.present:
            return StepResult.fail(
                "core install failed",
                permanent=not is_retryable_message(output),
                tail=output[-800:],
            )
        return StepResult.warn(
            f"{len(still_missing)} {tier} packages unavailable",
            permanent=not is_retryable_message(output),
            missing=still_missing,
            tail=output[-400:],
        )
    def _pip_install(self, command: list[str]) -> tuple[int, str]:
        """pip install with a bounded timeout, preferring the wheel cache."""
        full = [*command, "--prefer-binary"]
        try:
            proc = subprocess.run(
                full,
                capture_output=True,
                text=True,
                timeout=BUILD_TIMEOUT_S,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return 1, f"pip install timed out after {BUILD_TIMEOUT_S}s"
        except OSError as exc:
            return 1, f"pip could not be started: {exc}"
        return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()

    def install_requirements_files(self) -> StepResult:
        """Install from the repo's own requirements files.

        Best effort: the root `requirements.txt` pins native packages that may
        not build everywhere, so a failure is reported but not fatal.
        """
        files = self.detector.find_requirements_files()
        if not files:
            return StepResult.skip("no requirements files found")
        if self.dry_run:
            return StepResult.warn("dry-run: would install requirements files", files=[str(f) for f in files])

        failures: dict[str, str] = {}
        installed: list[str] = []
        for requirements in files:
            code, output = self._pip_install(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "-r",
                    str(requirements),
                ]
            )
            if code == 0:
                installed.append(requirements.name)
            else:
                failures[requirements.name] = output[-300:]

        if failures and not installed:
            return StepResult.warn(
                "requirements files did not fully install",
                permanent=not _any_retryable(failures.values()),
                failures=failures,
            )
        if failures:
            return StepResult.warn(
                f"installed {len(installed)}/{len(files)} requirements files",
                permanent=not _any_retryable(failures.values()),
                installed=installed,
                failures=failures,
            )
        return StepResult.ok(f"installed {len(installed)} requirements files", installed=installed)

    def build_rust(self) -> StepResult:
        """Build the Axum crate. Skipped when Rust or the crate is absent."""
        manifests = self.detector.find_cargo_manifests()
        if not manifests:
            return StepResult.skip("no Rust crate found")
        if not self.detector.detect().cargo_installed:
            return StepResult.warn("cargo not installed - skipping Rust build", manifests=[str(m) for m in manifests])
        if self.dry_run:
            return StepResult.warn("dry-run: would cargo build --release", manifests=[str(m) for m in manifests])

        results: dict[str, str] = {}
        failures: list[str] = []
        for manifest in manifests:
            if self._rust_binary_fresh(manifest):
                results[manifest.parent.name] = "up-to-date"
                continue
            code, output = self._cargo_build(manifest)
            key = manifest.parent.name
            if code == 0:
                results[key] = "built"
            else:
                failures.append(key)
                results[key] = output[-300:]

        if failures:
            return StepResult.warn(
                f"cargo build failed for {', '.join(failures)}",
                permanent=not _any_retryable(results[name] for name in failures),
                results=results,
            )
        return StepResult.ok(f"built {len(results)} Rust crate(s)", results=results)

    def _cargo_build(self, manifest: Path) -> tuple[int, str]:
        try:
            proc = subprocess.run(
                ["cargo", "build", "--release", "--manifest-path", str(manifest)],
                capture_output=True,
                text=True,
                timeout=1800,
                cwd=str(manifest.parent),
                check=False,
            )
        except subprocess.TimeoutExpired:
            return 1, "cargo build timed out after 1800s"
        except OSError as exc:
            return 1, f"cargo could not be started: {exc}"
        return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()

    def _rust_binary_fresh(self, manifest: Path) -> bool:
        """True when a release binary already exists next to the manifest.

        Avoids a multi-minute rebuild on every setup run - the whole point of
        idempotency is that a second run is cheap.
        """
        release_dir = manifest.parent / "target" / "release"
        if not release_dir.is_dir():
            return False
        try:
            name = _crate_name(manifest)
        except OSError:
            return False
        return any(release_dir.glob(f"{name}*")) and not any(release_dir.glob(f"{name}*.d"))

    # ------------------------------------------------------------------ tools

    def install_tool(self, tool: str) -> StepResult:
        """Report how to install a missing external tool.

        ARIA does not silently install system toolchains: a Rust or Python
        install is a machine-level change the operator should make knowingly.
        The step returns the exact command instead.
        """
        from .detector import _which  # local import keeps the detector's helpers private

        if _which(tool):
            return StepResult.skip(f"{tool} already installed")

        hints = {
            "git": "https://git-scm.com/downloads",
            "cargo": "https://rustup.rs (rustup-init.exe)",
            "rustc": "https://rustup.rs (rustup-init.exe)",
            "node": "https://nodejs.org (needs >= 22.19 for mcode)",
            "npm": "https://nodejs.org",
            "gh": "winget install --id GitHub.cli",
            "ollama": "https://ollama.com/download",
            "mcode": "irm https://filecdn.minimax.chat/public/install.ps1 | iex",
        }
        return StepResult.warn(
            f"{tool} not installed",
            tool=tool,
            hint=hints.get(tool, "install manually"),
        )


def _any_retryable(outputs) -> bool:
    """True when any output still looks like a transient failure.

    A single permanent error (an unavailable pin) settles the step, because
    re-running pip for the same requirements hours later produces the same
    result. A transient marker keeps the step eligible for a retry.
    """
    return any(is_retryable_message(text) for text in outputs)


def _crate_name(manifest: Path) -> str:
    """Read `name` out of a Cargo.toml without requiring a TOML parser."""
    for line in manifest.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith("name"):
            _, _, value = stripped.partition("=")
            return value.strip().strip('"').strip("'")
    raise OSError(f"no package name in {manifest}")
