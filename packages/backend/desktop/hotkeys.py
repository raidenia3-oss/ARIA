"""AURA Global Hotkey Listener (Bloque 75)."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("AURA.Hotkeys")

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
VK_A = 0x41
VK_M = 0x4D
VK_Q = 0x51
VK_S = 0x53
VK_F1 = 0x70
VK_ESCAPE = 0x1B
VK_SPACE = 0x20


@dataclass
class HotkeyBinding:
    id: int
    modifiers: int
    vk_code: int
    label: str
    callback: Callable
    description: str = ""

    @property
    def key_string(self) -> str:
        parts = []
        if self.modifiers & MOD_CONTROL:
            parts.append("Ctrl")
        if self.modifiers & MOD_ALT:
            parts.append("Alt")
        if self.modifiers & MOD_SHIFT:
            parts.append("Shift")
        if self.modifiers & MOD_WIN:
            parts.append("Win")
        parts.append(self._vk_to_name(self.vk_code))
        return "+".join(parts)

    @staticmethod
    def _vk_to_name(vk: int) -> str:
        special = {VK_F1: "F1", VK_ESCAPE: "Esc", VK_SPACE: "Space"}
        if vk in special:
            return special[vk]
        if 0x41 <= vk <= 0x5A:
            return chr(vk)
        if 0x30 <= vk <= 0x39:
            return chr(vk)


class GlobalHotkeyListener:
    """Listens for global Win32 hotkeys on a background thread."""

    def __init__(self) -> None:
        self._bindings: Dict[int, HotkeyBinding] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._next_id = 1

    def register_hotkey(self, modifiers, vk_code, callback, label="", description="") -> int:
        with self._lock:
            hk_id = self._next_id
            self._next_id += 1
            binding = HotkeyBinding(id=hk_id, modifiers=modifiers, vk_code=vk_code,
                                    label=label or f"HK_{hk_id}", callback=callback, description=description)
            self._bindings[hk_id] = binding
            if self._running:
                self._register_win32(binding)
            return hk_id

    def unregister_hotkey(self, hk_id) -> bool:
        with self._lock:
            b = self._bindings.pop(hk_id, None)
            if b and self._running:
                try:
                    ctypes.windll.user32.UnregisterHotKey(None, hk_id)
                except Exception:
                    pass
            return b is not None

    def _register_win32(self, binding) -> bool:
        try:
            result = ctypes.windll.user32.RegisterHotKey(None, binding.id, binding.modifiers, binding.vk_code)
            if result:
                logger.info("Registered hotkey: %s", binding.key_string)
            return bool(result)
        except Exception as e:
            logger.error("Error registering hotkey: %s", e)
            return False

    def register_defaults(self, callbacks=None) -> list:
        cb = callbacks or {}
        ids = []
        defaults = [
            (MOD_CONTROL | MOD_ALT, VK_A, "toggle_overlay", "Toggle AURA Overlay", cb.get("toggle_overlay")),
            (MOD_CONTROL | MOD_ALT, VK_M, "toggle_mic", "Toggle Microphone", cb.get("toggle_mic")),
            (MOD_CONTROL | MOD_ALT, VK_S, "screenshot", "Take Screenshot", cb.get("screenshot")),
            (MOD_CONTROL | MOD_ALT, VK_Q, "quit", "Quit AURA", cb.get("quit")),
        ]
        for mods, vk, label, desc, callback in defaults:
            if callback:
                ids.append(self.register_hotkey(mods, vk, callback, label, desc))
        return ids

    def _message_loop(self):
        with self._lock:
            for b in self._bindings.values():
                self._register_win32(b)
        msg = ctypes.wintypes.MSG()
        while self._running:
            result = ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result == 0 or result == -1:
                break
            if msg.message == WM_HOTKEY:
                hk_id = msg.wParam
                with self._lock:
                    binding = self._bindings.get(hk_id)
                if binding and binding.callback:
                    try:
                        binding.callback()
                    except Exception as e:
                        logger.error("Hotkey callback error [%s]: %s", binding.label, e)
            ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
            ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))

    def start(self):
        if self._running:
            return
        self._running = True
        self._message_loop()

    def stop(self):
        self._running = False
        with self._lock:
            for hk_id in list(self._bindings.keys()):
                try:
                    ctypes.windll.user32.UnregisterHotKey(None, hk_id)
                except Exception:
                    pass

    def start_background(self):
        self._thread = threading.Thread(target=self.start, daemon=True, name="AURA-Hotkeys")
        self._thread.start()

    @property
    def is_running(self):
        return self._running

    def get_bindings(self):
        with self._lock:
            return [{"id": b.id, "label": b.label, "description": b.description,
                     "key_string": b.key_string, "modifiers": b.modifiers, "vk_code": b.vk_code}
                    for b in self._bindings.values()]

    def status(self):
        return {"running": self._running, "bindings_count": len(self._bindings), "bindings": self.get_bindings()}


_listener = None
_listener_lock = threading.Lock()


def get_hotkey_listener():
    global _listener
    if _listener is None:
        with _listener_lock:
            if _listener is None:
                _listener = GlobalHotkeyListener()
    return _listener


def reset_hotkey_listener():
    global _listener
    with _listener_lock:
        if _listener and _listener.is_running:
            _listener.stop()
        _listener = None


__all__ = ["GlobalHotkeyListener", "HotkeyBinding", "get_hotkey_listener", "reset_hotkey_listener",
                      "MOD_ALT", "MOD_CONTROL", "MOD_SHIFT", "MOD_WIN", "VK_A", "VK_M", "VK_Q", "VK_S", "VK_F1", "VK_ESCAPE", "VK_SPACE"]

