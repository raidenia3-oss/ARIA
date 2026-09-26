from typing import Any, Dict, List, Optional


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
