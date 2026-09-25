import asyncio
from typing import Any, Dict, List, Optional


class ExplanationGenerator:
    def __init__(self) -> None:
        self._decision_log: List[Dict[str, Any]] = []

    async def explain_decision(
        self, decision: Any, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        reasoning = context.get("reasoning", {}) if context else {}
        scoring = context.get("scoring", {}) if context else {}
        emotion = context.get("emotion", {}) if context else {}
        prediction = context.get("prediction", {}) if context else {}
        memory = context.get("memory", {}) if context else {}

        explanation = []
        explanation.append(f"Decision: {decision}")

        if reasoning:
            best = reasoning.get("best_conclusion", "")
            if best and best != "No conclusion":
                explanation.append(f"Based on reasoning: {best}")

        if scoring:
            score = scoring.get("adjusted_score", 0)
            explanation.append(f"Scored {score:.3f} (weighted evaluation)")

        if emotion:
            dominant = emotion.get("dominant_emotion", "")
            if dominant:
                explanation.append(f"Emotional context: {dominant}")

        if prediction:
            pred = prediction.get("prediction", "")
            conf = prediction.get("confidence", 0)
            if pred:
                explanation.append(f"Predicted: {pred} (confidence: {conf:.0%})")

        if memory:
            if isinstance(memory, dict):
                count = len(memory) if hasattr(memory, "__len__") else 0
                explanation.append(f"Used {count} memory items for context")

        alternatives = context.get("alternatives", []) if context else []
        if alternatives:
            alt_str = "; ".join(
                [f"{a.get('option', {})}: {a.get('score', 0):.3f}" for a in alternatives[:2]]
            )
            explanation.append(f"Considered alternatives: {alt_str}")

        confidence = self._estimate_confidence(context) if context else 0.5

        self._decision_log.append(
            {"decision": decision, "explanation": " ".join(explanation), "confidence": confidence}
        )

        return {
            "decision": decision,
            "explanation": " ".join(explanation),
            "confidence": confidence,
            "components": {
                "reasoning": reasoning,
                "scoring": scoring,
                "emotion": emotion,
                "prediction": prediction,
                "memory": memory,
            },
            "uncertainties": self._identify_uncertainties(context) if context else [],
            "decision_log_size": len(self._decision_log),
        }

    def _estimate_confidence(self, context: Dict[str, Any]) -> float:
        score = 0.5
        if context.get("reasoning"):
            score += 0.1
        if context.get("scoring"):
            score += 0.1
        if context.get("prediction"):
            score += 0.05
        return min(score, 0.99)

    def _identify_uncertainties(self, context: Dict[str, Any]) -> List[str]:
        uncertainties = []
        if not context.get("reasoning"):
            uncertainties.append("Limited reasoning data")
        if not context.get("memory"):
            uncertainties.append("No memory context used")
        if context.get("scoring", {}).get("adjusted_score", 0) < 0.5:
            uncertainties.append("Low confidence score")
        return uncertainties
