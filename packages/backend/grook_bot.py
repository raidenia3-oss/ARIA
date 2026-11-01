"""
Grook Bot - Bot propio ligero para ARIA.

Base mínima: puede gestionar tareas, responder vía brain unificado, ejecutarse autónomamente.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional


class GrookBot:
    def __init__(self, name: str = "grook", brain=None) -> None:
        self.name = name
        self.brain = brain
        self.running = False
        self.last_tick = time.time()

    def start(self) -> Dict[str, Any]:
        self.running = True
        self.last_tick = time.time()
        return {"status": "running", "name": self.name}

    def stop(self) -> Dict[str, Any]:
        self.running = False
        return {"status": "stopped", "name": self.name}

    def tick(self) -> Dict[str, Any]:
        if not self.running:
            return {"status": "idle"}
        self.last_tick = time.time()
        if self.brain and hasattr(self.brain, "think"):
            try:
                resp = self.brain.think(f"[GROOK:{self.name}] ping")
                return {"status": "ok", "response": resp.get("message")}
            except Exception as e:
                return {"status": "error", "error": str(e)}
        return {"status": "ok", "response": "no_brain"}

    def chat(self, msg: str) -> Dict[str, Any]:
        if self.brain and hasattr(self.brain, "think"):
            return self.brain.think(msg)
        return {"message": f"[GROOK:{self.name}] {msg}"}
