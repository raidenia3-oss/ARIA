import asyncio
import random
from typing import Any, Dict, List, Optional


class CreativityEngine:
    def __init__(self) -> None:
        self._used_combinations: List[str] = []
        self._concept_bank: List[str] = []
        self._constraints: List[str] = []

    def add_to_bank(self, concept: str) -> None:
        if concept not in self._concept_bank:
            self._concept_bank.append(concept)

    def add_constraint(self, constraint: str) -> None:
        self._constraints.append(constraint)

    async def generate_creative_idea(self, domain: str, num_ideas: int = 5) -> List[Dict[str, Any]]:
        ideas = []
        for i in range(num_ideas):
            idea = await self._generate_single(domain, i)
            ideas.append(idea)
        return ideas

    async def _generate_single(self, domain: str, index: int) -> Dict[str, Any]:
        if len(self._concept_bank) >= 2:
            c1, c2 = random.sample(self._concept_bank, 2)
            blended = f"{c1} + {c2}"
        else:
            blended = f"{domain}-concept-{index}"

        idea = {
            "id": f"idea_{domain}_{index}",
            "domain": domain,
            "blend": blended,
            "novelty": random.uniform(0.3, 0.95),
            "feasibility": random.uniform(0.2, 0.9),
            "constraints_applied": self._constraints[:3],
        }
        key = f"{blend}:{domain}"
        if key not in self._used_combinations:
            self._used_combinations.append(key)
        return idea

    def conceptual_blend(self, concepts: List[str]) -> Dict[str, Any]:
        if len(concepts) < 2:
            return {"blend": concepts[0] if concepts else "none", "novelty": 0.0}
        blend = " × ".join(concepts)
        novelty = min(len(concepts) / 10, 0.9)
        return {"blend": blend, "novelty": novelty, "concepts": concepts}

    def analogical_generation(self, source: str, target: str) -> Dict[str, Any]:
        mapping = {"source": source, "target": target, "mappings": []}
        source_words = source.lower().split()
        target_words = target.lower().split()
        for s in source_words:
            for t in target_words:
                if len(s) > 3 and len(t) > 3 and hash(s + t) % 3 == 0:
                    mapping["mappings"].append(
                        {"from": s, "to": t, "strength": random.uniform(0.1, 0.8)}
                    )
        return mapping

    def divergent_thinking(self, problem: str, num_solutions: int = 8) -> List[str]:
        solutions = []
        prefixes = [
            "Rethink",
            "Reframe",
            "Combine",
            "Distribute",
            "Automate",
            "Simplify",
            "Invert",
            "Amplify",
        ]
        for i in range(min(num_solutions, len(prefixes))):
            solutions.append(f"{prefixes[i]}: {problem}")
        return solutions
