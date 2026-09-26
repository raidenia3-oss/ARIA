"""Tests for BLOQUE 59 - AURA Desktop App Shell & System Tray Integration.

Validates:
- Backend process manager lifecycle (start/stop/status)
- Desktop shell configuration integrity
- Global hotkey configuration
- Frameless window configuration

100% local: no cloud dependencies.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DESKTOP_DIR = PROJECT_ROOT / "desktop"


class TestBackendManager:
    """Tests for the Python backend process manager."""

    @pytest.fixture()
    def backend_manager(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "backend_manager", DESKTOP_DIR / "backend-manager.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_backend_manager_module_importable(self, backend_manager):
        assert hasattr(backend_manager, "start_backend")
        assert hasattr(backend_manager, "stop_backend")
        assert hasattr(backend_manager, "get_backend_status")

    def test_get_python_executable_returns_string(self, backend_manager):
        exe = backend_manager.get_python_executable()
        assert isinstance(exe, str)
        assert len(exe) > 0

    def test_get_backend_status_returns_dict(self, backend_manager):
        status = backend_manager.get_backend_status()
        assert isinstance(status, dict)
        assert "running" in status
        assert "host" in status
        assert "port" in status
        assert "health_url" in status
        assert status["host"] == "127.0.0.1"
        assert status["port"] == 8000

    def test_stop_backend_when_not_running(self, backend_manager):
        pid_file = Path(backend_manager.PID_FILE)
        pid_file.unlink(missing_ok=True)
        result = backend_manager.stop_backend()
        assert result is False


class TestDesktopShellConfig:
    """Tests for the desktop shell configuration integrity."""

    def test_package_json_exists(self):
        pkg_path = DESKTOP_DIR / "package.json"
        assert pkg_path.exists(), f"Missing {pkg_path}"

    def test_package_json_has_valid_structure(self):
        pkg_path = DESKTOP_DIR / "package.json"
        with open(pkg_path, "r", encoding="utf-8") as f:
            pkg = json.load(f)
        assert pkg["name"] == "aura-desktop"
        assert pkg["main"] == "main.js"
        assert "electron" in pkg.get("dependencies", {})

    def test_build_config_present(self):
        pkg_path = DESKTOP_DIR / "package.json"
        with open(pkg_path, "r", encoding="utf-8") as f:
            pkg = json.load(f)
        build = pkg.get("build", {})
        assert "productName" in build
        assert build["productName"] == "AURA"
        assert "files" in build
        assert isinstance(build["files"], list)
        assert len(build["files"]) > 0

    def test_main_js_exists(self):
        assert (DESKTOP_DIR / "main.js").exists()

    def test_preload_js_exists(self):
        assert (DESKTOP_DIR / "preload.js").exists()

    def test_backend_manager_py_exists(self):
        assert (DESKTOP_DIR / "backend-manager.py").exists()

    def test_shortcuts_js_exists(self):
        assert (DESKTOP_DIR / "shortcuts.js").exists()

    def test_tray_js_exists(self):
        assert (DESKTOP_DIR / "tray.js").exists()

    def test_window_js_exists(self):
        assert (DESKTOP_DIR / "window.js").exists()


class TestGlobalHotkeysConfig:
    """Tests for global hotkey configuration."""

    def test_shortcuts_js_exists(self):
        assert (DESKTOP_DIR / "shortcuts.js").exists()

    def test_shortcuts_js_has_required_combinations(self):
        shortcuts_path = DESKTOP_DIR / "shortcuts.js"
        content = shortcuts_path.read_text(encoding="utf-8", errors="replace")
        assert "Ctrl+Alt+A" in content
        assert "Ctrl+Alt+H" in content
        assert "Ctrl+Alt+T" in content
        assert "registerAll" in content
        assert "unregisterAll" in content


class TestFramelessWindowConfig:
    """Tests for frameless and translucent window configuration."""

    def test_window_js_exists(self):
        assert (DESKTOP_DIR / "window.js").exists()

    def test_window_js_has_frameless_config(self):
        window_path = DESKTOP_DIR / "window.js"
        content = window_path.read_text(encoding="utf-8", errors="replace")
        assert "frame: false" in content
        assert "transparent: true" in content
        assert "backgroundColor: '#00000000'" in content
        assert "hasShadow: true" in content

    def test_window_js_has_float_mode(self):
        window_path = DESKTOP_DIR / "window.js"
        content = window_path.read_text(encoding="utf-8", errors="replace")
        assert "makeFloatMode" in content
        assert "makeWindowMode" in content


class TestNoSecretsExposed:
    """Verify no plaintext secrets in desktop shell files."""

    SENSITIVE_PATTERNS = [
        "api_key",
        "API_KEY",
        "token",
        "TOKEN",
        "secret",
        "SECRET",
        "password",
        "PASSWORD",
        "credential",
        "CREDENTIAL",
    ]

    DESKTOP_FILES = [
        "main.js",
        "preload.js",
        "tray.js",
        "shortcuts.js",
        "window.js",
        "backend-manager.py",
        "package.json",
    ]

    def test_no_secrets_in_desktop_files(self):
        for filename in self.DESKTOP_FILES:
            filepath = DESKTOP_DIR / filename
            if not filepath.exists():
                continue
            content = filepath.read_text(encoding="utf-8", errors="replace")
            for pattern in self.SENSITIVE_PATTERNS:
                # Allow env var references (os.getenv / process.env)
                if f"getenv({pattern.lower()}" in content:
                    continue
                if f"env.{pattern.lower()}" in content:
                    continue
                assert pattern not in content, f"Potential secret '{pattern}' found in {filename}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
