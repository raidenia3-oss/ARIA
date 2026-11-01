from __future__ import annotations

import threading
from typing import Any, Callable, Dict, Optional

try:
    import pystray
    from PIL import Image, ImageDraw
    _PYSTRAY = True
except Exception:
    _PYSTRAY = False


def _make_image() -> Any:
    if not _PYSTRAY:
        return None
    img = Image.new("RGB", (64, 64), color=(10, 10, 15))
    d = ImageDraw.Draw(img)
    d.ellipse((8, 8, 56, 56), fill=(0, 180, 255))
    d.text((20, 22), "A", fill=(255, 255, 255))
    return img


class TrayManager:
    def __init__(self) -> None:
        self.icon: Optional[Any] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self.callbacks: Dict[str, Callable[[], None]] = {}

    def register_callback(self, name: str, fn: Callable[[], None]) -> None:
        self.callbacks[name] = fn

    def start(self) -> Dict[str, Any]:
        if not _PYSTRAY:
            return {"ok": False, "error": "pystray o Pillow no disponibles"}
        if self._running:
            return {"ok": True, "status": "already_running"}

        def _on_show(icon, item):
            cb = self.callbacks.get("show")
            if cb:
                cb()

        def _on_hide(icon, item):
            cb = self.callbacks.get("hide")
            if cb:
                cb()

        def _on_exit(icon, item):
            cb = self.callbacks.get("exit")
            if cb:
                cb()
            self.stop()

        menu = pystray.Menu(
            pystray.MenuItem("Mostrar ARIA", _on_show),
            pystray.MenuItem("Ocultar ARIA", _on_hide),
            pystray.MenuSeparator(),
            pystray.MenuItem("Salir", _on_exit),
        )
        self.icon = pystray.Icon("ARIA", _make_image(), "ARIA OS", menu)
        self._running = True
        self._thread = threading.Thread(target=self.icon.run, daemon=True, name="ARIATray")
        self._thread.start()
        return {"ok": True, "status": "started"}

    def stop(self) -> Dict[str, Any]:
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
        self.icon = None
        self._running = False
        return {"ok": True, "status": "stopped"}

    def status(self) -> Dict[str, Any]:
        return {"ok": True, "pystray": _PYSTRAY, "running": self._running}

    def notify(self, title: str, message: str) -> Dict[str, Any]:
        if not self.icon or not _PYSTRAY:
            return {"ok": False, "error": "tray no iniciado"}
        try:
            self.icon.notify(message, title)
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

_tray: TrayManager | None = None


def _get_tray() -> TrayManager:
    global _tray
    if _tray is None:
        _tray = TrayManager()
    return _tray


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    action = params.get("action", "")
    mgr = _get_tray()
    if action == "start":
        return mgr.start()
    if action == "stop":
        return mgr.stop()
    if action == "status":
        return mgr.status()
    if action == "notify":
        return mgr.notify(params.get("title", "ARIA"), params.get("message", ""))
    if action == "register_callback":
        name = params.get("name", "")
        if not name:
            return {"ok": False, "error": "nombre requerido"}
        mgr.register_callback(name, params.get("fn_ref", name))
        return {"ok": True, "registered": name}
    return {"error": f"accion desconocida: {action}"}
