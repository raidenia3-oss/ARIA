# Bridge HITL
from __future__ import annotations
from typing import List, Dict, Any

class BridgeHITL:
    def __init__(self):
        self.queue: List[Dict[str, Any]] = []

    def request_approval(self, task_id: str, diff: str) -> str:
        self.queue.append({"task_id": task_id, "diff": diff})
        return "pending_approval"

    def pull(self) -> List[Dict[str, Any]]:
        return list(self.queue)
