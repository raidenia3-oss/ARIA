# Módulos especializados (lazy)
class ModuleRegistry:
    def __init__(self, cfg: ModelConfig):
        self.cfg = cfg

    def get(self, name: str) -> Optional[str]:
        return self.cfg.modules.get(name) if self.cfg.modules else None
