"""Atria Client — Cliente base con rate limiting + token tracking inteligente.

Integra la API de Atria Dawn para generacion de datos de training,
mejora de respuestas, sintesis de skills y meta-aprendizaje.

Import: este paquete no es importable directo (`integration.py:7` hace
`from backend.atria_integration...`); el smoke test debe correr con
`PYTHONPATH=ARIA_APP`, como ya hace `ARIA_APP/scripts/verify_all.py:9`.
"""

import httpx
import asyncio
import time
import os
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path


class AtriaClient:
    """Cliente Atria Dawn con rate limiting + token tracking inteligente.

    Configuracion:
    - Ollama = Produccion (sin costo, sin limite)
    - Atria = Inteligencia estrategica (~4M tokens/mes, 100M tokens duran 2+ anios)
    """

    RPM_LIMIT_HEADER = "x-rpm-limit"
    # El servidor publica su tasa en el header `x-rpm-limit`. Antes hardcodeábamos
    # 100, con lo que ARIA se auto-limitaba a la mitad de la tasa real sin avisar.
    # 50 es el valor por defecto que declara el servidor hasta que el header lo
    # confirme; en cuanto llegue, pasa a ser el valor medido.
    DEFAULT_RATE_LIMIT = 50

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ATRIA_API_KEY", "")
        self.base_url = os.environ.get("ATRIA_API_URL", "https://api.atria-asi.ai/v1")
        self.model = os.environ.get("ATRIA_MODEL", "Atria-Dawn-Preview")
        self.available = bool(self.api_key)

        # Rate limiting. `rate_limit` arranca en el default DECLARADO por el
        # servidor, no en uno medido por nosotros: `rate_limit_source` dice cual de
        # los dos es. Se inicializa aqui (antes del early return) para que el
        # atributo exista siempre, incluso sin API key.
        self.rate_limit = self.DEFAULT_RATE_LIMIT
        self.rate_limit_source = "unavailable"
        self.requests_this_minute = 0
        self.minute_start = time.time()

        if not self.available:
            print("[AtriaClient] Warning: API key no configurada. Set ATRIA_API_KEY.")
            return

        self.client = httpx.AsyncClient(timeout=60.0)

        # Token tracking (100M total, 4M monthly budget)
        self.tokens_total = 100_000_000
        self.tokens_used = 0
        self.tokens_monthly_budget = 4_000_000
        self.tokens_monthly_used = 0
        self.month_reset = datetime.now()

        # Usage by category (ROI tracking)
        self.usage_by_category = {
            "training": 0,
            "enhancement": 0,
            "skills": 0,
            "reasoning": 0,
            "knowledge": 0,
            "meta_learning": 0,
            "general": 0,
        }

        # Request history for analytics
        self.request_history: List[dict] = []

        # ROI tracking
        self.value_generated = 0

    async def request(
        self,
        prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.7,
        category: str = "general",
    ) -> Dict[str, Any]:
        """Realiza request a Atria con validaciones completas."""

        if not self.available:
            return {
                "error": "ATRIA_NOT_CONFIGURED",
                "message": "Set ATRIA_API_KEY environment variable.",
                "success": False,
            }

        # 1. Check rate limit
        await self._check_rate_limit()

        # 2. Check tokens
        estimated_tokens = self._estimate_tokens(prompt, max_tokens)

        if self.tokens_used + estimated_tokens > self.tokens_total:
            return {
                "error": "TOKENS_EXHAUSTED",
                "tokens_remaining": self.tokens_total - self.tokens_used,
                "tokens_needed": estimated_tokens,
                "success": False,
            }

        if self.tokens_monthly_used + estimated_tokens > self.tokens_monthly_budget:
            return {
                "error": "MONTHLY_BUDGET_EXCEEDED",
                "monthly_used": self.tokens_monthly_used,
                "monthly_budget": self.tokens_monthly_budget,
                "success": False,
            }

        # 3. Validate category
        if category not in self.usage_by_category:
            category = "general"

        # 4. Make request
        try:
            messages = [{"role": "user", "content": prompt}]

            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": False,
                },
            )

            # Antes de raise_for_status: un 429 tambien trae el header del
            # servidor, y es justo el caso en el que el limite importa mas.
            self._observe_rpm_limit(response.headers)

            response.raise_for_status()
            data = response.json()

            choices = data.get("choices", [])
            if not choices:
                return {"error": "Empty response from Atria", "success": False}

            text = choices[0].get("message", {}).get("content", "") or ""
            usage = data.get("usage", {})
            actual_tokens = usage.get("total_tokens", estimated_tokens)

            # 5. Update tracking
            self.tokens_used += actual_tokens
            self.tokens_monthly_used += actual_tokens
            self.usage_by_category[category] = self.usage_by_category.get(category, 0) + actual_tokens
            self.requests_this_minute += 1
            self.value_generated += max(1, actual_tokens // 100)

            # 6. Log request
            self.request_history.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "category": category,
                    "tokens_used": actual_tokens,
                    "prompt_length": len(prompt),
                    "response_length": len(text),
                }
            )

            return {
                "response": text,
                "tokens_used": actual_tokens,
                "tokens_remaining": self.tokens_total - self.tokens_used,
                "success": True,
                "category": category,
                "model": self.model,
            }

        except httpx.HTTPStatusError as e:
            # HTTPStatusError es subclase de HTTPError: esta rama DEBE ir
            # primero o nunca se ejecutaria. Un 429 no es un error opaco,
            # es el servidor diciendonos cual es su tasa.
            if e.response is not None and e.response.status_code == 429:
                return {
                    "error": "RATE_LIMITED",
                    "rate_limit": self.rate_limit,
                    "rate_limit_source": self.rate_limit_source,
                    "status_code": 429,
                    "success": False,
                }
            return {"error": str(e), "success": False}
        except httpx.HTTPError as e:
            return {"error": str(e), "success": False}
        except Exception as e:
            return {"error": str(e), "success": False}

    def _observe_rpm_limit(self, headers: Optional[Any]) -> None:
        """Adopta la tasa real declarada por el servidor en `x-rpm-limit`.

        Es la unica lectura honesta del limite: la unica respuesta que tenemos es
        la que `request()` ya recibe, asi que no hay endpoint que consultar.
        Si el header falta, viene vacio, no es un entero o es <= 0, NO se inventa
        nada: `rate_limit` y `rate_limit_source` se quedan como estaban.
        """
        if headers is None:
            return

        raw = None
        getter = getattr(headers, "get", None)
        if callable(getter):
            raw = getter(self.RPM_LIMIT_HEADER)

        if raw is None:
            # dicts planos no son case-insensitive como httpx.Headers.
            items = getattr(headers, "items", None)
            if callable(items):
                for key, value in items():
                    if str(key).lower() == self.RPM_LIMIT_HEADER:
                        raw = value
                        break

        if raw is None:
            return

        if isinstance(raw, str) and not raw.strip():
            return

        try:
            limit = int(raw)
        except (TypeError, ValueError):
            return

        if limit <= 0:
            return

        self.rate_limit = limit
        self.rate_limit_source = "measured"

    async def _check_rate_limit(self):
        """Chequea el rate limit contra `self.rate_limit`.

        Ese limite no es un 100 fijo: viene observado del header `x-rpm-limit`
        del servidor (source "measured") o, hasta que llegue, del default
        declarado por el servidor (source "unavailable").
        """
        now = time.time()

        if now - self.minute_start > 60:
            self.requests_this_minute = 0
            self.minute_start = now

        if self.requests_this_minute >= self.rate_limit:
            wait_time = 60 - (now - self.minute_start)
            if wait_time > 0:
                await asyncio.sleep(wait_time + 1)
            self.requests_this_minute = 0
            self.minute_start = time.time()

    def _estimate_tokens(self, prompt: str, max_tokens: int) -> int:
        """Estima tokens (aproximacion)"""
        return len(prompt.split()) + max_tokens + 50

    def _check_monthly_reset(self):
        """Reset si cambio de mes"""
        if datetime.now() - self.month_reset > timedelta(days=30):
            self.tokens_monthly_used = 0
            self.month_reset = datetime.now()

    def get_token_status(self) -> Dict[str, Any]:
        """Status detallado de tokens y ROI"""
        self._check_monthly_reset()

        monthly_pct = (
            (self.tokens_monthly_used / self.tokens_monthly_budget) * 100
            if self.tokens_monthly_budget > 0 else 0
        )
        total_pct = (
            (self.tokens_used / self.tokens_total) * 100 if self.tokens_total > 0 else 0
        )
        daily_usage = (
            self.tokens_monthly_used / max((datetime.now() - self.month_reset).days, 1)
        )
        days_remaining = (
            (self.tokens_total - self.tokens_used) / daily_usage
            if daily_usage > 0 else float("inf")
        )

        return {
            "tokens_total": self.tokens_total,
            "tokens_used": self.tokens_used,
            "tokens_remaining": self.tokens_total - self.tokens_used,
            "total_percentage": round(total_pct, 2),
            "monthly_used": self.tokens_monthly_used,
            "monthly_budget": self.tokens_monthly_budget,
            "monthly_percentage": round(monthly_pct, 2),
            "daily_usage": round(daily_usage),
            "days_until_exhaustion": round(days_remaining, 1) if days_remaining != float("inf") else "N/A",
            "usage_by_category": self.usage_by_category,
            "request_count": len(self.request_history),
            "value_generated": self.value_generated,
            "rate_limit": self.rate_limit,
            "rate_limit_source": self.rate_limit_source,
            "available": self.available,
        }

    def get_roi_report(self) -> Dict[str, Any]:
        """Reporte de ROI por categoria"""
        total_cat_tokens = sum(self.usage_by_category.values())
        if total_cat_tokens == 0:
            return {"message": "No hay datos de uso aun."}

        categories = {}
        for cat, tokens in self.usage_by_category.items():
            if tokens > 0:
                multipliers = {
                    "training": 5.0,
                    "reasoning": 3.0,
                    "skills": 4.0,
                    "enhancement": 2.0,
                    "knowledge": 2.5,
                    "meta_learning": 3.5,
                }
                multiplier = multipliers.get(cat, 2.0)
                categories[cat] = {
                    "tokens": tokens,
                    "estimated_value": int(tokens * multiplier / 100),
                    "percentage_of_total": round((tokens / total_cat_tokens) * 100, 2),
                }

        return {
            "total_tokens_spent": total_cat_tokens,
            "categories": categories,
            "total_estimated_value": sum(c["estimated_value"] for c in categories.values()),
            "roi_ratio": round(
                sum(c["estimated_value"] for c in categories.values())
                / max(total_cat_tokens / 100, 1),
                2,
            ),
        }

    async def close(self):
        """Cierra el cliente HTTP"""
        if hasattr(self, "client"):
            await self.client.aclose()
