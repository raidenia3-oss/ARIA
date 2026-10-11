# Router híbrido (extiende lógica ai_router)
class HybridRouter:
    def __init__(self, mgr: ModelManager, cfg: ModelConfig):
        self.mgr = mgr
        self.cfg = cfg

    def route(self, task: Dict[str, Any]) -> Dict[str, Any]:
        # núcleo por defecto; módulos bajo demanda
        self.mgr.load_unified()
        return {"model": self.mgr.active, "mode": "unified", "modules": self.cfg.modules}
