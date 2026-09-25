"""ARIA Desktop Tray — system tray icon + global hotkey + orb summon."""

from __future__ import annotations

import os
import sys
import threading
import time
import json
import queue
import subprocess
from pathlib import Path
from typing import Optional, Callable, Any

import pystray
import keyboard
from PIL import Image, ImageDraw, ImageFont


ARIA_APP_DIR = Path(__file__).resolve().parent


def _create_icon_image() -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (5, 8, 22, 255))
    draw = ImageDraw.Draw(img)
    cx, cy, r = size // 2, size // 2, 18
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(56, 189, 248, 255))
    r2 = r + 8
    draw.ellipse([cx - r2, cy - r2, cx + r2, cy + r2],
                  outline=(124, 77, 255, 200), width=3)
    r3 = r2 + 8
    draw.ellipse([cx - r3, cy - r3, cx + r3, cy + r3],
                  outline=(124, 77, 255, 60), width=2)
    return img


class DesktopTray:
    """System tray icon with hotkey listener."""

    HOTKEY = "ctrl+shift+a"

    def __init__(self, on_summon: Optional[Callable] = None,
                 on_quit: Optional[Callable] = None) -> None:
        self.on_summon = on_summon
        self.on_quit = on_quit
        self._icon: Optional[pystray.Icon] = None
        self._running = False
        self._hotkey_thread: Optional[threading.Thread] = None
        self._queue: queue.Queue = queue.Queue()
        self._last_summon = 0.0
        self._cooldown = 2.0

    def start(self) -> None:
        self._running = True
        self._hotkey_thread = threading.Thread(
            target=self._hotkey_loop, daemon=True, name="tray-hotkey")
        self._hotkey_thread.start()

        img = _create_icon_image()
        self._icon = pystray.Icon("ARIA", img, "ARIA OS",
                                   menu=self._build_menu())
        threading.Thread(target=self._run_icon, daemon=True,
                          name="tray-icon").start()

    def _run_icon(self) -> None:
        try:
            self._icon.run()
        except Exception:
            pass

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem("ARIA OS v2.0", self._on_menu_summon),
            pystray.MenuItem("Mostrar HUD", self._on_menu_show),
            pystray.MenuItem("Status", self._on_menu_status),
            pystray.MenuItem("Auto-start", self._on_menu_toggle_autostart),
            pystray.MenuItem(pystray.SEPARATOR),
            pystray.MenuItem("Salir", self._on_menu_quit),
        )

    def _on_menu_summon(self) -> None:
        self._summon()

    def _on_menu_show(self) -> None:
        if self.on_summon:
            self.on_summon("show")

    def _on_menu_status(self) -> None:
        status = self._get_status()
        print(f"[AURA Tray] {json.dumps(status, ensure_ascii=False)}")

    def _on_menu_toggle_autostart(self) -> None:
        try:
            from auto_start import register, unregister, is_registered
            if is_registered():
                unregister()
                print("[AURA Tray] Auto-start desactivado")
            else:
                exe = os.path.join(str(ARIA_APP_DIR.parent), "dist", "ARIA OS.exe")
                register(exe if os.path.exists(exe) else None)
                print("[AURA Tray] Auto-start activado")
        except Exception as e:
            print(f"[AURA Tray] Auto-start error: {e}")

    def _on_menu_quit(self) -> None:
        self._running = False
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
        if self.on_quit:
            self.on_quit()

    def _summon(self) -> None:
        now = time.time()
        if now - self._last_summon < self._cooldown:
            return
        self._last_summon = now
        if self.on_summon:
            self.on_summon("hotkey")

    def _hotkey_loop(self) -> None:
        try:
            keyboard.add_hotkey(self.HOTKEY, self._summon, suppress=True)
        except Exception as e:
            print(f"[AURA Tray] Hotkey error: {e}")

        while self._running:
            try:
                action = self._queue.get(timeout=1.0)
                if action == "summon":
                    self._summon()
            except queue.Empty:
                pass

    def _get_status(self) -> Dict[str, Any]:
        info: Dict[str, Any] = {
            "running": self._running,
            "hotkey": self.HOTKEY,
            "last_summon": self._last_summon,
        }
        try:
            from auto_start import is_registered
            info["autostart"] = is_registered()
        except Exception:
            pass
        return info

    def stop(self) -> None:
        self._running = False
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
