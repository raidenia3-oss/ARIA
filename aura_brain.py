"""AURA Brain — unified brain with external APIs + small local model.

Architecture:
1. External APIs (Gemini, Groq, OpenRouter) = "experience" - fast, capable, cloud
2. Small local model (LoRA) = "reflection" - offline, personal, improves over time
3. Local rules = "instinct" - instant, no dependencies

Training strategy:
- Start with 50+ curated samples
- Capture good API responses as training data
- Fine-tune in stages: 50 -> 100 -> 200 -> 500 samples
- Use LoRA for efficient CPU training
- Quantize model to 4-bit for low RAM usage
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple


class AuraBrain:
    def __init__(self) -> None:
        self.model = None
        self.tokenizer = None
        self.model_loaded = False
        self.model_path = os.environ.get("AURA_LOCAL_MODEL_PATH", "fine-tuned-ame")
        self.base_model_cpu = os.environ.get("AURA_BASE_MODEL_CPU", "Qwen/Qwen2.5-0.5B-Instruct")
        self.base_model_gpu = os.environ.get("AURA_BASE_MODEL_GPU", "Qwen/Qwen2.5-1.5B-Instruct")
        self.training_data_path = "aura_merged_training.jsonl"
        self.min_training_samples = 50
        self.device = "cpu"
        self.backend = "none"
        self._detect_backend()
        self._training_status: Dict[str, Any] = {
            "trained": False,
            "samples": 0,
            "last_training": None,
            "backend": self.backend,
        }

    def _detect_backend(self) -> None:
        try:
            import torch
            if torch.cuda.is_available():
                self.device = "cuda"
                self.backend = "unsloth"
                return
        except Exception:
            pass
        try:
            import transformers
            import peft
            self.device = "cpu"
            self.backend = "transformers"
        except Exception:
            self.backend = "none"

    def load_model(self) -> bool:
        if self.model_loaded:
            return True
        try:
            if self.backend == "unsloth":
                return self._load_unsloth()
            elif self.backend == "transformers":
                return self._load_transformers()
            return False
        except Exception as e:
            print(f"[BRAIN] Failed to load model: {e}")
            self.model_loaded = False
            return False

    def _load_unsloth(self) -> bool:
        from unsloth import FastLanguageModel
        import torch
        base = self.base_model_gpu
        print(f"[BRAIN] Loading Unsloth model: {base}")
        model_name = base if not os.path.isdir(self.model_path) else self.model_path
        self.model, self.tokenizer = FastLanguageModel.from_pretrained(
            model_name=model_name,
            max_seq_length=2048,
            load_in_4bit=True,
        )
        if os.path.isdir(self.model_path) and model_name == base:
            self.model, self.tokenizer = FastLanguageModel.from_pretrained(
                model_name=self.model_path,
                max_seq_length=2048,
                load_in_4bit=True,
            )
        self.model_loaded = True
        print("[BRAIN] Unsloth model loaded.")
        return True

    def _load_transformers(self) -> bool:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel, PeftConfig
        import torch
        base = self.base_model_cpu
        print(f"[BRAIN] Loading Transformers model on CPU: {base}")
        self.tokenizer = AutoTokenizer.from_pretrained(base)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        dtype = torch.float32
        self.model = AutoModelForCausalLM.from_pretrained(
            base,
            torch_dtype=dtype,
            device_map="cpu",
            low_cpu_mem_usage=True,
        )
        if os.path.isdir(self.model_path):
            try:
                self.model = PeftModel.from_pretrained(self.model, self.model_path)
                print(f"[BRAIN] Loaded LoRA adapters from {self.model_path}")
            except Exception as e:
                print(f"[BRAIN] Could not load LoRA: {e}")
        self.model_loaded = True
        print("[BRAIN] Transformers model loaded on CPU.")
        return True

    def unload_model(self) -> None:
        if self.model is not None:
            try:
                del self.model
                del self.tokenizer
                import gc
                gc.collect()
                import torch
                torch.cuda.empty_cache()
            except Exception:
                pass
            self.model = None
            self.tokenizer = None
            self.model_loaded = False

    def generate(self, prompt: str, max_tokens: int = 256, temperature: float = 0.7) -> str:
        if not self.model_loaded or self.model is None:
            return ""
        try:
            import torch
            inputs = self.tokenizer(prompt, return_tensors="pt")
            if self.device == "cuda":
                inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    temperature=temperature,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id,
                )
            response = self.tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
            return response.strip()
        except Exception as e:
            print(f"[BRAIN] Generation failed: {e}")
            return ""

    def get_training_status(self) -> Dict[str, Any]:
        samples = 0
        try:
            if os.path.exists(self.training_data_path):
                with open(self.training_data_path, "r", encoding="utf-8") as f:
                    samples = sum(1 for _ in f)
        except Exception:
            pass
        self._training_status["samples"] = samples
        self._training_status["trained"] = samples >= self.min_training_samples
        self._training_status["backend"] = self.backend
        return dict(self._training_status)

    def add_training_sample(self, prompt: str, response: str, quality: str = "auto") -> bool:
        try:
            sample = {
                "text": prompt,
                "output": response,
                "quality": quality,
                "timestamp": time.time(),
            }
            with open(self.training_data_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")
            return True
        except Exception:
            return False

    def needs_training(self) -> bool:
        status = self.get_training_status()
        return not status["trained"]

    def get_status(self) -> Dict[str, Any]:
        return {
            "model_loaded": self.model_loaded,
            "model_path": self.model_path,
            "base_model_cpu": self.base_model_cpu,
            "base_model_gpu": self.base_model_gpu,
            "backend": self.backend,
            "device": self.device,
            "training": self.get_training_status(),
            "needs_training": self.needs_training(),
        }


class AuraBrainAPI:
    """External API brain — fast, capable, cloud-based with intelligent orchestration."""
    def __init__(self) -> None:
        self.providers = ["gemini", "groq", "openrouter", "hf"]
        self._provider_status: Dict[str, bool] = {}
        self._last_latency: Dict[str, float] = {}
        self._failure_count: Dict[str, int] = {}
        self._circuit_breaker: Dict[str, float] = {}
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 3600

    def is_available(self, provider: str) -> bool:
        if provider not in self.providers:
            return False
        now = time.time()
        if provider in self._circuit_breaker:
            if now - self._circuit_breaker[provider] < 30:
                return False
            del self._circuit_breaker[provider]
        return self._provider_status.get(provider, False)

    def mark_success(self, provider: str, latency: float) -> None:
        self._provider_status[provider] = True
        self._last_latency[provider] = latency
        self._failure_count[provider] = 0

    def mark_failure(self, provider: str) -> None:
        self._failure_count[provider] = self._failure_count.get(provider, 0) + 1
        if self._failure_count[provider] >= 3:
            self._circuit_breaker[provider] = time.time()
            self._provider_status[provider] = False

    def get_best_provider(self) -> Optional[str]:
        available = [p for p in self.providers if self.is_available(p)]
        if not available:
            return None
        return min(available, key=lambda p: self._last_latency.get(p, 9999))

    def get_cache_key(self, message: str, context: str = "") -> str:
        return f"{context}:{message.lower().strip()[:100]}"

    def get_cached(self, key: str) -> Optional[Dict[str, Any]]:
        entry = self._cache.get(key)
        if not entry:
            return None
        if time.time() - entry["timestamp"] > self._cache_ttl:
            del self._cache[key]
            return None
        return entry["response"]

    def set_cache(self, key: str, response: Dict[str, Any]) -> None:
        self._cache[key] = {
            "response": response,
            "timestamp": time.time(),
        }
        if len(self._cache) > 1000:
            oldest = min(self._cache, key=lambda k: self._cache[k]["timestamp"])
            del self._cache[oldest]

    def get_status(self) -> Dict[str, Any]:
        return {
            "providers": {p: self.is_available(p) for p in self.providers},
            "best": self.get_best_provider(),
            "latencies": dict(self._last_latency),
            "cache_size": len(self._cache),
        }
