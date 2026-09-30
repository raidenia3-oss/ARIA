"""Environment detection.

Read-only. Nothing here installs, writes or spawns a service; the detector only
answers "what does this machine look like right now" so the installer can
decide what is actually missing. Detection is cheap enough to run on every
setup invocation.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from .model import Environment

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Services ARIA talks to, and the port each one is expected on.
SERVICE_PORTS: dict[str, int] = {
    "fastapi_8000": 8000,
    "fastapi_8001": 8001,
    "axum_8002": 8002,
    "ollama_11434": 11434,
    "jan_1337": 1337,
}

# Tools worth knowing about. Absence is reported, never fatal on its own.
# Maps the tool name to the Environment attribute that records its presence.
TOOLS: dict[str, str] = {
    "git": "git_installed",
    "cargo": "cargo_installed",
    "rustc": "cargo_installed",  # rustc ships with cargo; same toolchain
    "node": "node_installed",
    "npm": "node_installed",  # npm ships with node
    "gh": "gh_cli_installed",
    "ollama": "ollama_installed",
    "mcode": "mcode_installed",
}


def _run(cmd: list[str], timeout: int = 8) -> tuple[int, str]:
    """Run a command, returning (code, output). Never raises."""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    return proc.returncode, (proc.stdout or proc.stderr or "").strip()


def _which(tool: str) -> str | None:
    return shutil.which(tool)


def _http_json(url: str, timeout: float = 2.0) -> dict | None:
    """GET a JSON endpoint. Returns None on any failure - used for probing."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return None


def _tcp_open(host: str, port: int, timeout: float = 0.6) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class EnvironmentDetector:
    """Builds an [`Environment`] snapshot for the current host."""

    def __init__(self, project_root: Path | str | None = None) -> None:
        self.project_root = Path(project_root) if project_root else PROJECT_ROOT

    def detect(self) -> Environment:
        env = Environment(
            os_name=platform.system(),
            os_release=platform.release(),
            arch=platform.machine(),
            python_version=platform.python_version(),
            python_executable=sys.executable,
            project_root=str(self.project_root),
        )

        env.in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
        env.venv_path = str(Path(sys.prefix)) if env.in_venv else ""

        self._detect_git(env)
        self._detect_rust(env)
        self._detect_node(env)
        self._detect_ollama(env)
        self._detect_gh(env)
        self._detect_mcode(env)
        self._detect_services(env)

        env.missing_tools = [
            tool for tool, attr in TOOLS.items() if not getattr(env, attr, False)
        ]
        return env

    # -------------------------------------------------------------- toolchain

    def _detect_git(self, env: Environment) -> None:
        path = _which("git")
        env.git_installed = path is not None
        if path:
            code, out = _run([path, "--version"])
            env.git_version = out.splitlines()[0] if code == 0 and out else path

    def _detect_rust(self, env: Environment) -> None:
        cargo = _which("cargo")
        env.cargo_installed = cargo is not None
        if cargo:
            code, out = _run([cargo, "--version"])
            env.cargo_version = out.splitlines()[0] if code == 0 and out else cargo

    def _detect_node(self, env: Environment) -> None:
        node = _which("node")
        env.node_installed = node is not None
        if node:
            code, out = _run([node, "--version"])
            env.node_version = out.strip() if code == 0 and out else node
        # mcode requires Node >= 22.19 before it will run.
        env.node_available = _node_major(env.node_version) >= 22

    def _detect_ollama(self, env: Environment) -> None:
        env.ollama_installed = _which("ollama") is not None
        payload = _http_json("http://127.0.0.1:11434/api/tags")
        env.ollama_running = payload is not None
        if isinstance(payload, dict):
            models = payload.get("models") or []
            names = []
            for model in models:
                if isinstance(model, dict) and model.get("name"):
                    names.append(str(model["name"]))
            env.ollama_models = names

    def _detect_gh(self, env: Environment) -> None:
        gh = _which("gh")
        env.gh_cli_installed = gh is not None
        if gh:
            # `gh auth status` exits 0 only when a token is actually usable.
            code, _ = _run([gh, "auth", "status"], timeout=12)
            env.gh_authenticated = code == 0

    def _detect_mcode(self, env: Environment) -> None:
        env.mcode_installed = _which("mcode") is not None

    # --------------------------------------------------------------- services

    def _detect_services(self, env: Environment) -> None:
        for name, port in SERVICE_PORTS.items():
            env.services[name] = _tcp_open("127.0.0.1", port)

    # ------------------------------------------------------------------ utils

    def find_requirements_files(self) -> list[Path]:
        """Requirements files that actually exist, most relevant first."""
        candidates = [
            self.project_root / "requirements.txt",
            self.project_root / "ARIA_APP" / "requirements.txt",
        ]
        return [path for path in candidates if path.is_file()]

    def find_cargo_manifests(self) -> list[Path]:
        """Rust crates. Skips `target/` so build output is never treated as a crate."""
        manifests: list[Path] = []
        for depth in (1, 2):
            pattern = "/".join(["*"] * depth) + "/Cargo.toml"
            for manifest in self.project_root.glob(pattern):
                if "target" in manifest.parts:
                    continue
                if manifest.is_file():
                    manifests.append(manifest)
        return sorted(set(manifests))

    def find_env_files(self) -> list[Path]:
        """Every `.env`-like file ARIA reads, in load-priority order."""
        names = [".env", ".env.ai", ".env.cloud"]
        found: list[Path] = []
        directories = (
            self.project_root,
            self.project_root / "ARIA_APP",
            self.project_root / "ARIA_APP" / "backend",
        )
        for directory in directories:
            for name in names:
                candidate = directory / name
                if candidate.is_file():
                    found.append(candidate)
        return found

    def python_site_packages_ok(self, package: str) -> bool:
        """True when `package` imports in the *current* interpreter."""
        code, _ = _run([sys.executable, "-c", f"import {package}"], timeout=20)
        return code == 0


def _node_major(version: str) -> int:
    digits = version.lstrip("v").split(".")
    try:
        return int(digits[0]) if digits else 0
    except ValueError:
        return 0


def read_env_keys(path: Path) -> dict[str, str]:
    """Parse a `.env` file into a key -> value mapping.

    Best effort: a malformed line is skipped rather than raising, because
    setup must survive a hand-edited env file.
    """
    result: dict[str, str] = {}
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return result
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export ") :].strip()
        if key:
            result[key] = value.strip().strip('"').strip("'")
    return result


def env_value_looks_real(value: str) -> bool:
    """False for empty values and for the obvious placeholders.

    Placeholders are what ship in `.env.example`; treating them as configured
    is the classic way an auto-setup reports success on a machine that has
    nothing configured.
    """
    if not value:
        return False
    lowered = value.strip().lower()
    if lowered in {"changeme", "todo", "none", "null", "unset"}:
        return False
    if "your-" in lowered or lowered.startswith("your_"):
        return False
    if "xxx" in lowered or "placeholder" in lowered or "<" in lowered:
        return False
    return True
