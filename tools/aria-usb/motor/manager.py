# ModelManager: one-at-a-time + lazy load
class ModelManager:
    def __init__(self, cfg: ModelConfig):
        self.cfg = cfg
        self.active: Optional[str] = None

    def load_unified(self) -> str:
        self.active = self.cfg.unified_id
        return self.active

    def unload(self) -> None:
        self.active = None
