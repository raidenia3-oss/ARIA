"""Knowledge Integrator - Conocimiento nuevo."""
import asyncio, json
from pathlib import Path
from typing import Dict, Any, List, Optional

class KnowledgeIntegrator:
    def __init__(self, atria_client):
        self.client = atria_client
        self.kd = Path("ARIA_APP/data/knowledge")
        self.kd.mkdir(parents=True, exist_ok=True)
        self.sources = []

    async def integrate_source(self, stype, sref):
        prompt = "Integra: " + stype + ": " + sref + ". JSON."
        r = await self.client.request(prompt, max_tokens=3000, category="knowledge")
        if r.get("success"):
            try:
                facts = json.loads(r["response"])
                self.sources.append({"type": stype, "facts": facts, "tokens": r.get("tokens_used", 0)})
                return {"status": "ok", "count": len(facts)}
            except: return {"status": "parse"}
        return {"status": "error"}

    async def update_knowledge_base(self, topics):
        prompt = "Actualiza: " + str(topics)
        r = await self.client.request(prompt, max_tokens=4000, category="knowledge")
        if r.get("success"):
            try: json.loads(r["response"]); return 1
            except: return 0
        return 0

    def get_stats(self):
        return {"sources": len(self.sources)}

