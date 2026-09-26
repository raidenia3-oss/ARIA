"""Reasoning Resolver - Resuelve problemas complejos."""
import asyncio, json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

class ReasoningResolver:
    def __init__(self, atria_client):
        self.client = atria_client
        self.log = []
        self.ok = 0
        self.bad = 0

    async def can_solve(self, problem):
        prompt = "Problema: " + str(problem) + ". Complejo? yes/no."
        r = await self.client.request(prompt, max_tokens=50, category="reasoning")
        if r.get("success"): return "yes" in r["response"].lower()
        return False

    async def resolve(self, problem, context=None):
        prompt = "Resuelve paso a paso: " + str(problem)
        r = await self.client.request(prompt, max_tokens=2000, category="reasoning")
        if r.get("success"):
            self.ok += 1
            res = {"problem": problem, "solution": r["response"], "status": "resolved", "timestamp": datetime.now().isoformat()}
            self.log.append(res)
            return res
        self.bad += 1
        return {"status": "error"}

    def get_stats(self):
        t = self.ok + self.bad
        return {"total": t, "ok": self.ok, "bad": self.bad, "rate": self.ok/max(t,1)*100}

