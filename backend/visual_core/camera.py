# camera module - minimal skeleton, fail-closed
from __future__ import annotations
from typing import Any, Dict


class Camera:
    def __init__(self) -> None:
        self.active = False

    def start(self) -> Dict[str, Any]:
        self.active = True
        return {"status": "active"}

    def stop(self) -> Dict[str, Any]:
        self.active = False
        return {"status": "inactive"}

    def status(self) -> Dict[str, Any]:
        return {"active": self.active}


camera = Camera()
