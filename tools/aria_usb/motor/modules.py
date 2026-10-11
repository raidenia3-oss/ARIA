# Módulos especializados (lazy)
from __future__ import annotations
from typing import Optional
from .core import ModelConfig

class ModuleRegistry:
    def __init__(self, cfg: ModelConfig):
        self.cfg = cfg

    def get(self, name: str) -> Optional[str]:
        return self.cfg.modules.get(name) if self.cfg.modules else None
