"""Token Optimizer - Optimiza gastos de tokens."""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

class TokenOptimizer:
    """Optimiza uso de tokens Atria."""

    def __init__(self, atria_client):
        self.client = atria_client
        self.optimizations = []

    def optimize_request(self, prompt: str, category: str, estimated_tokens: int) -> dict:
        """Optimiza un request antes de enviarlo."""
        optimized = {
            "original_tokens": estimated_tokens,
            "optimizations": [],
            "category": category,
        }

        # Remove redundancies
        words = prompt.split()
        if len(words) > 500:
            optimized["original_tokens"] = len(words) + 50
            optimized["optimizations"].append("compressed_prompt")

        # Category-based token budget
        budgets = {
            "training": 3000,
            "enhancement": 800,
            "skills": 3000,
            "reasoning": 2000,
            "knowledge": 3000,
            "meta_learning": 3000,
        }
        budget = budgets.get(category, 1000)
        optimized["budget"] = budget

        if estimated_tokens > budget:
            optimized["optimizations"].append(f"token_budget_{budget}")

        return optimized

    def get_optimization_report(self) -> Dict[str, Any]:
        return {
            "total_optimizations": len(self.optimizations),
            "latest": self.optimizations[-1] if self.optimizations else None,
        }

