from collections import defaultdict
from datetime import datetime
from typing import Dict, Tuple


class RateLimiter:
    def __init__(self, requests_per_second: int = 100):
        self.requests_per_second = requests_per_second
        self.buckets: Dict[str, Tuple[float, datetime]] = defaultdict(
            lambda: (float(self.requests_per_second), datetime.utcnow())
        )

    async def check_rate_limit(self, client_id: str) -> bool:
        now = datetime.utcnow()
        tokens, last_update = self.buckets[client_id]
        elapsed = (now - last_update).total_seconds()
        tokens = min(self.requests_per_second, tokens + elapsed * self.requests_per_second)
        if tokens >= 1:
            tokens -= 1
            self.buckets[client_id] = (tokens, now)
            return True
        self.buckets[client_id] = (tokens, now)
        return False


rate_limiter = RateLimiter(requests_per_second=100)
