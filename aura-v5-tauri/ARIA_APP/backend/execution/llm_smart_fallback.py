"""Smart LLM Fallback Chain: Ollama → Cache → Atria → Generic"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

logger = logging.getLogger("aria")


class SmartLLMFallback:
    """Fallback chain: Ollama (fast) → Cache (instant) → Atria (reliable) → Generic"""

    DEFAULT_TIMEOUT = 5.0
    CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"

    def __init__(self, timeout: float = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self._cache = {}
        self._load_cache()

    def _load_cache(self):
        try:
            cache_file = self.CACHE_DIR / "enhanced_responses.jsonl"
            if cache_file.exists():
                for line in cache_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                    try:
                        entry = json.loads(line.strip())
                        if entry.get("prompt") and entry.get("response"):
                            self._cache[entry["prompt"].lower().strip()] = entry["response"]
                    except Exception:
                        continue
                logger.info(f"Cache loaded: {len(self._cache)} entries")
        except Exception as e:
            logger.warning(f"Cache load failed: {e}")

    def _save_cache(self, prompt: str, response: str):
        try:
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_file = self.CACHE_DIR / "enhanced_responses.jsonl"
            with open(cache_file, "a", encoding="utf-8") as f:
                f.write(json.dumps({"prompt": prompt, "response": response, "ts": time.time()}, ensure_ascii=False) + "\n")
            self._cache[prompt.lower().strip()] = response
        except Exception:
            pass

    async def generate_with_fallback(self, prompt: str, system_prompt: str = "") -> dict:
        """Generate with automatic fallback chain"""
        # 1. Cache first (instant)
        cached = self._lookup_cache(prompt)
        if cached:
            return {"response": cached, "source": "cache", "latency": 0.0}

        # 2. Try Ollama (fast, local)
        try:
            result = await self._try_ollama(prompt, system_prompt)
            if result:
                self._save_cache(prompt, result)
                return {"response": result, "source": "ollama", "latency": 0.0}
        except asyncio.TimeoutError:
            logger.warning("Ollama timeout, trying Atria...")
        except Exception as e:
            logger.warning(f"Ollama error: {e}")

        # 3. Try Atria (reliable cloud)
        try:
            result = await self._try_atria(prompt, system_prompt)
            if result:
                self._save_cache(prompt, result)
                return {"response": result, "source": "atria", "latency": 0.0}
        except Exception as e:
            logger.warning(f"Atria error: {e}")

        # 4. Generic fallback
        return {"response": "Estoy pensando en eso...", "source": "fallback", "latency": 0.0}

    def _lookup_cache(self, prompt: str) -> str | None:
        key = prompt.lower().strip()
        if key in self._cache:
            return self._cache[key]
        # Fuzzy: check if prompt contains cached key or vice versa
        for cached_key, cached_response in self._cache.items():
            if cached_key in key or key in cached_key:
                return cached_response
        return None

    async def _try_ollama(self, prompt: str, system_prompt: str) -> str | None:
        """Try Ollama with timeout"""
        try:
            import ollama
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    ollama.generate,
                    model="dolphin-2_6-phi-2",
                    prompt=full_prompt,
                    stream=False,
                ),
                timeout=self.timeout,
            )
            text = response.get("response", "").strip()
            return text if text else None
        except asyncio.TimeoutError:
            raise
        except Exception as e:
            logger.warning(f"Ollama generate error: {e}")
            return None

    async def _try_atria(self, prompt: str, system_prompt: str) -> str | None:
        """Try Atria API"""
        try:
            import httpx
            import os
            api_key = os.environ.get("ATRIA_API_KEY", "")
            if not api_key:
                return None
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    "https://api.atria.ai/v1/chat",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"prompt": prompt, "system": system_prompt, "max_tokens": 500},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("response", "").strip() or None
                return None
        except Exception as e:
            logger.warning(f"Atria error: {e}")
            return None