"""Explanation Generator — Genera explicaciones"""

from typing import Dict, Any


class ExplanationGenerator:
    """Genera explicaciones de decisiones"""

    def __init__(self):
        self.explanations = []

    async def explain(self, decision: Dict) -> str:
        """Explica una decisión"""
        explanation = f"Decisión: {decision.get('action', 'unknown')}"
        self.explanations.append(explanation)
        return explanation
