import asyncio
import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional


class ConnectorBase:
    def __init__(self, name: str = "") -> None:
        self.name = name or self.__class__.__name__
        self._connected: bool = False
        self._last_check: float = 0.0
        self._failure_count: int = 0
        self._total_requests: int = 0
        self._success_count: int = 0
        self._circuit_open: bool = False
        self._circuit_opened_at: float = 0.0
        self._fallback_data: List[Dict[str, Any]] = []

    async def connect(self) -> bool:
        try:
            await self.verify_connection()
            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False

    async def verify_connection(self) -> bool:
        raise NotImplementedError

    async def retry_with_exponential_backoff(
        self, func, max_retries: int = 5, base_delay: float = 1.0, *args, **kwargs
    ) -> Any:
        last_exc: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                if self._circuit_open:
                    if time.time() - self._circuit_opened_at < 30:
                        raise Exception("Circuit breaker open")
                    self._circuit_open = False
                return await func(*args, **kwargs)
            except Exception as exc:
                last_exc = exc
                self._failure_count += 1
                delay = base_delay * (2**attempt) + (await self._jitter())
                await asyncio.sleep(delay)
        if self._failure_count >= 5:
            self._circuit_open = True
            self._circuit_opened_at = time.time()
        raise last_exc

    async def _jitter(self) -> float:
        import random

        return random.uniform(0, 0.5)

    async def fallback_mechanism(self, operation: str, **kwargs) -> Dict[str, Any]:
        return {
            "fallback": True,
            "connector": self.name,
            "operation": operation,
            "timestamp": datetime.now().isoformat(),
            "message": "Using local fallback",
        }

    async def log_request(self, method: str, path: str, duration: float, status: str) -> None:
        self._total_requests += 1
        if status == "success":
            self._success_count += 1

    @property
    def availability(self) -> float:
        if self._total_requests == 0:
            return 1.0
        return self._success_count / self._total_requests

    @property
    def is_available(self) -> bool:
        return self._connected and not self._circuit_open
