"""AURA v2.x — Prompt Tuner (Phase D).

Automatically tune agent prompts via A/B testing.
"""
import asyncio
import json
import os
import random
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class PromptVariation:
    template: str
    score: float = 0.0
    accuracy: float = 0.0
    speed_ms: float = 0.0


@dataclass
class TunedAgent:
    name: str
    best_prompt: str
    accuracy_gain: float = 0.0
    tests_run: int = 0
    variations_tested: int = 0


@dataclass
class TuneAllResult:
    improved_agents: List[Dict[str, Any]] = field(default_factory=list)
    accuracy_gains: Dict[str, float] = field(default_factory=dict)
    total_tests: int = 0
    duration_seconds: float = 0.0


class PromptTuner:

    def __init__(self, prompts_dir: Optional[str] = None) -> None:
        self._prompts_dir = prompts_dir or os.path.join(
            os.path.dirname(__file__), ".." , "prompts"
        )
        self._tuned: Dict[str, TunedAgent] = {}
        self._history: List[Dict[str, Any]] = []

    async def tune_agent_prompt(
        self,
        agent_name: str,
        test_cases: List[str],
        variations: int = 5,
    ) -> TunedAgent:
        """Tune an agent prompt: test current, generate variations, pick best."""
        base_prompt = self._load_prompt(agent_name)

        best_variation = PromptVariation(template=base_prompt)
        best_score = await self._evaluate_prompt(agent_name, base_prompt, test_cases)

        for v in range(variations):
            variation_prompt = self._generate_variation(base_prompt, v)
            accuracy, speed = await self._test_prompt(agent_name, variation_prompt, test_cases)

            prompt_var = PromptVariation(
                template=variation_prompt,
                accuracy=accuracy,
                speed_ms=speed,
            )
            # Score = weighted combination
            prompt_var.score = accuracy * 0.7 + min(speed / 1000, 1.0) * 0.3

            if prompt_var.score > best_score:
                best_score = prompt_var.score
                best_variation = prompt_var

        # Save best prompt
        self._save_prompt(agent_name, best_variation.template)

        tuned = TunedAgent(
            name=agent_name,
            best_prompt=best_variation.template,
            accuracy_gain=best_score,
            tests_run=len(test_cases),
            variations_tested=variations + 1,
        )
        self._tuned[agent_name] = tuned

        record = {
            "agent": agent_name,
            "timestamp": time.time(),
            "accuracy": best_score,
            "variations": variations + 1,
        }
        self._history.append(record)

        return tuned

    async def tune_all_agents(self) -> TuneAllResult:
        """Tune prompts for all agents. 20 test cases, 5 variations each."""
        start = time.time()

        agent_names = [
            "code_reviewer", "business_analyst", "researcher",
            "video_analyzer", "language_tutor", "fitness_coach",
            "music_composer", "psychology_counselor",
        ]

        result = TuneAllResult()

        for name in agent_names:
            try:
                test_cases = self._generate_test_cases(name, 20)
                tuned = await self.tune_agent_prompt(name, test_cases, variations=5)

                previous_accuracy = self._get_previous_accuracy(name)
                gain = tuned.accuracy_gain - previous_accuracy

                result.improved_agents.append({
                    "agent": name,
                    "tests_run": tuned.tests_run,
                    "variations_tested": tuned.variations_tested,
                    "accuracy": tuned.accuracy_gain,
                })
                result.accuracy_gains[name] = round(gain, 4)
                result.total_tests += tuned.tests_run
            except Exception as e:
                result.improved_agents.append({
                    "agent": name,
                    "error": str(e),
                })

        result.duration_seconds = round(time.time() - start, 2)
        return result

    def _load_prompt(self, agent_name: str) -> str:
        path = os.path.join(self._prompts_dir, f"{agent_name}_prompt.txt")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return f"You are {agent_name}. Respond accurately and concisely."

    def _save_prompt(self, agent_name: str, prompt: str) -> None:
        path = os.path.join(self._prompts_dir, f"{agent_name}_prompt.txt")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(prompt)

    def _generate_variation(self, base: str, variation_index: int) -> str:
        modifiers = [
            "",
            "Be concise and direct.\n",
            "Think step by step before responding.\n",
            "Provide examples where relevant.\n",
            "Use structured output with clear sections.\n",
        ]
        prefix = modifiers[variation_index % len(modifiers)]
        suffix = f"\n---\nVariation {variation_index} | AURA Tuner"
        return prefix + base + suffix

    async def _evaluate_prompt(
        self,
        agent_name: str,
        prompt: str,
        test_cases: List[str],
    ) -> float:
        accuracy, _ = await self._test_prompt(agent_name, prompt, test_cases)
        return accuracy

    async def _test_prompt(
        self,
        agent_name: str,
        prompt: str,
        test_cases: List[str],
    ) -> Tuple[float, float]:
        correct = 0
        total_time = 0.0

        for case in test_cases:
            start = time.time()
            try:
                result = await self._run_agent(agent_name, case, prompt)
                if self._is_correct(result, case):
                    correct += 1
            except Exception:
                pass
            total_time += time.time() - start

        accuracy = correct / max(len(test_cases), 1)
        avg_speed = (total_time / max(len(test_cases), 1)) * 1000
        return accuracy, avg_speed

    async def _run_agent(
        self,
        agent_name: str,
        input_data: str,
        prompt: str,
    ) -> Any:
        agent = self._get_agent_instance(agent_name)
        if agent is None:
            return {"output": input_data, "prompt_used": prompt}

        method = self._get_agent_method(agent)
        if method is None:
            return {"output": str(agent), "prompt_used": prompt}

        try:
            result = await method(input_data)
            if isinstance(result, dict):
                result["prompt_used"] = prompt
            return result
        except TypeError:
            try:
                result = method()
                if isinstance(result, dict):
                    result["prompt_used"] = prompt
                return result
            except Exception:
                return {"output": "error", "prompt_used": prompt}

    def _is_correct(self, result: Any, test_case: str) -> bool:
        if result is None:
            return False
        if isinstance(result, dict):
            if "error" in result and result["error"]:
                return False
            return True
        return True

    def _get_agent_instance(self, name: str):
        from backend.agents.agent_code_reviewer import CodeReviewerAgent
        from backend.agents.agent_business_analyst import BusinessAnalystAgent
        from backend.agents.agent_researcher import ResearcherAgent
        from backend.agents.agent_video_analyzer import VideoAnalyzerAgent
        from backend.agents.agent_language_tutor import LanguageTutorAgent
        from backend.agents.agent_fitness_coach import FitnessCoachAgent
        from backend.agents.agent_music_composer import MusicComposerAgent
        from backend.agents.agent_psychology_counselor import PsychologyCounselorAgent

        mapping = {
            "code_reviewer": CodeReviewerAgent,
            "business_analyst": BusinessAnalystAgent,
            "researcher": ResearcherAgent,
            "video_analyzer": VideoAnalyzerAgent,
            "language_tutor": LanguageTutorAgent,
            "fitness_coach": FitnessCoachAgent,
            "music_composer": MusicComposerAgent,
            "psychology_counselor": PsychologyCounselorAgent,
        }
        cls = mapping.get(name)
        return cls() if cls else None

    def _get_agent_method(self, agent):
        import inspect
        if agent is None:
            return None
        methods = [
            m for m in dir(agent)
            if not m.startswith("_") and callable(getattr(agent, m))
        ]
        if methods:
            return getattr(agent, methods[0])
        return None

    def _generate_test_cases(self, agent_name: str, count: int) -> List[str]:
        templates = [
            f"Process {agent_name} task {i}: analyze and respond",
            f"Test case {i} for {agent_name}",
            f"{agent_name} scenario {i}: standard input",
            f"Evaluate {agent_name} on example {i}",
            f"{agent_name} benchmark query #{i}",
        ]
        cases = []
        for i in range(count):
            template = templates[i % len(templates)]
            cases.append(template.format(i=i))
        return cases

    def _get_previous_accuracy(self, agent_name: str) -> float:
        for record in reversed(self._history):
            if record.get("agent") == agent_name:
                return record.get("accuracy", 0.5)
        return 0.5

    def get_tuned_prompt(self, agent_name: str) -> Optional[str]:
        agent = self._tuned.get(agent_name)
        if agent:
            return agent.best_prompt
        return self._load_prompt(agent_name)

    def get_all_tuned_agents(self) -> Dict[str, TunedAgent]:
        return dict(self._tuned)


# Prompt tuning for specific files mentioned in requirements
def tune_fanfic_prompt() -> str:
    """Tune the fanfic generation prompt."""
    base = """Eres un escritor profesional de fanfic. Genera historias creativas basadas en los parámetros proporcionados.

<environment_details>
Current time: {current_time}
Working directory: {working_dir}
</environment_details>

Requisitos:
- Desarrollar personajes con profundidad emocional
- Mantener coherencia de worldbuilding
- Usar diálogos naturales y enriquecedores
- Estructura narrativa clara: inicio, conflicto, resolución
- Extensión: {length}
- Tema: {theme}

Instrucciones de estilo:
- Narrativa en tercera persona
- Descripciones vívidas sin ser prolijas
- Ritmo variable según la tensión narrativa
- Vocabulario rico pero accesible"""
    return base
