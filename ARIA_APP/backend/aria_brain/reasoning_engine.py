import asyncio
from typing import Any, Dict, List, Optional


class ReasoningEngine:
    def __init__(self) -> None:
        self._rules: List[Dict[str, Any]] = []
        self._facts: Dict[str, Any] = {}
        self._assumptions: List[str] = []

    def add_rule(self, condition: str, conclusion: str, confidence: float = 0.8) -> None:
        self._rules.append(
            {"condition": condition, "conclusion": conclusion, "confidence": confidence}
        )

    def add_fact(self, fact: str, value: Any = True) -> None:
        self._facts[fact] = value

    def set_assumption(self, assumption: str) -> None:
        self._assumptions.append(assumption)

    async def reason_about(self, situation: str) -> Dict[str, Any]:
        logical = await self._logical_reasoning(situation)
        abductive = await self._abductive_reasoning(situation)
        analogical = await self._analogical_reasoning(situation)
        causal = await self._causal_reasoning(situation)
        counterfactual = await self._counterfactual_reasoning(situation)

        return {
            "situation": situation,
            "logical": logical,
            "abductive": abductive,
            "analogical": analogical,
            "causal": causal,
            "counterfactual": counterfactual,
            "best_conclusion": self._synthesize(
                logical, abductive, analogical, causal, counterfactual
            ),
        }

    async def _logical_reasoning(self, situation: str) -> Dict[str, Any]:
        applicable = [r for r in self._rules if r["condition"].lower() in situation.lower()]
        conclusions = [r["conclusion"] for r in applicable]
        confidence = sum(r["confidence"] for r in applicable) / max(len(applicable), 1)
        return {
            "conclusions": conclusions,
            "confidence": confidence,
            "rules_applied": len(applicable),
        }

    async def _abductive_reasoning(self, situation: str) -> Dict[str, Any]:
        hypotheses = []
        words = situation.lower().split()
        for rule in self._rules:
            rule_words = rule["condition"].lower().split()
            overlap = sum(1 for w in rule_words if w in words)
            if overlap > 0:
                hypotheses.append(
                    {
                        "hypothesis": rule["conclusion"],
                        "likelihood": overlap / len(rule_words),
                        "rule": rule["condition"],
                    }
                )
        hypotheses.sort(key=lambda x: x["likelihood"], reverse=True)
        best = hypotheses[0] if hypotheses else {"hypothesis": "unknown", "likelihood": 0.0}
        return {
            "best_hypothesis": best["hypothesis"],
            "confidence": best["likelihood"],
            "alternatives": hypotheses[:3],
        }

    async def _analogical_reasoning(self, situation: str) -> Dict[str, Any]:
        sources = [s for s in self._assumptions if s.lower() in situation.lower()]
        mappings = []
        for src in sources:
            for rule in self._rules:
                if src in rule["condition"]:
                    mappings.append(
                        {"source": src, "target": rule["conclusion"], "similarity": 0.7}
                    )
        return {"mappings": mappings, "insights": [m["target"] for m in mappings[:3]]}

    async def _causal_reasoning(self, situation: str) -> Dict[str, Any]:
        causes = [
            r
            for r in self._rules
            if "if" in r["condition"].lower() and "then" in r["conclusion"].lower()
        ]
        effects = [r["conclusion"] for r in causes if r["condition"].lower() in situation.lower()]
        return {"causes": effects, "predicted_effects": effects, "chain_depth": len(effects)}

    async def _counterfactual_reasoning(self, situation: str) -> Dict[str, Any]:
        alternatives = []
        for rule in self._rules:
            if "not" not in situation.lower():
                alt = f"IF NOT ({rule['condition']}) THEN {rule['conclusion']}"
                alternatives.append(alt)
        return {
            "scenarios": alternatives[:5],
            "key_difference": "Alternative path analysis",
            "impact": "Medium",
        }

    def _synthesize(self, *results: Dict[str, Any]) -> str:
        all_conclusions = []
        for r in results:
            for key in ["conclusions", "best_hypothesis", "insights", "causes"]:
                val = r.get(key)
                if val and isinstance(val, list):
                    all_conclusions.extend(val)
                elif val:
                    all_conclusions.append(str(val))
        return (
            " | ".join(str(c) for c in all_conclusions[:3]) if all_conclusions else "No conclusion"
        )

    async def multi_step_reason(self, problem: str, max_steps: int = 5) -> Dict[str, Any]:
        """Multi-step reasoning with confidence scoring and fallback."""
        steps = []
        current = problem
        overall_confidence = 1.0

        for i in range(max_steps):
            result = await self.reason_about(current)
            confidence = self._calculate_step_confidence(result)
            steps.append({
                "step": i + 1,
                "input": current,
                "output": result.get("best_conclusion", ""),
                "confidence": confidence,
                "details": result,
            })
            overall_confidence *= confidence

            # Check if we have a satisfactory answer
            if confidence >= 0.7 and i >= 1:
                break

            # Generate next question from current conclusion
            conclusion = result.get("best_conclusion", "")
            if conclusion and conclusion != "No conclusion" and i < max_steps - 1:
                current = f"Based on: {conclusion}, what next?"
            else:
                break

        return {
            "problem": problem,
            "steps": steps,
            "total_steps": len(steps),
            "overall_confidence": round(overall_confidence, 3),
            "sufficient": overall_confidence >= 0.6,
            "final_answer": steps[-1]["output"] if steps else "",
        }

    def _calculate_step_confidence(self, result: Dict[str, Any]) -> float:
        """Calculate confidence for a reasoning step."""
        confidences = []
        for key in ["logical", "abductive", "causal"]:
            r = result.get(key, {})
            if isinstance(r, dict):
                c = r.get("confidence", 0)
                confidences.append(c)
        if not confidences:
            return 0.5
        return sum(confidences) / len(confidences)
