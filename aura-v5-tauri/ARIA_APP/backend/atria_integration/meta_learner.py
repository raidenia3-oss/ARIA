"""Meta-Learner - Aprende a aprender."""
import asyncio, json
from pathlib import Path
from typing import Dict, Any, List, Optional

class MetaLearner:
    def __init__(self, atria_client):
        self.client = atria_client
        self.sf = Path("ARIA_APP/data/knowledge/strategies.json")
        self.strategies = []
        self.iterations = 0
        self.history = []
        self._load()

    def _load(self):
        if self.sf.exists():
            try:
                with open(self.sf, encoding="utf-8") as f:
                    self.strategies = json.load(f)
            except: pass

    def _save(self):
        self.sf.parent.mkdir(parents=True, exist_ok=True)
        with open(self.sf, "w", encoding="utf-8") as f:
            json.dump(self.strategies, f, ensure_ascii=False, indent=2)

    async def analyze_performance(self):
        prompt = "Analiza rendimiento. JSON."
        r = await self.client.request(prompt, max_tokens=3000, category="meta_learning")
        if r.get("success"):
            try:
                a = json.loads(r["response"])
                self.history.append({"iter": self.iterations, "a": a})
                return a
            except: return {}
        return {}

    async def optimize_strategy(self):
        if not self.history: await self.analyze_performance()
        prompt = "Propone 5 estrategias. JSON."
        r = await self.client.request(prompt, max_tokens=3000, category="meta_learning")
        if r.get("success"):
            try:
                s = json.loads(r["response"])
                self.strategies = s; self._save(); self.iterations += 1
                return {"status": "ok", "count": len(s)}
            except: return {"status": "parse"}
        return {"status": "error"}

    async def self_improve(self):
        return {"analysis": await self.analyze_performance(), "optimization": await self.optimize_strategy(), "iter": self.iterations}

    def get_stats(self):
        return {"iterations": self.iterations, "strategies": len(self.strategies)}

