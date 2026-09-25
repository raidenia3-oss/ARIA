import asyncio
import random
from typing import Any, Callable, Optional


class RetryStrategy:
    def __init__(
        self, max_retries: int = 5, base_delay: float = 1.0, max_delay: float = 30.0
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    async def execute(self, func: Callable, *args, **kwargs) -> Any:
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
