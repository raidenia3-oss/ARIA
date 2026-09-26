"""
Smart AI Router for AURA.

Hybrid brain architecture:
- Local small model (0.5B/1.5B) handles simple, frequent, private tasks.
- External API (Gemini/Groq/OpenRouter) handles complex, broad-context tasks.
- Router classifies complexity, decides provider, and logs interactions
  for continual training of the small model.

Modes:
- auto: classify by heuristics + optional local confidence estimator.
- local_only: force local model.
- cloud_only: force external API.
- hybrid: local first, fallback to cloud on low confidence.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    from ame_backend.src.services.ai_engine import AIEngine
except Exception:  # pragma: no cover
    AIEngine = None  # type: ignore

COMPLEXITY_KEYWORDS = {
    "high": [
        "analiza", "analizar", "razona", "razonamiento", "explica en profundidad",
        "compara", "diferencia", "arquitectura", "diseña", "diseño",
        "planifica", "estrategia", "optimiza", "debug complejo", "refactor",
        "código complejo", "algoritmo", "implementa", "investiga", "busca en internet",
        "contexto amplio", "multimodal", "imagen", "archivo",
    ],
    "low": [
        "hora", "fecha", "abre", "ejecuta", "lista", "busca archivo",
        "hola", "ayuda", "qué puedes hacer", "estado", "memoria",
        "quién eres", "repite", "responde rápido",
    ],
}

MODEL_LOCAL = os.getenv("SMART_ROUTER_LOCAL_MODEL", "qwen2.5:0.5b")
MODEL_CLOUD_DEFAULT = os.getenv("SMART_ROUTER_CLOUD_MODEL", "gemini-2.0-flash-exp")


@dataclass
class InteractionLog:
    prompt: str
    context: Optional[str]
    provider: str
    model: str
    response: str
    latency_ms: float
    complexity: str
    confidence: Optional[float] = None
    used_for_training: bool = False


class SmartAIRouter:
    def __init__(self, mode: Optional[str] = None) -> None:
        self.mode = mode or os.getenv("SMART_ROUTER_MODE", "hybrid")
        self.engine = AIEngine() if AIEngine else None
        self.log_path = os.getenv("SMART_ROUTER_LOG", "training/data/interactions.jsonl")
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        self._interactions: List[InteractionLog] = []
        self._load_logs()

    def ask(
        self,
        prompt: str,
        context: Optional[str] = None,
        force_provider: Optional[str] = None,
        force_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        complexity = self._estimate_complexity(prompt)
        provider, model, reason = self._decide_provider(
            complexity=complexity,
            force_provider=force_provider,
            force_model=force_model,
        )

        start = time.time()
        response_text = ""
        latency_ms = 0.0
        error = None

        try:
            if provider == "local":
                response_text = self._call_local(prompt, context, model)
            else:
                result = self._call_cloud(prompt, context, provider, model)
                response_text = result.get("text", "")
        except Exception as exc:
            error = str(exc)
            response_text = f"Router error: {error}"

        latency_ms = (time.time() - start) * 1000

        interaction = InteractionLog(
            prompt=prompt,
            context=context,
            provider=provider if not error else "error",
            model=model or "",
            response=response_text,
            latency_ms=latency_ms,
            complexity=complexity,
        )
        self._append_log(interaction)

        return {
            "text": response_text,
            "provider": provider,
            "model": model,
            "complexity": complexity,
            "latency_ms": round(latency_ms, 2),
            "reason": reason,
            "error": error,
        }

    def export_training_data(self, min_complexity: str = "medium") -> str:
        out_path = "training/data/router_training_pairs.jsonl"
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        levels = {"low": 0, "medium": 1, "high": 2}
        min_level = levels.get(min_complexity, 1)
        count = 0
        with open(out_path, "w", encoding="utf-8") as f:
            for inter in self._interactions:
                if inter.provider == "error":
                    continue
                if levels.get(inter.complexity, 0) < min_level:
                    continue
                pair = {
                    "text": inter.prompt,
                    "output": inter.response,
                    "meta": {
                        "provider": inter.provider,
                        "model": inter.model,
                        "complexity": inter.complexity,
                        "latency_ms": inter.latency_ms,
                    },
                }
                f.write(json.dumps(pair, ensure_ascii=False) + "\n")
                count += 1
        print(f"[router] Exported {count} training pairs -> {out_path}")
        return out_path

    def _estimate_complexity(self, prompt: str) -> str:
        lower = prompt.lower()
        high_hits = sum(1 for kw in COMPLEXITY_KEYWORDS["high"] if kw in lower)
        low_hits = sum(1 for kw in COMPLEXITY_KEYWORDS["low"] if kw in lower)
        if high_hits > low_hits and high_hits >= 2:
            return "high"
        if low_hits > high_hits:
            return "low"
        return "medium"

    def _decide_provider(
        self,
        complexity: str,
        force_provider: Optional[str],
        force_model: Optional[str],
    ) -> Tuple[str, Optional[str], str]:
        if force_provider:
            return force_provider, force_model, "forced"
        if self.mode == "local_only":
            return "local", MODEL_LOCAL, "mode_local_only"
        if self.mode == "cloud_only":
            return "cloud", force_model or MODEL_CLOUD_DEFAULT, "mode_cloud_only"
        if complexity == "high":
            return "cloud", MODEL_CLOUD_DEFAULT, "complexity_high"
        if complexity == "low":
            return "local", MODEL_LOCAL, "complexity_low"
        return "local", MODEL_LOCAL, "default_hybrid_local"

    def _call_local(self, prompt: str, context: Optional[str], model: str) -> str:
        try:
            import requests
            base = os.getenv("LOCAL_LFM_BASE_URL", "http://localhost:11434")
            url = f"{base.rstrip('/')}/api/generate"
            payload = {"model": model, "prompt": prompt, "stream": False}
            if context:
                payload["prompt"] = f"Context:\n{context}\n\nUser:\n{prompt}"
            r = requests.post(url, json=payload, timeout=int(os.getenv("LOCAL_LFM_TIMEOUT", "120")))
            r.raise_for_status()
            data = r.json()
            return data.get("response", "")
        except Exception as exc:
            raise RuntimeError(f"Local model error: {exc}") from exc

    def _call_cloud(self, prompt: str, context: Optional[str], provider: str, model: Optional[str]) -> Dict[str, Any]:
        if not self.engine:
            raise RuntimeError("AIEngine not available")
        return self.engine.chat(prompt=prompt, context=context, provider_override=provider if provider != "cloud" else None, model_override=model)

    def _append_log(self, interaction: InteractionLog) -> None:
        self._interactions.append(interaction)
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "prompt": interaction.prompt,
                    "context": interaction.context,
                    "provider": interaction.provider,
                    "model": interaction.model,
                    "response": interaction.response,
                    "latency_ms": interaction.latency_ms,
                    "complexity": interaction.complexity,
                    "ts": time.time(),
                }, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _load_logs(self) -> None:
        if not os.path.exists(self.log_path):
            return
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        self._interactions.append(InteractionLog(**obj))
                    except Exception:
                        continue
        except Exception:
            pass


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Smart AI Router CLI")
    parser.add_argument("--mode", default=os.getenv("SMART_ROUTER_MODE", "hybrid"))
    parser.add_argument("--export-training", action="store_true")
    parser.add_argument("--min-complexity", default="medium")
    args = parser.parse_args()

    router = SmartAIRouter(mode=args.mode)

    if args.export_training:
        router.export_training_data(min_complexity=args.min_complexity)
        return 0

    print(f"[router] Mode: {router.mode}")
    print("Type 'quit' to exit.\n")
    while True:
        prompt = input("You: ").strip()
        if prompt.lower() in ("quit", "exit", "salir"):
            break
        if not prompt:
            continue
        result = router.ask(prompt)
        print(f"[{result['provider']} | {result['model']} | {result['complexity']}] AURA: {result['text']}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
