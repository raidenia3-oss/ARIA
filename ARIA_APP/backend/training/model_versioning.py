import asyncio
import json
import os
import time
from typing import Any, Dict, List, Optional


class ModelVersioning:
    def __init__(self, model_dir: str = "") -> None:
        self.model_dir = model_dir or os.path.join(os.path.dirname(__file__), "..", "models")
        os.makedirs(self.model_dir, exist_ok=True)
        self._versions: List[Dict[str, Any]] = []
        self._ab_test: Optional[Dict[str, Any]] = None

    async def save_version(
        self, model_data: Optional[Dict[str, Any]] = None, metrics: Optional[Dict[str, Any]] = None
    ) -> str:
        version_id = f"v{int(time.time())}"
        version = {
            "version_id": version_id,
            "timestamp": time.time(),
            "model_data": model_data or {},
            "metrics": metrics or {},
            "performance": metrics.get("accuracy", 0.0) if metrics else 0.0,
        }
        self._versions.append(version)

        version_path = os.path.join(self.model_dir, f"{version_id}.json")
        try:
            with open(version_path, "w") as f:
                json.dump(version, f)
        except Exception:
            pass

        if len(self._versions) > 1:
            await self._auto_evaluate(version_id)
        return version_id

    async def get_best_version(self) -> Optional[Dict[str, Any]]:
        if not self._versions:
            return None
        return max(self._versions, key=lambda v: v.get("performance", 0.0))

    async def rollback(self, version_id: str) -> bool:
        for v in self._versions:
            if v["version_id"] == version_id:
                v["rolled_back"] = True
                return True
        return False

    async def a_b_test(
        self, version_a: str, version_b: str, traffic_split: float = 0.5
    ) -> Dict[str, Any]:
        self._ab_test = {
            "version_a": version_a,
            "version_b": version_b,
            "traffic_split": traffic_split,
            "started_at": time.time(),
            "results_a": [],
            "results_b": [],
        }
        return self._ab_test

    async def record_ab_result(self, version: str, metric: float) -> None:
        if self._ab_test:
            key = "results_a" if version == self._ab_test["version_a"] else "results_b"
            getattr(self._ab_test, key).append(metric)

    async def _auto_evaluate(self, version_id: str) -> None:
        if len(self._versions) < 2:
            return
        current = self._versions[-1]
        previous = self._versions[-2]
        if current.get("performance", 0) < previous.get("performance", 0) * 0.95:
            current["degraded"] = True
            await self.rollback(current_id := current["version_id"])
