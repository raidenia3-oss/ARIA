import asyncio
import time
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional


class HealthCheck:
    def __init__(self) -> None:
        self._services: Dict[str, Dict[str, Any]] = {}
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
