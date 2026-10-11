# Router híbrido (extiende lógica ai_router)
from __future__ import annotations
from typing import Any, Dict, Optional
from .manager import ModelManager
from .core import ModelConfig

class HybridRouter:
    def __init__(self, mgr: ModelManager, cfg: ModelConfig):
        self.mgr = mgr
        self.cfg = cfg

    def route(self, task: Dict[str, Any]) -> Dict[str, Any]:
        self.mgr.load_unified()
        return {"model": self.mgr.active, "mode": "unified", "modules": self.cfg.modules}
