from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from backend.grook_bot import GrookBot
from backend.explorer.http_client import get_client
from backend.brain_orchestrator import brain


class ExplorerBot(GrookBot):
    def __init__(self, name: str = "explorer", brain_ref=None) -> None:
        super().__init__(name=name, brain=brain_ref or brain)
        self.client = get_client()
        self.visited = set()
        self.history = []

    def fetch(self, url: str) -> Dict[str, Any]:
        res = self.client.get(url)
        self.history.append({"type": "fetch", "url": url, "ts": time.time(), "ok": res.get("ok")})
        return res

    def search(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        q = query.replace(" ", "+")
        url = f"https://duckduckgo.com/html/?q={q}"
        res = self.fetch(url)
        return {"query": query, "source": url, "raw": res}

    def explore(self, topic: str) -> Dict[str, Any]:
        s = self.search(topic)
        if self.brain and hasattr(self.brain, "think"):
            try:
                summary = self.brain.think(f"Resumir búsqueda outbound-only sobre: {topic}\n\n{s.get('raw',{}).get('text','')[:2000]}")
                return {"topic": topic, "summary": summary.get("message"), "source": s.get("source")}
            except Exception as e:
                return {"topic": topic, "error": str(e)}
        return {"topic": topic, "raw_search": s}
