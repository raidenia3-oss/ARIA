from __future__ import annotations

import time
from typing import Any, Dict, Optional
from backend.bot_manager import bot_manager
from backend.explorer.explorer_bot import ExplorerBot


class ExplorerManager:
    def __init__(self) -> None:
        self.instances: Dict[str, ExplorerBot] = {}

    def create_explorer(self, name: str = "explorer") -> Dict[str, Any]:
        res = bot_manager.create_bot(name, bot_type="explorer", config={"mode": "outbound-only"})
        bid = res.get("bot_id")
        if bid:
            self.instances[bid] = ExplorerBot(name=name)
        return res

    def start(self, bot_id: str) -> Dict[str, Any]:
        inst = self.instances.get(bot_id)
        if not inst:
            return {"status": "not_found"}
        inst.start()
        bot_manager.start_bot(bot_id)
        return {"status": "started", "bot_id": bot_id}

    def stop(self, bot_id: str) -> Dict[str, Any]:
        inst = self.instances.get(bot_id)
        if not inst:
            return {"status": "not_found"}
        inst.stop()
        bot_manager.stop_bot(bot_id)
        return {"status": "stopped", "bot_id": bot_id}

    def fetch(self, bot_id: str, url: str) -> Dict[str, Any]:
        inst = self.instances.get(bot_id)
        if not inst:
            return {"status": "not_found"}
        return inst.fetch(url)

    def search(self, bot_id: str, query: str) -> Dict[str, Any]:
        inst = self.instances.get(bot_id)
        if not inst:
            return {"status": "not_found"}
        return inst.search(query)

    def explore(self, bot_id: str, topic: str) -> Dict[str, Any]:
        inst = self.instances.get(bot_id)
        if not inst:
            return {"status": "not_found"}
        return inst.explore(topic)


explorer_manager = ExplorerManager()
