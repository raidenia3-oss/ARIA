import asyncio
from typing import Any, Dict, List, Optional, Tuple


class DecisionMaking:
    def __init__(self) -> None:
        self._criteria_weights: Dict[str, float] = {}
        self._utility_functions: List[Dict[str, Any]] = []
        self._risk_threshold: float = 0.7

    def set_criteria_weight(self, criteria: str, weight: float) -> None:
        self._criteria_weights[criteria] = max(0.0, min(1.0, weight))

    def add_utility_function(self, name: str, formula: str, description: str = "") -> None:
        self._utility_functions.append(
            {"name": name, "formula": formula, "description": description}
        )

    async def make_decision(self, options: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not options:
            return {"decision": None, "confidence": 0.0, "reason": "No options provided"}

        scored = []
        for opt in options:
            score = await self._score_option(opt)
            risk = await self._assess_risk(opt)
            scored.append(
                {
                    "option": opt,
                    "score": score,
                    "risk": risk,
                    "adjusted": score * (1 - risk * self._risk_threshold),
                }
            )

        scored.sort(key=lambda x: x["adjusted"], reverse=True)
        best = scored[0]
        confidence = self._calculate_confidence(scored)

        alternatives = [{"option": s["option"], "score": s["adjusted"]} for s in scored[1:3]]

        return {
            "decision": best["option"],
            "score": best["score"],
            "adjusted_score": best["adjusted"],
            "confidence": confidence,
            "risk": best["risk"],
            "alternatives": alternatives,
            "all_scores": [{"option": s["option"], "score": s["adjusted"]} for s in scored],
        }

    async def _score_option(self, option: Dict[str, Any]) -> float:
        if not self._criteria_weights:
            return option.get("default_score", 0.5)
        total_weight = sum(self._criteria_weights.values())
        if total_weight == 0:
            return 0.5
        weighted_sum = 0.0
        for criteria, weight in self._criteria_weights.items():
            value = option.get(criteria, 0)
            if isinstance(value, (int, float)):
                normalized = min(max(value, 0.0), 1.0)
            elif isinstance(value, bool):
                normalized = 1.0 if value else 0.0
            else:
                normalized = 0.5
            weighted_sum += normalized * weight
        return weighted_sum / total_weight

    async def _assess_risk(self, option: Dict[str, Any]) -> float:
        risk_factors = option.get("risk_factors", [])
        if not risk_factors:
            return 0.1
        return min(sum(risk_factors) / len(risk_factors), 1.0)

    def _calculate_confidence(self, scored: List[Dict[str, Any]]) -> float:
        if not scored:
            return 0.0
        if len(scored) == 1:
            return 0.5
        best_score = scored[0]["adjusted"]
        second_score = scored[1]["adjusted"]
        diff = best_score - second_score
        return min(abs(diff) * 3, 0.99)
