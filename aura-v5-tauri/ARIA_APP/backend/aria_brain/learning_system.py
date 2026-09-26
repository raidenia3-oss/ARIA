import asyncio
import random
from typing import Any, Dict, List, Optional, Tuple


class LearningSystem:
    def __init__(self) -> None:
        self._q_table: Dict[str, float] = {}
        self._weights: Dict[str, float] = {}
        self._patterns: List[Dict[str, Any]] = []
        self._rewards: List[float] = []
        self._learning_rate: float = 0.01
        self._discount_factor: float = 0.95
        self._exploration_rate: float = 0.1

    async def learn_from_feedback(
        self,
        action: str,
        reward: float,
        state: Optional[str] = None,
        next_state: Optional[str] = None,
    ) -> Dict[str, Any]:
        state_key = state or "default"
        next_key = next_state or state_key

        current_q = self._q_table.get(f"{state_key}:{action}", 0.0)
        next_max_q = max(
            [v for k, v in self._q_table.items() if k.startswith(f"{next_key}:")], default=0.0
        )
        new_q = current_q + self._learning_rate * (
            reward + self._discount_factor * next_max_q - current_q
        )
        self._q_table[f"{state_key}:{action}"] = new_q

        self._rewards.append(reward)

        return {"updated": True, "new_q": new_q, "action": action, "reward": reward}

    async def supervised_learn(self, examples: List[Dict[str, Any]]) -> Dict[str, Any]:
        for example in examples:
            features = example.get("features", [])
            label = example.get("label")
            for feature in features:
                key = f"{feature}:{label}"
                self._weights[key] = self._weights.get(key, 0.0) + 0.01
        return {"learned": len(examples), "weights_updated": len(self._weights)}

    async def unsupervised_discover(self, data: List[Any]) -> List[Dict[str, Any]]:
        if not data:
            return []
        clusters: Dict[int, List[Any]] = {}
        for item in data:
            bucket = hash(str(item)) % min(len(data), 10)
            clusters.setdefault(bucket, []).append(item)
        return [{"cluster": k, "size": len(v), "sample": v[:3]} for k, v in clusters.items()]

    async def meta_learn(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        task_performances = []
        for task in tasks:
            success = task.get("success", False)
            task_performances.append(1.0 if success else 0.0)
        avg_performance = sum(task_performances) / max(len(task_performances), 1)
        new_lr = self._learning_rate * (1.0 + avg_performance)
        self._learning_rate = min(new_lr, 0.1)
        return {
            "avg_performance": avg_performance,
            "new_learning_rate": self._learning_rate,
            "tasks_processed": len(tasks),
        }
