"""ARIA Auto-Start — registers the app in Windows startup."""

from __future__ import annotations

import os
import sys
import json
import time
import winreg
from pathlib import Path
from typing import Any, Dict


STARTUP_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "ARIA OS"


def is_registered() -> bool:
    """Checks if AURA is already in Windows startup."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY_PATH, 0,
                            winreg.KEY_READ) as key:
            for i in range(1024):
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                    if name == APP_NAME:
                        return True
                except OSError:
                    break
    except Exception:
        pass
    return False


def register(exe_path: str = None) -> bool:
    """Adds AURA to Windows startup.

    Args:
        exe_path: Path to the AURA executable. If None, auto-detects.
    """
    if exe_path is None:
        exe_path = _detect_exe_path()
    if not exe_path or not os.path.exists(exe_path):
        return False

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY_PATH, 0,
                            winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
        return True
    except Exception:
        return False


def unregister() -> bool:
    """Removes AURA from Windows startup."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY_PATH, 0,
                            winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_NAME)
        return True
    except Exception:
        return False


def _detect_exe_path() -> str:
    """Auto-detects the AURA exe path."""
    exe = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dist", "ARIA OS.exe")
    if os.path.exists(exe):
        return os.path.abspath(exe)
    py = sys.executable
    standalone = os.path.join(os.path.dirname(os.path.abspath(__file__)), "standalone.py")
    if os.path.exists(standalone):
        return f'"{py}" "{standalone}"'
    return ""


def get_status() -> Dict[str, Any]:
    return {
        "registered": is_registered(),
        "exe_path": _detect_exe_path(),
    }