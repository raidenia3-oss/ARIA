"""PARTE 7: INVISIBLE MODE + TRAY (200 lines) — Modo invisible con tray icon.

Funciones async:
- toggle_invisible_mode(): núcleo desaparece, tray aparece
- Tray icon features: click toggle, right-click menu
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    import pystray

    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False

try:
    from PIL import Image, ImageDraw, ImageFont

    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import win32api
    import win32con
    import win32gui

    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

try:
    import ctypes

    HAS_CTYPES = True
except ImportError:
    HAS_CTYPES = False


@dataclass
class InvisibleModeState:
    invisible: bool = False
    tray_active: bool = False
    monitoring_active: bool = True
    hotkey_set: bool = False
    last_toggle_time: float = 0.0
    toggle_count: int = 0


class AuraInvisibleMode:
    """Modo invisible: núcleo oculto, tray icon activo."""

    HOTKEY_ALT_A = 0x0041

    def __init__(self):
        self.state = InvisibleModeState()
        self._tray_icon: Optional[Any] = None
        self._window_hidden = False
        self._original_window_handle: Optional[int] = None
        self._hotkey_id = 1001
        self._callbacks: Dict[str, Any] = {}
        self._os_name = sys.platform

    async def toggle_invisible_mode(self) -> Dict[str, Any]:
        """Toggle entre visible e invisible."""
        self.state.invisible = not self.state.invisible
        self.state.toggle_count += 1
        self.state.last_toggle_time = time.time()

        if self.state.invisible:
            await self._hide_core()
            await self._show_tray()
        else:
            await self._show_core()
            await self._hide_tray()

        self.state.hotkey_set = True

        return {
            "invisible": self.state.invisible,
            "tray_active": self.state.tray_active,
            "monitoring_active": self.state.monitoring_active,
            "toggle_count": self.state.toggle_count,
            "timestamp": time.time(),
        }

    async def _hide_core(self) -> None:
        """Oculta núcleo visual."""
        self.state.monitoring_active = True
        self._window_hidden = True

        if HAS_WIN32:
            try:
                hwnd = win32gui.GetForegroundWindow()
                if hwnd:
                    self._original_window_handle = hwnd
                    win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
            except Exception:
                pass

        if self._callbacks.get("on_hide"):
            try:
                await self._callbacks["on_hide"]()
            except Exception:
                pass

    async def _show_core(self) -> None:
        """Muestra núcleo visual."""
        self._window_hidden = False

        if HAS_WIN32 and self._original_window_handle:
            try:
                win32gui.ShowWindow(self._original_window_handle, win32con.SW_SHOW)
                win32gui.SetForegroundWindow(self._original_window_handle)
                self._original_window_handle = None
            except Exception:
                pass

        if self._callbacks.get("on_show"):
            try:
                await self._callbacks["on_show"]()
            except Exception:
                pass

    async def _show_tray(self) -> None:
        """Muestra tray icon."""
        self.state.tray_active = True

        if HAS_PYSTRAY:
            try:
                menu = pystray.Menu(
                    pystray.MenuItem("Estado", self._tray_status),
                    pystray.MenuItem("Configuración", self._tray_settings),
                    pystray.MenuItem("Screenshot", self._tray_screenshot),
                    pystray.MenuItem("Logs", self._tray_logs),
                    pystray.MenuItem("Salir", self._tray_quit),
                )
                icon_image = self._create_tray_image()
                self._tray_icon = pystray.Icon(
                    "ARIA OS",
                    icon_image,
                    "ARIA OS - Invisible Mode",
                    menu,
                )
                self._tray_icon.run()
            except Exception:
                self.state.tray_active = False
        else:
            self.state.tray_active = False

    async def _hide_tray(self) -> None:
        """Oculta tray icon."""
        self.state.tray_active = False
        if self._tray_icon:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
            self._tray_icon = None

    def _create_tray_image(self, size=(64, 64)):
        """Crea imagen del tray icon."""
        if not HAS_PIL:
            return None

        image = Image.new("RGB", size, (10, 14, 39))
        draw = ImageDraw.Draw(image)

        cx, cy = size[0] // 2, size[1] // 2
        for r in range(20, 0, -3):
            alpha_ratio = r / 20.0
            color = (
                int(0 * alpha_ratio),
                int(255 * alpha_ratio),
                int(136 * alpha_ratio),
            )
            draw.ellipse(
                [cx - r, cy - r, cx + r, cy + r],
                fill=color,
                outline=color,
            )

        draw.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=(0, 255, 136))

        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
        draw.text((cx - 10, cy - 5), "A", fill=(10, 14, 39), font=font)

        return image

    async def _tray_status(self) -> None:
        if self._callbacks.get("tray_status"):
            try:
                await self._callbacks["tray_status"]()
            except Exception:
                pass

    async def _tray_settings(self) -> None:
        if self._callbacks.get("tray_settings"):
            try:
                await self._callbacks["tray_settings"]()
            except Exception:
                pass

    async def _tray_screenshot(self) -> None:
        if self._callbacks.get("tray_screenshot"):
            try:
                await self._callbacks["tray_screenshot"]()
            except Exception:
                pass

    async def _tray_logs(self) -> None:
        if self._callbacks.get("tray_logs"):
            try:
                await self._callbacks["tray_logs"]()
            except Exception:
                pass

    async def _tray_quit(self) -> None:
        if self._callbacks.get("tray_quit"):
            try:
                await self._callbacks["tray_quit"]()
            except Exception:
                pass

    async def register_hotkey(self) -> bool:
        """Registra hotkey Alt+A para toggle."""
        if not HAS_CTYPES:
            return False

        try:
            user32 = ctypes.windll.user32
            hinstance = ctypes.windll.kernel32.GetModuleHandleW(None)
            self._hotkey_id = 1001
            VK_MENU = 0x12
            VK_A = 0x41
            MOD_ALT = 0x0001

            result = user32.RegisterHotKey(None, self._hotkey_id, MOD_ALT, VK_A)
            if result:
                self.state.hotkey_set = True
                return True
        except Exception:
            pass

        return False

    async def unregister_hotkey(self) -> bool:
        """Desregistra hotkey."""
        if not HAS_CTYPES:
            return False
        try:
            user32 = ctypes.windll.user32
            user32.UnregisterHotKey(None, self._hotkey_id)
            self.state.hotkey_set = False
            return True
        except Exception:
            return False

    def set_callback(self, name: str, callback: Any) -> None:
        """Registra callback para eventos del tray."""
        self._callbacks[name] = callback

    def get_status(self) -> Dict[str, Any]:
        return {
            "invisible": self.state.invisible,
            "tray_active": self.state.tray_active,
            "monitoring_active": self.state.monitoring_active,
            "hotkey_set": self.state.hotkey_set,
            "toggle_count": self.state.toggle_count,
            "last_toggle": self.state.last_toggle_time,
            "window_hidden": self._window_hidden,
        }

    async def start_monitoring_loop(self, interval: float = 5.0) -> None:
        """Loop de monitoreo en invisible mode."""
        self.state.monitoring_active = True
        while self.state.monitoring_active:
            try:
                if self.state.invisible:
                    if self._callbacks.get("invisible_monitor"):
                        await self._callbacks["invisible_monitor"]()
            except Exception:
                pass
            await asyncio.sleep(interval)

    async def stop(self) -> None:
        """Detiene todo."""
        self.state.monitoring_active = False
        self.state.invisible = False
        await self._hide_tray()
        await self.unregister_hotkey()
