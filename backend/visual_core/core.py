# núcleo visual completo - integra cámara + identidad + expresión
from __future__ import annotations
from typing import Any, Dict

from .camera import camera
from .identity import identity
from .expressor import expressor
from .nucleo import nucleo
from .visualizer import visualizer


class CoreVisual:
    def __init__(self) -> None:
        pass

    def activate_full(self, passphrase: str = "aria") -> Dict[str, Any]:
        res = {}
        res["camera"] = camera.start()
        res["identity"] = identity.register(passphrase) if not identity.verified else {"status": "already_verified", "verified": True}
        res["nucleo"] = nucleo.activate()
        res["expressor"] = expressor.awake()
        res["visualizer"] = visualizer.start()
        return res

    def status(self) -> Dict[str, Any]:
        return {
            "camera": camera.status(),
            "identity": identity.status(),
            "nucleo": nucleo.status(),
            "expressor": expressor.status(),
        }


core_visual = CoreVisual()
