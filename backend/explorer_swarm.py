from __future__ import annotations

try:
    from backend.explorer.explorer_api import explorer_manager
    from backend.explorer.http_client import get_client
except Exception:
    explorer_manager = None
    get_client = None


class ExplorerSwarm:
    def __init__(self) -> None:
        self.explorer_manager = explorer_manager

    def spawn(self, count: int = 1, name_prefix: str = "aria-explorer") -> dict:
        results = []
        if not self.explorer_manager:
            return {"status": "unavailable"}
        for i in range(max(1, int(count))):
            try:
                res = self.explorer_manager.create_explorer(name=f"{name_prefix}-{i+1}")
                results.append(res)
            except Exception as e:
                results.append({"error": str(e)})
        return {"status": "ok", "spawned": len(results), "results": results}

    def status(self) -> dict:
        if not self.explorer_manager:
            return {"status": "unavailable"}
        bots = []
        try:
            for bid, inst in self.explorer_manager.instances.items():
                bots.append({"bot_id": bid, "name": getattr(inst, "name", ""), "running": getattr(inst, "running", None)})
        except Exception as e:
            return {"status": "error", "error": str(e)}
        return {"status": "ok", "count": len(bots), "bots": bots}


swarm = ExplorerSwarm()
