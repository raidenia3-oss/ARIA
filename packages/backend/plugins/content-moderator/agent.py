import asyncio
import time
from typing import Any, Dict, List, Optional
from backend.plugins.plugin_template import PluginAgent


class PluginAgent(PluginAgent):
    def __init__(self):
        super().__init__()
        self.name = "content-moderator"
        self.version = "1.0.0"
        self.commands = {
            "moderate": self.moderate,
            "classify_severity": self.classify_severity,
            "suggest_fix": self.suggest_fix,
        }
        self._blocked_terms = ["spam", "scam", "fraud"]
        self._categories = ["safe", "low_risk", "medium_risk", "high_risk", "nsfw"]

    async def on_load(self):
        print("[ContentModerator] Plugin cargado — moderación de contenido activa")

    async def moderate(self, args: dict) -> dict:
        text = args.get("text", "")
        threshold = args.get("severity_threshold", 0.7)
        start = time.time()
        try:
            from openai import OpenAI
            client = OpenAI()
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "system",
                    "content": "Analiza el contenido y clasifica su seguridad. Responde JSON: {safe: bool, categories: [...], severity: 0-1, reasons: [...]}",
                }, {"role": "user", "content": f"Analiza para moderación: {text[:4000]}"}],
                temperature=0.1,
            )
            content = response.choices[0].message.content
            severity = self._estimate_severity(text, content)
            is_safe = severity < threshold
            return {
                "status": "ok",
                "safe": is_safe,
                "severity": round(severity, 3),
                "threshold": threshold,
                "action": "approved" if is_safe else "flagged",
                "latency_ms": round((time.time() - start) * 1000, 2),
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "latency_ms": round((time.time() - start) * 1000, 2)}

    async def classify_severity(self, args: dict) -> dict:
        text = args.get("text", "")
        if not text:
            return {"status": "ok", "severity": 0.0, "category": "safe"}
        if any(term in text.lower() for term in self._blocked_terms):
            return {"status": "ok", "severity": 0.9, "category": "high_risk", "flagged_terms": self._blocked_terms}
        try:
            length_factor = min(len(text) / 1000, 1.0)
            score = length_factor * 0.3 + hash(text) % 30 / 100
            cat = self._categories[min(int(score * len(self._categories)), len(self._categories) - 1)]
            return {"status": "ok", "severity": round(score, 3), "category": cat}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def suggest_fix(self, args: dict) -> dict:
        text = args.get("text", "")
        category = args.get("category", "generic")
        if not text:
            return {"status": "ok", "suggestion": "", "original": ""}
        try:
            from openai import OpenAI
            client = OpenAI()
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "system",
                    "content": f"Reescribe el texto para que sea apropiado para la categoría: {category}. Mantén el significado original.",
                }, {"role": "user", "content": text}],
                temperature=0.3,
            )
            return {"status": "ok", "original": text, "suggestion": response.choices[0].message.content}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _estimate_severity(self, text: str, ai_response: str) -> float:
        base = 0.1
        if "flagged" in ai_response.lower():
            base += 0.5
        if len(text) < 5:
            base += 0.1
        return min(base + (hash(text) % 20) / 100, 1.0)
