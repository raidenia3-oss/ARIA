import asyncio
import time
from typing import Any, Optional


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
