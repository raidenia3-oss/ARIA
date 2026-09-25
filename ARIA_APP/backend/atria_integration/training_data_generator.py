"""Training Data Generator - Genera datasets para fine-tuning."""
import asyncio
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional


class TrainingDataGenerator:
    """Genera datasets de entrenamiento para Ollama."""

    def __init__(self, atria_client):
        self.client = atria_client
        self.dataset = []
        self.output_dir = Path("ARIA_APP/data/training/atria_generated")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.generated_count = 0

    async def generate_domain_dataset(
        self, domain: str, num_examples: int = 20, difficulty: str = "mixed"
    ) -> List[dict]:
        prompt = (
            "Genera " + str(num_examples) + " ejemplos para " + domain
            + ". Dificultad: " + difficulty
            + ". Retorna JSON array con question, answer, explanation."
        )
        result = await self.client.request(prompt, max_tokens=3000, category="training")
        if result.get("success"):
            try:
                response_text = result["response"]
                import re
                match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", response_text, re.DOTALL)
                if match:
                    response_text = match.group(1)
                examples = json.loads(response_text)
                validated = [ex for ex in examples if "question" in ex and "answer" in ex]
                filename = domain + "_" + difficulty + "_" + str(len(validated)) + "ex.jsonl"
                filepath = self.output_dir / filename
                with open(filepath, "w", encoding="utf-8") as f:
                    for ex in validated:
                        f.write(json.dumps(ex, ensure_ascii=False) + "\n")
                self.generated_count += len(validated)
                return validated
            except json.JSONDecodeError:
                return []
        return []

    async def generate_comprehensive_dataset(self, domains=None, examples_per_domain=20) -> int:
        if not domains:
            domains = ["programming", "logic", "writing", "math", "science"]
        total = 0
        for d in domains:
            ex = await self.generate_domain_dataset(d, num_examples=examples_per_domain)
            total += len(ex)
        return total

    async def create_lora_finetune_dataset(self) -> int:
        lora = []
        for f in self.output_dir.glob("*.jsonl"):
            if f.name.startswith("lora_final"): continue
            with open(f, encoding="utf-8") as fh:
                for line in fh:
                    ex = json.loads(line)
                    lora.append({
                        "instruction": ex.get("question", ""),
                        "output": ex.get("answer", ""),
                    })
        final = self.output_dir / "lora_final_dataset.jsonl"
        with open(final, "w", encoding="utf-8") as f:
            for item in lora:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        return len(lora)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "generated_count": self.generated_count,
            "output_dir": str(self.output_dir),
        }

