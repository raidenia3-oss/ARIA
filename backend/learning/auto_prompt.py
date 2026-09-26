# -*- coding: utf-8 -*-
"""AURA OS — Auto Prompt Generator.

Uses genetic algorithm to evolve prompts for research,
automation, and agent tasks based on performance history.
"""
from __future__ import annotations

import copy
import json
import logging
import random
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("AURA.AutoPrompt")


@dataclass
class PromptGenome:
    genome_id: str
    template: str
    fitness: float = 0.0
    generation: int = 0
    uses: int = 0
    successes: int = 0
    task_type: str = ""
    created_at: float = field(default_factory=time.time)

    @property
    def rate(self) -> float:
        return self.successes / max(1, self.uses)


class AutoPromptGenerator:
    """Evolves prompts using genetic algorithm principles."""

    POPULATION_SIZE = 20
    MUTATION_RATE = 0.15
    GENERATIONS = 5
    STORAGE_FILE = Path("data/learning/prompts.json")

    def __init__(self) -> None:
        self.population: List[PromptGenome] = []
        self.history: List[Dict[str, Any]] = []
        self.STORAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def generate_prompt(self, task_type: str, context: Dict[str, Any] = None) -> PromptGenome:
        context = context or {}
        candidates = [p for p in self.population if p.task_type == task_type]
        if candidates:
            candidates.sort(key=lambda p: p.fitness, reverse=True)
            parent = candidates[0]
            genome = self._mutate(parent, context)
        else:
            template = self._base_template(task_type, context)
            genome = PromptGenome(
                genome_id=f"PG-{int(time.time())}",
                template=template,
                generation=0,
                task_type=task_type,
            )
        self.population.append(genome)
        self._save()
        return genome

    def evaluate_prompt(self, genome_id: str, success: bool, score: float = 0.5) -> None:
        for genome in self.population:
            if genome.genome_id == genome_id:
                genome.uses += 1
                if success:
                    genome.successes += 1
                genome.fitness = genome.rate * 0.7 + score * 0.3
                self.history.append({
                    "genome_id": genome_id,
                    "success": success,
                    "score": score,
                    "timestamp": time.time(),
                })
                break
        self._trim_population()
        self._save()

    def evolve(self, task_type: str) -> PromptGenome:
        candidates = [p for p in self.population if p.task_type == task_type]
        if len(candidates) < 2:
            return self.generate_prompt(task_type)
        parents = sorted(candidates, key=lambda p: p.fitness, reverse=True)[:self.POPULATION_SIZE // 2]
        new_genomes: List[PromptGenome] = []
        for _ in range(self.GENERATIONS):
            parent_a = random.choice(parents)
            parent_b = random.choice(parents)
            child = self._crossover(parent_a, parent_b)
            child = self._mutate(child, {})
            child.generation += 1
            new_genomes.append(child)
        self.population.extend(new_genomes)
        self._trim_population()
        self._save()
        best = max(new_genomes, key=lambda g: g.fitness)
        return best

    def get_best_prompt(self, task_type: str) -> Optional[str]:
        candidates = [p for p in self.population if p.task_type == task_type]
        if not candidates:
            return None
        candidates.sort(key=lambda p: p.fitness, reverse=True)
        return candidates[0].template

    def get_stats(self) -> Dict[str, Any]:
        total = len(self.population)
        if not total:
            return {"total_prompts": 0}
        by_type: Dict[str, int] = {}
        for p in self.population:
            ptype = p.template.split(":")[0]
            by_type[ptype] = by_type.get(ptype, 0) + 1
        avg_fitness = sum(p.fitness for p in self.population) / total
        return {
            "total_prompts": total,
            "by_type": by_type,
            "avg_fitness": round(avg_fitness, 4),
            "best_fitness": round(max(p.fitness for p in self.population), 4),
            "total_uses": sum(p.uses for p in self.population),
            "total_successes": sum(p.successes for p in self.population),
            "generations": max(p.generation for p in self.population),
        }

    def _base_template(self, task_type: str, context: Dict[str, Any]) -> str:
        templates = {
            "research": "Investigate {topic} with focus on {aspects}. Provide structured analysis.",
            "automation": "Automate {task} with steps: {steps}. Handle errors gracefully.",
            "analysis": "Analyze {data} for {criteria}. Report findings concisely.",
            "coding": "Write {language} code for {purpose}. Include error handling.",
        }
        base = templates.get(task_type, "Process {task} with context: {details}")
        return base.format(
            topic=context.get("topic", "the subject"),
            aspects=context.get("aspects", "key dimensions"),
            task=context.get("task", "the task"),
            steps=context.get("steps", "sequential"),
            data=context.get("data", "the data"),
            criteria=context.get("criteria", "relevance"),
            language=context.get("language", "Python"),
            purpose=context.get("purpose", "the goal"),
            details=json.dumps(context)[:200],
        )

    def _mutate(self, genome: PromptGenome, context: Dict[str, Any]) -> PromptGenome:
        mutated = copy.deepcopy(genome)
        mutated.genome_id = f"PG-{int(time.time())}-{random.randint(0, 9999)}"
        mutated.generation = genome.generation + 1
        template = mutated.template
        if random.random() < self.MUTATION_RATE:
            words = template.split()
            if len(words) > 2:
                idx = random.randint(0, len(words) - 1)
                words[idx] = f"<v{random.randint(1, 5)}>"
                mutated.template = " ".join(words)
        if random.random() < self.MUTATION_RATE:
            prefix = ["[FOCUS]", "[DEEP]", "[QUICK]", "[STRUCTURED]"]
            mutated.template = f"{random.choice(prefix)} {mutated.template}"
        return mutated

    def _crossover(self, a: PromptGenome, b: PromptGenome) -> PromptGenome:
        parts_a = a.template.split()
        parts_b = b.template.split()
        if not parts_a or not parts_b:
            return copy.deepcopy(a)
        midpoint = min(len(parts_a), len(parts_b)) // 2
        child_template = " ".join(parts_a[:midpoint] + parts_b[midpoint:])
        return PromptGenome(
            genome_id=f"PG-{int(time.time())}",
            template=child_template,
            fitness=0.0,
            generation=max(a.generation, b.generation) + 1,
            task_type=a.task_type or b.task_type,
        )

    def _trim_population(self) -> None:
        if len(self.population) > self.POPULATION_SIZE * 3:
            self.population.sort(key=lambda p: p.fitness, reverse=True)
            self.population = self.population[:self.POPULATION_SIZE * 2]

    def _load(self) -> None:
        try:
            if self.STORAGE_FILE.exists():
                data = json.loads(self.STORAGE_FILE.read_text())
                for item in data.get("population", []):
                    self.population.append(PromptGenome(
                        genome_id=item["genome_id"],
                        template=item["template"],
                        fitness=item.get("fitness", 0.0),
                        generation=item.get("generation", 0),
                        uses=item.get("uses", 0),
                        successes=item.get("successes", 0),
                        task_type=item.get("task_type", ""),
                        created_at=item.get("created_at", time.time()),
                    ))
        except Exception:
            pass

    def _save(self) -> None:
        try:
            data = {
                "population": [
                    {
                        "genome_id": p.genome_id,
                        "template": p.template,
                        "fitness": p.fitness,
                        "generation": p.generation,
                        "uses": p.uses,
                        "successes": p.successes,
                        "task_type": p.task_type,
                        "created_at": p.created_at,
                    }
                    for p in self.population
                ]
            }
            self.STORAGE_FILE.write_text(json.dumps(data, indent=2, default=str))
        except Exception:
            pass


auto_prompt_generator = AutoPromptGenerator()
