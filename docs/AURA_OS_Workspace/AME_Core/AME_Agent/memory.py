import json
from pathlib import Path
from datetime import datetime

class AgentMemory:
    """
    Guarda historial de tareas para que el agente
    aprenda de sesiones anteriores
    """

    MEMORY_PATH = Path("/sdcard/ame_memory.json")
    MAX_ENTRIES = 100

    def __init__(self):
        self.history = self._load()

    def _load(self) -> list:
        if self.MEMORY_PATH.exists():
            try:
                return json.loads(self.MEMORY_PATH.read_text())
            except Exception:
                return []
        return []

    def save(self, task: str, steps: list):
        entry = {
            "task":  task,
            "steps": len(steps),
            "tools": [s["tool"] for s in steps],
            "ts":    datetime.now().isoformat()
        }
        self.history.append(entry)
        if len(self.history) > self.MAX_ENTRIES:
            self.history = self.history[-self.MAX_ENTRIES:]
        self.MEMORY_PATH.write_text(json.dumps(self.history, indent=2))

    def get_relevant(self, task: str, n: int = 3) -> list:
        keywords = task.lower().split()
        scored = []
        for entry in self.history:
            score = sum(1 for kw in keywords
                        if kw in entry["task"].lower())
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:n]]

    def print_history(self, n: int = 10):
        print(f"\n{'='*40}")
        print(f"Ultimas {n} tareas:")
        for entry in self.history[-n:]:
            ts = entry["ts"][:16].replace("T", " ")
            print(f"  [{ts}] {entry['task'][:50]}")
            print(f"         {entry['steps']} pasos: "
                  f"{', '.join(entry['tools'][:3])}")
        print(f"{'='*40}\n")