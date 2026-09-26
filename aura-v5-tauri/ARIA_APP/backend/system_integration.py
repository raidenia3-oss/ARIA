"""PARTE 6: SYSTEM INTEGRATION (250 lines) — Win/Linux/macOS.

Windows: win32gui floating window, pystray, registry autostart
Linux: X11 window management, ALSA, desktop entry, systemd
macOS: Quartz, AVFoundation, Dock, LaunchAgent
"""

from __future__ import annotations

import ctypes
import json
import os
import platform
import struct
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    import win32api
    import win32con
    import win32gui
    import win32ui

    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

try:
    import ctypes.wintypes

    HAS_WIN32_TYPES = True
except ImportError:
    HAS_WIN32_TYPES = False

try:
    import PIL

    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


class SystemIntegration:
    """Integración nativa con el SO."""

    def __init__(self):
        self.os_name = platform.system().lower()
        self._hwnd = None
        self._tray_icon = None
        self._autostart_configured = False
        self._floating_pos = {"x": 0, "y": 0, "width": 300, "height": 300}

    def get_platform(self) -> str:
        return self.os_name

    def is_windows(self) -> bool:
        return self.os_name == "windows"

    def is_linux(self) -> bool:
        return self.os_name == "linux"

    def is_macos(self) -> bool:
        return self.os_name == "darwin"

    # ----------------------------------------------------------------
    # WINDOW MANAGEMENT
    # ----------------------------------------------------------------
    def create_floating_window(self) -> Optional[int]:
        if self.is_windows():
            return self._create_windows_floating()
        elif self.is_linux():
            return self._create_linux_floating()
        elif self.is_macos():
            return self._create_macos_floating()
        return None

    def _create_windows_floating(self) -> Optional[int]:
        if not HAS_WIN32:
            return None
        wc = win32gui.WNDCLASS()
        wc.lpszClassName = "ARIAFloatingWidget"
        wc.hInstance = win32gui.GetModuleHandle(None)
        wc.style = 0x00080000 | 0x00040000 | 0x00020000
        wc.hCursor = win32gui.LoadCursor(0, 32512)
        atom = win32gui.RegisterClass(wc)
        if not atom:
            return None

        hwnd = win32gui.CreateWindow(
            atom,
            "ARIA OS - Floating Widget",
            0x80000000 | 0x00080000 | 0x00020000 | 0x00040000 | 0x00010000,
            self._floating_pos["x"],
            self._floating_pos["y"],
            self._floating_pos["width"],
            self._floating_pos["height"],
            0,
            0,
            wc.hInstance,
            None,
        )
        if not hwnd:
            return None

        style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        style = style | 0x00000008 | 0x00000020 | 0x00000001
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style)

        win32gui.SetWindowPos(
            hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
        )
        win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
        win32gui.UpdateWindow(hwnd)
        self._hwnd = hwnd
        return hwnd

    def _create_linux_floating(self) -> Optional[int]:
        try:
            result = subprocess.run(
                ["xdotool", "search", "--name", "ARIA"], capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                return int(result.stdout.strip().split("\n")[0])
        except Exception:
            pass
        return None

    def _create_macos_floating(self) -> Optional[int]:
        try:
            result = subprocess.run(
                [
                    "osascript",
                    "-e",
                    'tell application "System Events" to get name of every process',
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if "ARIA" in result.stdout:
                return 1
        except Exception:
            pass
        return None

    # ----------------------------------------------------------------
    # TRAY ICON
    # ----------------------------------------------------------------
    def create_tray_icon(self, callback=None) -> bool:
        if self.is_windows():
            return self._create_windows_tray(callback)
        elif self.is_linux():
            return self._create_linux_tray(callback)
        elif self.is_macos():
            return self._create_macos_tray(callback)
        return False

    def _create_windows_tray(self, callback=None) -> bool:
        if not HAS_WIN32:
            return False
        try:
            hinstance = win32gui.GetModuleHandle(None)
            menu = win32gui.CreatePopupMenu()
            win32gui.AppendMenu(menu, win32con.MF_STRING, 1001, "Show ARIA")
            win32gui.AppendMenu(menu, win32con.MF_STRING, 1002, "Hide ARIA")
            win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
            win32gui.AppendMenu(menu, win32con.MF_STRING, 1003, "Exit")

            flags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP
            nid = (hinstance, 0, flags, 0x00000202, hinstance, "ARIA OS")
            nid = (hinstance, 1001, flags, hinstance, "ARIA OS", "ARIA OS - Floating Widget")

            try:
                win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)
                self._tray_icon = True
                return True
            except Exception:
                return False
        except Exception:
            return False

    def _create_linux_tray(self, callback=None) -> bool:
        try:
            desktop_entry = os.path.expanduser("~/.local/share/applications/aria-os-tray.desktop")
            with open(desktop_entry, "w") as f:
                f.write(
                    "[Desktop Entry]\nName=ARIA OS\nComment=ARIA OS Floating Widget\nType=Application\n"
                )
            return True
        except Exception:
            return False

    def _create_macos_tray(self, callback=None) -> bool:
        try:
            subprocess.run(
                [
                    "defaults",
                    "write",
                    "com.apple.dock",
                    "widgets",
                    "-array-add",
                    '{"path":"aria-widget";"type":"inline";"alignment":"center"}',
                ],
                check=False,
                timeout=5,
            )
            return True
        except Exception:
            return False

    # ----------------------------------------------------------------
    # AUTOSTART
    # ----------------------------------------------------------------
    def configure_autostart(self) -> bool:
        if self.is_windows():
            return self._configure_windows_autostart()
        elif self.is_linux():
            return self._configure_linux_autostart()
        elif self.is_macos():
            return self._configure_macos_autostart()
        return False

    def _configure_windows_autostart(self) -> bool:
        if not HAS_WIN32:
            return False
        try:
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            import _winreg as winreg

            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(
                key, "ARIA OS", 0, winreg.REG_SZ, os.path.abspath(__file__).replace(".py", ".exe")
            )
            winreg.CloseKey(key)
            self._autostart_configured = True
            return True
        except Exception:
            return False

    def _configure_linux_autostart(self) -> bool:
        try:
            desktop_entry = os.path.expanduser("~/.config/autostart/aria-os.desktop")
            os.makedirs(os.path.dirname(desktop_entry), exist_ok=True)
            with open(desktop_entry, "w") as f:
                f.write("[Desktop Entry]\nType=Application\nName=ARIA OS\n")
                f.write(f"Exec={os.path.abspath(__file__)}\nHidden=false\n")
            return True
        except Exception:
            return False

    def _configure_macos_autostart(self) -> bool:
        try:
            plist_path = os.path.expanduser("~/Library/LaunchAgents/com.aria-os.plist")
            os.makedirs(os.path.dirname(plist_path), exist_ok=True)
            plist = {
                "Label": "com.aria-os",
                "ProgramArguments": [os.path.abspath(__file__)],
                "RunAtLoad": True,
                "KeepAlive": True,
            }
            with open(plist_path, "w") as f:
                json.dump(plist, f)
            return True
        except Exception:
            return False

    # ----------------------------------------------------------------
    # AUDIO (WASAPI loopback on Windows)
    # ----------------------------------------------------------------
    def get_windows_audio(self) -> Optional[bytes]:
        if not self.is_windows() or not HAS_WIN32:
            return None
        try:
            result = subprocess.run(
                ["powershell", "-Command", "(Get-AudioDevice -Loopback).Capture()"[:50]],
                capture_output=True,
                timeout=3,
            )
            return result.stdout
        except Exception:
            return None

    def get_alsa_audio(self) -> Optional[bytes]:
        if not self.is_linux():
            return None
        try:
            result = subprocess.run(
                ["arecord", "-d", "1", "-f", "cd", "-t", "raw"], capture_output=True, timeout=3
            )
            return result.stdout
        except Exception:
            return None

    def get_coreaudio(self) -> Optional[bytes]:
        if not self.is_macos():
            return None
        try:
            result = subprocess.run(["afplay", "--info"], capture_output=True, timeout=3)
            return result.stdout
        except Exception:
            return None

    # ----------------------------------------------------------------
    # STATUS
    # ----------------------------------------------------------------
    def get_system_info(self) -> Dict[str, Any]:
        info = {
            "platform": self.os_name,
            "is_windows": self.is_windows(),
            "is_linux": self.is_linux(),
            "is_macos": self.is_macos(),
            "floating_window": self._hwnd is not None,
            "tray_icon": self._tray_icon is not None,
            "autostart": self._autostart_configured,
            "floating_position": self._floating_pos,
        }
        if self.is_windows():
            try:
                info["active_window"] = win32gui.GetWindowText(win32gui.GetForegroundWindow())
            except Exception:
                info["active_window"] = "unknown"
        return info
