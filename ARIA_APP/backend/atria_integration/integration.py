"""ARIA Atria Integration - Orquestador principal."""
import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional

from backend.atria_integration.atria_client import AtriaClient
from backend.atria_integration.token_optimizer import TokenOptimizer
from backend.atria_integration.token_monitor import TokenMonitor
from backend.atria_integration.training_data_generator import TrainingDataGenerator
from backend.atria_integration.response_enhancer import ResponseEnhancer
from backend.atria_integration.skill_synthesizer import SkillSynthesizer
from backend.atria_integration.reasoning_resolver import ReasoningResolver
from backend.atria_integration.knowledge_integrator import KnowledgeIntegrator
from backend.atria_integration.meta_learner import MetaLearner


class AURAAtriaIntegration:
    """Orquestador principal de integracion Atria.

    Ollama = Produccion (sin costo)
    Atria = Inteligencia estrategica (~4M tokens/mes)
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.client = AtriaClient(api_key=api_key)
        self.optimizer = TokenOptimizer(self.client)
        self.monitor = TokenMonitor(self.client)
        self.training = TrainingDataGenerator(self.client)
        self.enhancer = ResponseEnhancer(self.client)
        self.skills = SkillSynthesizer(self.client)
        self.reasoning = ReasoningResolver(self.client)
        self.knowledge = KnowledgeIntegrator(self.client)
        self.meta = MetaLearner(self.client)
        self.active = self.client.available

    async def train(self, domains=None, examples_per_domain=20) -> int:
        if not self.active: return 0
        return await self.training.generate_comprehensive_dataset(
            domains=domains, examples_per_domain=examples_per_domain
        )

    async def enhance(self, response: str, question: str) -> dict:
        if not self.active: return {"status": "no_api"}
        result = await self.enhancer.enhance_response(response, question)
        await asyncio.sleep(3)
        return result

    async def synthesize_skills(self, count=10) -> int:
        if not self.active: return 0
        return await self.skills.synthesize_skills(count)

    async def solve(self, problem: str, context=None) -> dict:
        if not self.active: return {"status": "no_api"}
        return await self.reasoning.resolve(problem, context)

    async def integrate_knowledge(self, source_type: str, source_ref: str) -> dict:
        if not self.active: return {"status": "no_api"}
        return await self.knowledge.integrate_source(source_type, source_ref)

    async def self_improve(self) -> dict:
        if not self.active: return {"status": "no_api"}
        return await self.meta.self_improve()

    def dashboard(self) -> Dict[str, Any]:
        return self.monitor.get_dashboard()

    def should_continue(self) -> bool:
        return self.monitor.should_continue()

    async def close(self):
        await self.client.close()


async def main():
    integration = AURAAtriaIntegration()
    print(f"Atria available: {integration.active}")
    if integration.active:
        print(f"Dashboard: {json.dumps(integration.dashboard(), indent=2, default=str)}")
    await integration.close()

if __name__ == "__main__":
    asyncio.run(main())

