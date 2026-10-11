# Bridge Termux + AIRIS (HITL)
class BridgeHITL:
    def __init__(self):
        self.queue = []

    def request_approval(self, task_id: str, diff: str) -> str:
        self.queue.append({"task_id": task_id, "diff": diff})
        return "pending_approval"
