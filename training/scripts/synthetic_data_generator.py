"""
Synthetic Data Generator for AURA Small Model Training.

Strategy:
- Use external APIs (Gemini -> Groq -> OpenRouter) to generate high-quality
  Q/A pairs for the small model domain (AURA assistant, system control, reasoning, etc.).
- Avoid expensive CPU training by generating curated datasets instead of
  training from scratch on raw data.
- Output: JSONL files ready for QLoRA / lightweight fine-tuning.
"""

from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

try:
    from ame_backend.src.services.ai_engine import AIEngine
except Exception:  # pragma: no cover
    AIEngine = None  # type: ignore

TOPICS = [
    "AURA setup and configuration on Windows and Linux",
    "Ollama local model setup and management",
    "Python scripting and automation for system tasks",
    "PowerShell and Bash system administration",
    "Discord bot creation with Ruby or Python",
    "Hugging Face model download and local deployment",
    "Fine-tuning small language models with QLoRA on CPU",
    "API integration: Gemini, Groq, OpenRouter for AI apps",
    "Voice commands and speech-to-text with Whisper/Vosk",
    "Web scraping and OSINT collection for training data",
    "Memory management and persistent user profiles",
    "Multi-agent orchestration and task delegation",
    "RAG and knowledge retrieval from local documents",
    "Cybersecurity scanning with Shodan and Venice",
    "Autonomous self-improvement and code evolution loops",
    "Frontend integration with Next.js and API routes",
    "Docker and Railway deployment for AI services",
    "Error handling, logging, and observability in AI pipelines",
]


@dataclass
class GenerationConfig:
    topic: str
    num_samples: int = 20
    max_new_tokens: int = 512
    temperature: float = 0.7
    output_path: str = "training/data/synthetic_generated.jsonl"


class SyntheticDataGenerator:
    def __init__(self, preferred_provider: Optional[str] = None) -> None:
        self.engine = AIEngine() if AIEngine else None
        self.preferred_provider = preferred_provider or os.getenv("SYNTH_PROVIDER", "auto")

    def generate_topic(self, cfg: GenerationConfig) -> List[Dict[str, str]]:
        system_prompt = (
            "You are AURA's training data generator. "
            "Generate concise, high-quality Q/A pairs for a small local assistant. "
            f"Topic: {cfg.topic}. "
            "Output ONLY a JSON array of objects with keys: 'text' (user prompt) and 'output' (assistant answer). "
            "No markdown, no extra text."
        )
        user_prompt = f"Generate {cfg.num_samples} training examples about: {cfg.topic}"

        result = self._call_ai(system_prompt, user_prompt)
        if not result or "text" not in result:
            return []

        return self._parse_json_array(result["text"])

    def generate_batch(self, topics: Optional[List[str]] = None, samples_per_topic: int = 10) -> str:
        topics = topics or TOPICS
        output_path = "training/data/synthetic_generated.jsonl"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        total_written = 0
        with open(output_path, "w", encoding="utf-8") as f:
            for topic in topics:
                print(f"[synth] Generating data for: {topic}")
                cfg = GenerationConfig(topic=topic, num_samples=samples_per_topic)
                pairs = self.generate_topic(cfg)
                for pair in pairs:
                    f.write(json.dumps(pair, ensure_ascii=False) + "\n")
                    total_written += 1
                time.sleep(1)  # avoid rate limits

        print(f"[synth] Done. Generated {total_written} samples -> {output_path}")
        return output_path

    def _call_ai(self, system_prompt: str, user_prompt: str) -> Optional[Dict[str, Any]]:
        if not self.engine:
            return None
        context = system_prompt
        prompt = user_prompt
        try:
            return self.engine.chat(prompt=prompt, context=context)
        except Exception as e:
            print(f"[synth] AI call failed: {e}")
            return None

    def _parse_json_array(self, text: str) -> List[Dict[str, str]]:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```", 1)[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict) and "text" in item and "output" in item]
        except json.JSONDecodeError:
            pass
        return []


def main() -> int:
    generator = SyntheticDataGenerator()
    path = generator.generate_batch(samples_per_topic=15)
    print(f"Saved synthetic dataset to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
