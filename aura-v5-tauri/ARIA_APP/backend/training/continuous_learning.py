import asyncio
import random
from typing import Any, Dict, List, Optional


class ContinuousLearning:
    def __init__(self) -> None:
        self._feedback_buffer: List[Dict[str, Any]] = []
        self._learning_rate: float = 0.001
        self._epsilon: float = 1.0
        self._epsilon_decay: float = 0.995
        self._min_epsilon: float = 0.01
        self._interaction_count: int = 0

    async def learn_from_interaction(self, user_feedback: Dict[str, Any]) -> Dict[str, Any]:
        self._feedback_buffer.append(user_feedback)
        self._interaction_count += 1

        reward = user_feedback.get("reward", 0.0)
        self._update_epsilon()
        self._adapt_lr(reward)

        if len(self._feedback_buffer) > 1000:
            self._feedback_buffer = self._feedback_buffer[-500:]

        return {
            "learned": True,
            "buffer_size": len(self._feedback_buffer),
            "epsilon": self._epsilon,
            "learning_rate": self._learning_rate,
            "total_interactions": self._interaction_count,
        }

    def _update_epsilon(self) -> None:
        self._epsilon = max(self._min_epsilon, self._epsilon * self._epsilon_decay)

    def _adapt_lr(self, reward: float) -> None:
        if reward > 0.8:
            self._learning_rate = min(self._learning_rate * 1.1, 0.01)
        elif reward < 0.2:
            self._learning_rate = max(self._learning_rate * 0.9, 1e-6)

    def catastrophic_forgetting_prevention(
        self, new_weights: Dict[str, float], old_weights: Dict[str, float]
    ) -> Dict[str, float]:
        merged = {}
        all_keys = set(new_weights.keys()) | set(old_weights.keys())
        for key in all_keys:
            new_w = new_weights.get(key, 0.0)
            old_w = old_weights.get(key, 0.0)
            merged[key] = 0.9 * new_w + 0.1 * old_w
        return merged

    def get_stats(self) -> Dict[str, Any]:
        return {
            "epsilon": self._epsilon,
            "learning_rate": self._learning_rate,
            "interactions": self._interaction_count,
            "buffer_size": len(self._feedback_buffer),
        }
