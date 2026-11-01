# expresión visual del núcleo - minimal
from __future__ import annotations
from typing import Any, Dict


class NucleoExpressor:
    def __init__(self) -> None:
        self.state = "idle"  # idle, pulse, awake, focused
        self.intensity = 0.3

    def pulse(self) -> Dict[str, Any]:
        self.state = "pulse"
        return {"state": self.state, "intensity": self.intensity}

    def awake(self) -> Dict[str, Any]:
        self.state = "awake"
        self.intensity = 0.6
        return {"state": self.state, "intensity": self.intensity}

    def focus(self) -> Dict[str, Any]:
        self.state = "focused"
        self.intensity = 0.9
        return {"state": self.state, "intensity": self.intensity}

    def idle(self) -> Dict[str, Any]:
        self.state = "idle"
        self.intensity = 0.3
        return {"state": self.state, "intensity": self.intensity}

    def status(self) -> Dict[str, Any]:
        return {"state": self.state, "intensity": self.intensity}


expressor = NucleoExpressor()
