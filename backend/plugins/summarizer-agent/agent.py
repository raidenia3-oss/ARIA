import asyncio
import time
from typing import Any, Dict, List, Optional
from backend.plugins.plugin_template import PluginAgent


class PluginAgent(PluginAgent):
    def __init__(self):
        super().__init__()
        self.name = "summarizer-agent"
        self.version = "1.0.0"
        self.commands = {
            "summarize": self.summarize,
            "summarize_url": self.summarize_url,
            "extract_key_points": self.extract_key_points,
        }

    async def on_load(self):
        print("[SummarizerAgent] Plugin cargado — resumen de textos activo")

    async def summarize(self, args: dict) -> dict:
        text = args.get("text", "")
        mode = args.get("mode", "abstract")
        detail = args.get("detail_level", "medium")
        start = time.time()
        try:
            from openai import OpenAI
            client = OpenAI()
            system = {
                "abstract": "Resume el texto en un párrafo coherente.",
                "extractive": "Extrae las frases más importantes del texto tal cual.",
                "bullets": "Presenta los puntos clave como lista de viñetas.",
            }.get(mode, "Resume el texto.")
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": system}, {"role": "user", "content": text}],
                temperature=0.4,
            )
            return {
                "status": "ok", "mode": mode, "detail": detail,
                "summary": response.choices[0].message.content,
                "original_length": len(text), "summary_length": len(response.choices[0].message.content),
                "latency_ms": round((time.time() - start) * 1000, 2),
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "latency_ms": round((time.time() - start) * 1000, 2)}

    async def summarize_url(self, args: dict) -> dict:
        url = args.get("url", "")
        mode = args.get("mode", "abstract")
        try:
            from urllib.request import urlopen
            with urlopen(url, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            import re
            text = re.sub(r'<[^>]+>', ' ', html)
            text = re.sub(r'\s+', ' ', text).strip()[:50000]
            return await self.summarize({"text": text, "mode": mode})
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def extract_key_points(self, args: dict) -> dict:
        text = args.get("text", "")
        count = args.get("count", 5)
        result = await self.summarize({"text": text, "mode": "bullets"})
        points = result.get("summary", "").split("\n")[:count]
        return {"status": "ok", "key_points": points, "count": len(points)}
