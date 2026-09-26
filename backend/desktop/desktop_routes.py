"""API Router para el Desktop App Shell (Bloque 59).

Endpoints REST para controlar la aplicacion de escritorio nativa:
- Estado del proceso backend y del launcher
- Arranque/parada/reinicio del backend
- Informacion de la ventana y configuracion de la UI

Mantiene compatibilidad con los contratos REST existentes.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.desktop.launcher import get_launcher

logger = logging.getLogger("AURA.Desktop.Routes")

desktop_router = APIRouter(prefix="/api/desktop", tags=["desktop"])


class DesktopStatus(BaseModel):
    backend_running: bool
    backend_info: Dict[str, Any] = {}
    base_url: str = ""
    host: str = "127.0.0.1"
    port: int = 8000


@desktop_router.get("/status", response_model=DesktopStatus)
async def get_desktop_status() -> DesktopStatus:
    """Obtiene el estado del launcher de escritorio y backend."""
    launcher = get_launcher()
    info = launcher.get_info()
    return DesktopStatus(
        backend_running=launcher.is_running(),
        backend_info=info,
        base_url=launcher.base_url,
        host=launcher.host,
        port=launcher.port,
    )


@desktop_router.post("/backend/start")
async def start_backend(timeout: float = 30.0) -> Dict[str, Any]:
    """Inicia el proceso backend Python."""
    launcher = get_launcher()
    success = launcher.start(timeout)
    return {"started": success, "running": launcher.is_running()}


@desktop_router.post("/backend/stop")
async def stop_backend() -> Dict[str, Any]:
    """Detiene el proceso backend Python."""
    launcher = get_launcher()
    success = launcher.stop()
    return {"stopped": success, "running": launcher.is_running()}


@desktop_router.post("/backend/restart")
async def restart_backend(timeout: float = 30.0) -> Dict[str, Any]:
    """Reinicia el proceso backend Python."""
    launcher = get_launcher()
    success = launcher.restart(timeout)
    return {"restarted": success, "running": launcher.is_running()}


@desktop_router.get("/backend/info")
async def get_backend_info() -> Dict[str, Any]:
    """Obtiene informacion detallada del proceso backend."""
    launcher = get_launcher()
    return launcher.get_info()


@desktop_router.get("/config/ui")
async def get_ui_config() -> Dict[str, Any]:
    """Obtiene la configuracion de la interfaz de escritorio."""
    import os
    return {
        "base_url": os.getenv("AURA_API_URL", "http://127.0.0.1:8000"),
        "window": {
            "frameless": True,
            "translucent": True,
            "width": 280,
            "height": 440,
        },
        "hotkeys": {
            "toggle_window": "Alt+Space",
            "screenshot": "Alt+S",
            "toggle_mic": "Alt+M",
        },
        "tray": {
            "tooltip": "AURA Desktop",
            "show": True,
        },
    }


__all__ = ["desktop_router", "DesktopStatus"]
