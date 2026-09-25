import asyncio
import json
import os
from typing import Any, Dict, List, Optional


class CircuitBreaker:
    def __init__(
        self, name: str = "", failure_threshold: int = 5, recovery_timeout: float = 30.0
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state: str = "closed"
        self._failure_count: int = 0
        self._last_failure_time: float = 0.0
        self._success_count: int = 0

    async def call(self, func, *args, **kwargs) -> Any:
        if self._state == "open":
            if asyncio.get_event_loop().time() - self._last_failure_time < self.recovery_timeout:
                raise Exception(f"Circuit breaker '{self.name}' is open")
            self._state = "half-open"

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        self._success_count += 1
        if self._state == "half-open":
            self._state = "closed"
            self._failure_count = 0

    def _on_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = asyncio.get_event_loop().time()
        if self._failure_count >= self.failure_threshold:
            self._state = "open"

    @property
    def state(self) -> str:
        return self._state


class RetryStrategy:
    def __init__(
        self, max_retries: int = 5, base_delay: float = 1.0, max_delay: float = 30.0
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    async def execute(self, func, *args, **kwargs) -> Any:
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                last_exc = exc
                if attempt == self.max_retries - 1:
                    break
                delay = min(self.base_delay * (2**attempt), self.max_delay)
                delay += random.uniform(0, delay * 0.1)
                await asyncio.sleep(delay)
        raise last_exc


class GracefulDegradation:
    def __init__(self) -> None:
        self._modes: List[str] = ["full", "simple", "minimal", "cache"]
        self._current_mode: str = "full"
        self._memory_threshold: float = 0.9
        self._cpu_threshold: float = 0.9

    def check_and_degrade(self, metrics: Dict[str, float]) -> str:
        if metrics.get("memory_usage", 0) > self._memory_threshold:
            self._current_mode = "cache"
        elif metrics.get("cpu_usage", 0) > self._cpu_threshold:
            self._current_mode = "minimal"
        elif self._current_mode != "full":
            self._current_mode = "simple" if metrics.get("load", 0) > 0.7 else "full"
        return self._current_mode

    def get_cache_config(self) -> Dict[str, Any]:
        if self._current_mode == "cache":
            return {"max_size": 100, "ttl": 60, "compress": True}
        return {"max_size": 1000, "ttl": 300, "compress": False}
