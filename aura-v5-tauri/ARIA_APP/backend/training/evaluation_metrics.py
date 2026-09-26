import asyncio
import math
from typing import Any, Dict, List, Optional


class EvaluationMetrics:
    def __init__(self) -> None:
        self._last_evaluation: Optional[Dict[str, Any]] = None

    async def evaluate_model(
        self, predictions: List[str], targets: List[str], metrics: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        if metrics is None:
            metrics = ["bleu", "rouge", "perplexity"]

        results = {}
        if "bleu" in metrics:
            results["bleu"] = self._bleu(predictions, targets)
        if "rouge" in metrics:
            results["rouge"] = self._rouge(predictions, targets)
        if "perplexity" in metrics:
            results["perplexity"] = self._perplexity(predictions)
        if "f1" in metrics:
            results["f1"] = self._f1(predictions, targets)
        if "accuracy" in metrics:
            results["accuracy"] = self._accuracy(predictions, targets)

        self._last_evaluation = results
        return results

    def _bleu(self, predictions: List[str], targets: List[str]) -> float:
        if not predictions or not targets:
            return 0.0
        matches = sum(
            1 for p, t in zip(predictions, targets) if p.strip().lower() == t.strip().lower()
        )
        return matches / min(len(predictions), len(targets))

    def _rouge(self, predictions: List[str], targets: List[str]) -> float:
        if not predictions or not targets:
            return 0.0
        scores = []
        for p, t in zip(predictions, targets):
            p_tokens = set(p.lower().split())
            t_tokens = set(t.lower().split())
            if not t_tokens:
                scores.append(0.0)
                continue
            overlap = len(p_tokens & t_tokens) / len(t_tokens)
            scores.append(overlap)
        return sum(scores) / len(scores) if scores else 0.0

    def _perplexity(self, predictions: List[str]) -> float:
        if not predictions:
            return 1000.0
        total_tokens = sum(len(p.split()) for p in predictions)
        return max(1.0, total_tokens / len(predictions))

    def _f1(self, predictions: List[str], targets: List[str]) -> float:
        if not predictions or not targets:
            return 0.0
        tp = sum(1 for p, t in zip(predictions, targets) if p.strip().lower() == t.strip().lower())
        precision = tp / len(predictions) if predictions else 0.0
        recall = tp / len(targets) if targets else 0.0
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)

    def _accuracy(self, predictions: List[str], targets: List[str]) -> float:
        if not predictions or not targets:
            return 0.0
        correct = sum(
            1 for p, t in zip(predictions, targets) if p.strip().lower() == t.strip().lower()
        )
        return correct / min(len(predictions), len(targets))
