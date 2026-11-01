# visualizer skeleton - minimal overlay concept
from __future__ import annotations
from typing import Any, Dict


class Visualizer:
    def __init__(self) -> None:
        self.rendering = False
        self.opacity = 0.2  # small, pass unnoticed

    def start(self) -> Dict[str, Any]:
        self.rendering = True
        return {"status": "rendering", "opacity": self.opacity}

    def stop(self) -> Dict[str, Any]:
        self.rendering = False
        return {"status": "stopped"}

    def set_opacity(self, opacity: float) -> Dict[str, Any]:
        if 0.0 <= opacity <= 1.0:
            self.opacity = opacity
            return {"status": "ok", "opacity": opacity}
        return {"status": "invalid"}


visualizer = Visualizer()
