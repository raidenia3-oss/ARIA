# -*- coding: utf-8 -*-
"""AURA OS - IDE Controller Integration (Android Studio + Godot + VS Code + Antigravity).

Wraps AME/local_app_controller.py for backend use and exposes
Android Studio, Godot, VS Code and Antigravity operations as REST endpoints.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path for AME import
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from AME.local_app_controller import LocalAppController  # noqa: E402


class IDEController:
    """High-level controller for Android Studio, Godot, VS Code, Antigravity."""

    def __init__(self) -> None:
        self._app = LocalAppController()

    @property
    def app_controller(self) -> LocalAppController:
        return self._app

    def get_installed_apps(self) -> Dict[str, Any]:
        """Return status of all tracked apps."""
        result = {}
        for name, info in self._app.apps.items():
            result[name] = {
                "installed": info["installed"],
                "path": info["path"],
                "running": self._app.is_running(name),
            }
        return result

    # --- Android Studio ---

    def android_open(self, project_path: str = "") -> Dict[str, Any]:
        return self._app.android_studio_open_project(project_path)

    def android_run_gradle(self, project_path: str, task: str = "assembleDebug") -> Dict[str, Any]:
        return self._app.android_studio_run_gradle(project_path, task)

    def android_find_projects(self, base_dir: str = "") -> Dict[str, Any]:
        return self._app.android_studio_get_projects(base_dir)

    def android_get_status(self) -> Dict[str, Any]:
        studio = self._app.apps.get("android_studio", {})
        return {
            "installed": studio.get("installed", False),
            "path": studio.get("path", ""),
            "running": self._app.is_running("android_studio"),
        }

    # --- Godot ---

    def godot_run(self, project_path: str) -> Dict[str, Any]:
        return self._app.godot_run_project(project_path)

    def godot_get_status(self) -> Dict[str, Any]:
        godot = self._app.apps.get("godot", {})
        return {
            "installed": godot.get("installed", False),
            "path": godot.get("path", ""),
            "running": self._app.is_running("godot"),
        }

    def godot_find_projects(self, base_dir: str = "") -> Dict[str, Any]:
        """Find Godot projects (project.godot files) in a directory tree."""
        base = Path(base_dir) if base_dir else _ROOT
        if not base.is_dir():
            return {"ok": False, "error": f"Directorio no encontrado: {base}"}
        projects = []
        for proj_file in base.rglob("project.godot"):
            proj_dir = proj_file.parent
            projects.append({
                "name": proj_dir.name,
                "path": str(proj_dir),
                "size_mb": sum(f.stat().st_size for f in proj_dir.rglob("*") if f.is_file()) // (1024 * 1024),
            })
        return {"ok": True, "projects": projects[:30], "total": len(projects)}

    # --- VS Code ---

    def vscode_open(self, path: str = "") -> Dict[str, Any]:
        return self._app.vs_code_open(path)

    def vscode_get_status(self) -> Dict[str, Any]:
        code = self._app.apps.get("vs_code", {})
        return {
            "installed": code.get("installed", False),
            "path": code.get("path", ""),
            "running": self._app.is_running("vs_code"),
        }

    # --- Antigravity ---

    def antigravity_open(self, path: str = "") -> Dict[str, Any]:
        return self._app.antigravity_open(path)

    def antigravity_get_status(self) -> Dict[str, Any]:
        ag = self._app.apps.get("antigravity", {})
        return {
            "installed": ag.get("installed", False),
            "path": ag.get("path", ""),
            "running": self._app.is_running("antigravity"),
        }

    # --- Generic ---

    def kill_app(self, app_name: str) -> Dict[str, Any]:
        return self._app.kill(app_name)

    def run_command(self, command: str, cwd: Optional[str] = None) -> Dict[str, Any]:
        return self._app.run_command(command, cwd)


# Singleton
_ide: Optional[IDEController] = None


def get_ide_controller() -> IDEController:
    global _ide
    if _ide is None:
        _ide = IDEController()
    return _ide
