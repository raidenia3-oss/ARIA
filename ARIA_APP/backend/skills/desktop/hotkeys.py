from __future__ import annotations

import threading
from typing import Any, Callable, Dict, Optional

try:
    import keyboard
    _KEYBOARD = True
except Exception:
    _KEYBOARD = False


class HotkeyManager:
    def __init__(self) -> None:
        self._hotkeys: Dict[str, str] = {}  # combination -> callback_name
        self._listening = False
        self._thread: Optional[threading.Thread] = None
        self.callbacks: Dict[str, Callable[[], None]] = {}

    def register_callback(self, name: str, fn: Callable[[], None]) -> None:
        self.callbacks[name] = fn

    def register(self, combination: str, callback_name: str) -> Dict[str, Any]:
        if not _KEYBOARD:
            return {"ok": False, "error": "keyboard module no disponible"}
        if combination in self._hotkeys:
            return {"ok": False, "error": f"hotkey ya registrado: {combination}"}

        def _handler():
            cb = self.callbacks.get(callback_name)
            if cb:
                cb()

        try:
            keyboard.add_hotkey(combination, _handler, suppress=False)
            self._hotkeys[combination] = callback_name
            return {"ok": True, "combination": combination, "callback": callback_name}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def unregister(self, combination: str) -> Dict[str, Any]:
        if not _KEYBOARD:
            return {"ok": False, "error": "keyboard module no disponible"}
        if combination not in self._hotkeys:
            return {"ok": False, "error": f"hotkey no registrado: {combination}"}
        try:
            keyboard.remove_hotkey(combination)
            del self._hotkeys[combination]
            return {"ok": True, "combination": combination}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def list(self) -> Dict[str, Any]:
        return {
            "ok": True,
            "keyboard_available": _KEYBOARD,
            "hotkeys": {k: v for k, v in self._hotkeys.items()},
            "count": len(self._hotkeys),
        }

    def start_listener(self) -> Dict[str, Any]:
        if not _KEYBOARD:
            return {"ok": False, "error": "keyboard module no disponible"}
        if self._listening:
            return {"ok": True, "status": "already_running"}
        self._listening = True
        # keyboard.add_hotkey ya escucha en background; nada más que hacer
        return {"ok": True, "status": "listening"}

    def stop(self) -> Dict[str, Any]:
        if not _KEYBOARD:
            return {"ok": False, "error": "keyboard module no disponible"}
        for combination in list(self._hotkeys.keys()):
            try:
                keyboard.remove_hotkey(combination)
            except Exception:
                pass
        self._hotkeys.clear()
        self._listening = False
        return {"ok": True, "status": "stopped"}

_hotkeys: HotkeyManager | None = None


def _get_hotkeys() -> HotkeyManager:
    global _hotkeys
    if _hotkeys is None:
        _hotkeys = HotkeyManager()
    return _hotkeys


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    action = params.get("action", "")
    mgr = _get_hotkeys()
    if action == "register":
        return mgr.register(params.get("combination", ""), params.get("callback", ""))
    if action == "unregister":
        return mgr.unregister(params.get("combination", ""))
    if action == "list":
        return mgr.list()
    if action == "start":
        return mgr.start_listener()
    if action == "stop":
        return mgr.stop()
    if action == "register_callback":
        name = params.get("name", "")
        if not name:
            return {"ok": False, "error": "nombre requerido"}
        mgr.register_callback(name, params.get("fn_ref", name))
        return {"ok": True, "registered": name}
    return {"error": f"accion desconocida: {action}"}
