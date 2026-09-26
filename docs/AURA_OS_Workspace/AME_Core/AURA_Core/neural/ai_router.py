"""
AURA Neural AI Router v5 — Pool Multi-Provider Gratuito con Fallback Chain
Integra: Gemini 2.5 Flash, Nvidia NIM (Llama 3.3 70B), Groq, OpenRouter
=======================================================================
Cadena de Resiliencia: 429/503 → captura → log → next provider
"""

import os, json, logging, asyncio, time
from typing import Optional, Dict, List, AsyncGenerator
from pathlib import Path
from dotenv import load_dotenv
import httpx

load_dotenv(Path(__file__).parent.parent / ".env")
logger = logging.getLogger(__name__)

# ── Proveedores gratuitos con prioridad ──────────────────────────
PROVIDER_CHAIN = [
    {
        "name": "gemini",
        "api_key_env": "GEMINI_API_KEY",
        "endpoint": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent",
        "timeout": 30,
    },
    {
        "name": "nvidia_nim",
        "api_key_env": "NVIDIA_NIM_API_KEY",
        "endpoint": "https://api.nvcf.nvidia.com/v2/nvcf/pexec/functions/meta/llama-3.3-70b-instruct",
        "timeout": 45,
    },
    {
        "name": "groq",
        "api_key_env": "GROQ_API_KEY",
        "endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "model": "mixtral-8x7b-32768",
        "timeout": 30,
    },
    {
        "name": "openrouter",
        "api_key_env": "OPENROUTER_API_KEY",
        "endpoint": "https://openrouter.ai/api/v1/chat/completions",
        "model": "google/gemma-2-9b-it:free",
        "headers": {
            "HTTP-Referer": "https://github.com/raidenia3-oss/AURA-server.01",
            "X-Title": "AURA",
        },
        "timeout": 30,
    },
]

# ── Global Memory Injector ──────────────────────────────────────
BRAIN_MEMORY_PATH = Path(__file__).parent.parent / "config" / "brain_memory.txt"


def _load_brain_memory() -> str:
    try:
        if BRAIN_MEMORY_PATH.exists():
            return BRAIN_MEMORY_PATH.read_text(encoding="utf-8")
    except Exception:
        pass
    return ""


# ── Fallback Chain ──────────────────────────────────────────────
QUOTA_CODES = {429, 502, 503, 504}


class NeuralRouter:
    """Enrutador asíncrono multi-proveedor con fallback automático."""

    def __init__(self):
        self._brain_suffix = _load_brain_memory()

    def _inject_memory(self, prompt: str) -> str:
        """Anexa el contexto global al prompt."""
        if self._brain_suffix:
            return f"{prompt}\n\n[CONTEXTO GLOBAL]\n{self._brain_suffix}"
        return prompt

    async def _call_provider(
        self, client: httpx.AsyncClient, cfg: dict, prompt: str
    ) -> Optional[str]:
        """Ejecuta llamada HTTP a un proveedor. Retorna texto o None."""
        api_key = os.environ.get(cfg["api_key_env"])
        if not api_key:
            logger.warning(f"[{cfg['name']}] Sin API key")
            return None

        try:
            if cfg["name"] == "gemini":
                url = f"{cfg['endpoint']}?key={api_key}"
                payload = {"contents": [{"parts": [{"text": prompt}]}]}
                headers = {"Content-Type": "application/json"}
            elif cfg["name"] == "nvidia_nim":
                url = cfg["endpoint"]
                payload = {
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 1024,
                }
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
            else:
                url = cfg["endpoint"]
                payload = {
                    "model": cfg["model"],
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                }
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
                extra_headers = cfg.get("headers", {})
                headers.update(extra_headers)

            resp = await client.post(url, json=payload, headers=headers, timeout=cfg["timeout"])

            if resp.status_code in QUOTA_CODES:
                logger.warning(f"[{cfg['name']}] Rate limit/saturated ({resp.status_code})")
                return None

            if resp.status_code != 200:
                logger.error(f"[{cfg['name']}] HTTP {resp.status_code}: {resp.text[:200]}")
                return None

            data = resp.json()
            if cfg["name"] == "gemini":
                return (
                    data.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
                )
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")

        except httpx.TimeoutException:
            logger.warning(f"[{cfg['name']}] Timeout")
        except httpx.ConnectError:
            logger.warning(f"[{cfg['name']}] Connection refused")
        except Exception as e:
            logger.error(f"[{cfg['name']}] Error: {e}")
        return None

    async def route(self, prompt: str, memory_inject: bool = True) -> Dict:
        """Ejecuta cadena de fallback completa."""
        final_prompt = self._inject_memory(prompt) if memory_inject else prompt
        fallback_log = []

        async with httpx.AsyncClient() as client:
            for cfg in PROVIDER_CHAIN:
                start = time.time()
                response = await self._call_provider(client, cfg, final_prompt)
                elapsed = round((time.time() - start) * 1000, 2)

                if response:
                    logger.info(f"✅ [{cfg['name']}] OK en {elapsed}ms")
                    return {
                        "provider": cfg["name"],
                        "response": response,
                        "latency_ms": elapsed,
                        "fallback_chain": fallback_log,
                    }
                fallback_log.append({"provider": cfg["name"], "latency_ms": elapsed})

        return {
            "provider": None,
            "response": None,
            "error": "Todos los proveedores fallaron",
            "fallback_chain": fallback_log,
        }

    async def neural_room(self, prompt: str) -> Dict[str, str]:
        """Modo Neural Room: ejecuta peticiones en paralelo a múltiples proveedores."""
        final_prompt = self._inject_memory(prompt)
        responses = {}
        async with httpx.AsyncClient() as client:
            tasks = [self._call_provider(client, cfg, final_prompt) for cfg in PROVIDER_CHAIN]
            results = await asyncio.gather(*tasks)
            for cfg, result in zip(PROVIDER_CHAIN, results):
                responses[cfg["name"]] = result or "[sin respuesta]"
        return responses


# ── Función de alto nivel para uso rápido ───────────────────────
async def ask(prompt: str, mode: str = "standard") -> Dict:
    router = NeuralRouter()
    if mode == "neural_room":
        return await router.neural_room(prompt)
    return await router.route(prompt)

