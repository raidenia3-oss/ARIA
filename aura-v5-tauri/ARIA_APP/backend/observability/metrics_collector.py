import asyncio
import time
from datetime import datetime
from typing import Any, Dict, List, Optional


class HealthCheck:
    def __init__(self) -> None:
        self._services: Dict[str, Dict[str, Any]] = {}
        self._checks: List[Dict[str, Any]] = []
        self._interval: float = 60.0

    def register(self, name: str, url: str, timeout: float = 5.0) -> None:
        self._services[name] = {
            "url": url,
            "timeout": timeout,
            "last_check": None,
            "status": "unknown",
            "response_time": None,
            "error_count": 0,
        }

    async def check_all(self) -> Dict[str, Any]:
        results = {}
        for name, info in self._services.items():
            result = await self._check_service(name, info)
            results[name] = result
        return {"timestamp": datetime.now().isoformat(), "services": results}

    async def _check_service(self, name: str, info: Dict[str, Any]) -> Dict[str, Any]:
        start = time.time()
        try:
            import urllib.request

            req = urllib.request.Request(info["url"])
            with urllib.request.urlopen(req, timeout=info["timeout"]) as resp:
                elapsed = time.time() - start
                self._services[name].update(
                    {
                        "last_check": datetime.now().isoformat(),
                        "status": "healthy",
                        "response_time": elapsed,
                        "error_count": 0,
                    }
                )
                return {"name": name, "status": "healthy", "response_time_ms": int(elapsed * 1000)}
        except Exception as exc:
            self._services[name]["error_count"] += 1
            elapsed = time.time() - start
            self._services[name].update(
                {
                    "last_check": datetime.now().isoformat(),
                    "status": "unhealthy",
                    "response_time": elapsed,
                    "error": str(exc),
                }
            )
            return {
                "name": name,
                "status": "unhealthy",
                "error": str(exc),
                "response_time_ms": int(elapsed * 1000),
            }

    async def monitor_loop(self, interval: float = 60.0) -> None:
        self._interval = interval
        while True:
            await self.check_all()
            await asyncio.sleep(interval)


class MetricsCollector:
    def __init__(self) -> None:
        self._metrics: Dict[str, List[float]] = {}
        self._counters: Dict[str, int] = {}

    async def record_metric(self, name: str, value: float) -> None:
        if name not in self._metrics:
            self._metrics[name] = []
        self._metrics[name].append(value)
        if len(self._metrics[name]) > 1000:
            self._metrics[name] = self._metrics[name][-1000:]

    def get_metric(self, name: str) -> Optional[Dict[str, Any]]:
        if name not in self._metrics:
            return None
        values = self._metrics[name]
        return {
            "name": name,
            "count": len(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "last": values[-1],
        }

    async def increment(self, counter: str) -> None:
        self._counters[counter] = self._counters.get(counter, 0) + 1

    async def get_all_metrics(self) -> Dict[str, Any]:
        all_metrics = {name: self.get_metric(name) for name in self._metrics}
        return {
            "metrics": all_metrics,
            "counters": self._counters,
            "timestamp": datetime.now().isoformat(),
        }
