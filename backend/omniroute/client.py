from __future__ import annotations

import httpx
import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, AsyncGenerator, Union
from backend.omniroute.models import (
    OmnirouteConfig,
    ProviderInfo,
    ProviderStatus,
)


class OmnirouteClient:
    """Cliente para Omniroute API"""

    def __init__(self, config: OmnirouteConfig):
        self.config = config
        self.client = httpx.AsyncClient(timeout=config.timeout)
        self.provider_cache: Dict[str, ProviderInfo] = {}
        self.last_cache_update: Optional[datetime] = None

    async def get_providers(self, force_refresh: bool = False) -> List[ProviderInfo]:
        """Obtener lista de proveedores disponibles"""
        if (
            self.last_cache_update
            and not force_refresh
            and (datetime.utcnow() - self.last_cache_update) < timedelta(minutes=5)
        ):
            return list(self.provider_cache.values())

        try:
            response = await self.client.get(
                f"{self.config.omniroute_url}/api/providers"
            )
            response.raise_for_status()

            providers_data = response.json()
            self.provider_cache = {
                p["name"]: ProviderInfo(**p)
                for p in providers_data.get("providers", [])
            }
            self.last_cache_update = datetime.utcnow()

            return list(self.provider_cache.values())

        except Exception as e:
            print(f"[Omniroute] Error fetching providers: {e}")
            return list(self.provider_cache.values()) if self.provider_cache else []

    async def get_best_provider(self, model_type: str = "general") -> Optional[ProviderInfo]:
        """Obtener mejor proveedor segun scoring de 12 factores"""
        providers = await self.get_providers()

        healthy = [p for p in providers if p.status == ProviderStatus.HEALTHY]

        if not healthy:
            return None

        if healthy[0].score is not None:
            return sorted(healthy, key=lambda p: p.score or 0, reverse=True)[0]
        else:
            return sorted(healthy, key=lambda p: p.latency_ms or float("inf"))[0]

    async def chat(
        self,
        message: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False,
        context: Optional[List[Dict]] = None,
    ) -> Union[str, AsyncGenerator[str, None]]:
        """
        Chat con Omniroute (con fallback automatico)
        """
        attempt = 0
        last_error = None

        while attempt < self.config.retry_attempts:
            try:
                if not model:
                    provider = await self.get_best_provider()
                    if not provider:
                        raise Exception("No healthy providers available")
                    model = f"{provider.name}/{provider.model}"

                payload = {
                    "model": model,
                    "messages": context or [{"role": "user", "content": message}],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": stream,
                }

                response = await self.client.post(
                    f"{self.config.omniroute_url}/api/chat/completions",
                    json=payload,
                )
                response.raise_for_status()

                if stream:

                    async def stream_response():
                        async with response:
                            async for line in response.aiter_lines():
                                if line.startswith("data: "):
                                    try:
                                        data = json.loads(line[6:])
                                        chunk = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                        if chunk:
                                            yield chunk
                                    except Exception:
                                        pass

                    return stream_response()

                else:
                    data = response.json()
                    return data.get("choices", [{}])[0].get("message", {}).get("content", "")

            except Exception as e:
                last_error = e
                attempt += 1

                if attempt < self.config.retry_attempts and self.config.fallback_enabled:
                    print(f"[Omniroute] Attempt {attempt} failed: {e}. Trying next provider...")
                    await asyncio.sleep(1)
                else:
                    raise last_error or Exception("All providers failed")

        raise last_error or Exception("Max retry attempts exceeded")

    async def get_health(self) -> Dict:
        """Verificar salud de Omniroute"""
        try:
            response = await self.client.get(
                f"{self.config.omniroute_url}/api/health"
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def close(self):
        """Cerrar cliente"""
        await self.client.aclose()
