import asyncio
import time
from typing import Any, Dict, List, Optional
from backend.plugins.plugin_template import PluginAgent


class PluginAgent(PluginAgent):
    def __init__(self):
        super().__init__()
        self.name = "translator-agent"
        self.version = "1.0.0"
        self.commands = {
            "translate": self.translate,
            "detect_language": self.detect_language,
            "batch_translate": self.batch_translate,
        }
        self._cache: Dict[str, Dict] = {}

    async def on_load(self):
        print("[TranslatorAgent] Plugin cargado — traducción multilingüe activa")

    async def translate(self, args: dict) -> dict:
        text = args.get("text", "")
        target = args.get("target_lang", "es")
        source = args.get("source_lang", "auto")
        start = time.time()
        try:
            from openai import OpenAI
            client = OpenAI()
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "system",
                    "content": f"Traduce al {target}. Preserva el contexto cultural.",
                }, {
                    "role": "user",
                    "content": f"Traduce: {text}",
                }],
                temperature=0.3,
            )
            result = response.choices[0].message.content
            return {
                "status": "ok",
                "original": text,
                "translated": result,
                "source_lang": source,
                "target_lang": target,
                "confidence": 0.95,
                "latency_ms": round((time.time() - start) * 1000, 2),
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "latency_ms": round((time.time() - start) * 1000, 2)}

    async def detect_language(self, args: dict) -> dict:
        text = args.get("text", "")
        try:
            from langdetect import detect, detect_langs
            lang = detect(text)
            langs = [str(l) for l in detect_langs(text)]
            return {"status": "ok", "language": lang, "all_languages": langs, "confidence": 0.99}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def batch_translate(self, args: dict) -> dict:
        texts = args.get("texts", [])
        target = args.get("target_lang", "es")
        results = []
        for t in texts:
            res = await self.translate({"text": t, "target_lang": target})
            results.append(res)
        return {"status": "ok", "translations": results, "count": len(results)}
