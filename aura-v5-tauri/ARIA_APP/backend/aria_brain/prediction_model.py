import asyncio
import random
from typing import Any, Dict, List, Optional


class PredictionModel:
    def __init__(self) -> None:
        self._action_history: List[Dict[str, Any]] = []
        self._transition_matrix: Dict[str, Dict[str, float]] = {}
        self._user_patterns: Dict[str, List[str]] = []
        self._last_states: List[str] = []

    async def predict_next_action(self, context: Optional[str] = None) -> Dict[str, Any]:
        if not self._action_history:
            return {"prediction": "continue_current", "confidence": 0.5, "method": "default"}

        recent = [h["action"] for h in self._action_history[-10:]]
        prediction = self._markov_predict(recent)
        confidence = self._compute_confidence(recent, prediction)

        return {
            "prediction": prediction,
            "confidence": confidence,
            "method": "markov_chain",
            "context": context,
            "based_on": len(self._action_history),
        }

    async def predict_sentiment(self, recent_texts: List[str]) -> Dict[str, Any]:
        if not recent_texts:
            return {"sentiment": "neutral", "confidence": 0.5}

        positive_words = {
            "good",
            "great",
            "happy",
            "love",
            "excellent",
            "amazing",
            "nice",
            "perfect",
        }
        negative_words = {"bad", "terrible", "hate", "awful", "horrible", "wrong", "broken", "fail"}

        pos_count = 0
        neg_count = 0
        for text in recent_texts:
            words = text.lower().split()
            pos_count += sum(1 for w in words if w in positive_words)
            neg_count += sum(1 for w in words if w in negative_words)

        total = pos_count + neg_count
        if total == 0:
            return {"sentiment": "neutral", "confidence": 0.5}
        if pos_count > neg_count:
            return {"sentiment": "positive", "confidence": pos_count / total}
        elif neg_count > pos_count:
            return {"sentiment": "negative", "confidence": neg_count / total}
        return {"sentiment": "neutral", "confidence": 0.5}

    async def predict_interests(self, history: List[str]) -> List[Dict[str, Any]]:
        interest_scores: Dict[str, float] = {}
        for item in history:
            words = item.lower().split()
            for word in words:
                if len(word) > 4:
                    interest_scores[word] = interest_scores.get(word, 0.0) + 1.0

        sorted_interests = sorted(interest_scores.items(), key=lambda x: x[1], reverse=True)[:10]
        total = sum(v for _, v in sorted_interests) or 1.0
        return [{"topic": k, "score": v / total} for k, v in sorted_interests]

    def record_action(self, action: str, context: Optional[str] = None) -> None:
        self._action_history.append(
            {"action": action, "context": context, "timestamp": asyncio.get_event_loop().time()}
        )
        if len(self._action_history) > 1000:
            self._action_history = self._action_history[-1000:]

    def _markov_predict(self, recent: List[str]) -> str:
        if len(recent) < 2:
            return random.choice(recent) if recent else "continue"
        current = recent[-1]
        transitions = self._transition_matrix.setdefault(current, {})
        if transitions:
            return max(transitions, key=transitions.get)
        return recent[-1]

    def _compute_confidence(self, recent: List[str], prediction: str) -> float:
        base = 0.5
        if prediction in recent[:-1]:
            base += 0.3
        if len(recent) > 5:
            base += 0.2
        return min(base, 0.99)
