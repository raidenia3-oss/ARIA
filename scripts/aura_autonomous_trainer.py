#!/usr/bin/env python3
"""
AURA Autonomous Trainer — Entrenamiento autónomo con búsqueda web y auto-mejora.

Pipeline completo de Auto-ML:
  1. Collect: Busca en internet datos de entrenamiento (web scraping)
  2. Prepare: Tokeniza, limpia, particiona train/eval
  3. Train:   Fine-tuning con LoRA + cuantización 4-bit (memoria optimizada)
  4. Evaluate: Autoevalúa con métricas (loss, perplexity, exactitud Q&A)
  5. Improve: Si la evaluación es mala, recolecta más datos y reentrena (loop)
  6. Export:  Guarda modelo + metadata + metrics

Módulos (extensibles):
  - data_collectors/*.py  — plugins de colección (web, api, file, wiki)
  - evaluators/*.py       — plugins de evaluación
  - optimizers/*.py       — plugins de optimización

Uso:
  # Entrenamiento autónomo completo
  python scripts/aura_autonomous_trainer.py --auto

  # Con búsqueda web activada
  python scripts/aura_autonomous_trainer.py --auto --web-search --topics "Python,AI"

  # Solo evaluar modelo existente
  python scripts/aura_autonomous_trainer.py --evaluate models/qwen-1.5b

  # Ver métricas del entrenamiento anterior
  python scripts/aura_autonomous_trainer.py --metrics
"""

from __future__ import annotations

import os
import sys
import json
import time
import math
import logging
import argparse
import importlib
import subprocess
import random
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from functools import partial

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("AuraAutonomousTrainer")

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_BASE = REPO_ROOT / "fine-tuned-ame"
METRICS_FILE = OUTPUT_BASE / "training_metrics.json"


@dataclass
class TrainingConfig:
    """Configuración del entrenamiento."""
    model_id: str = "Qwen/Qwen2.5-1.5B"
    model_path: str = "models/qwen-1.5b"
    output_dir: str = "fine-tuned-ame"
    epochs: int = 5
    lr: float = 8e-5
    batch_size: int = 2
    max_length: int = 512
    use_lora: bool = True
    use_4bit: bool = False
    use_gradient_checkpointing: bool = True
    lora_r: int = 16
    lora_alpha: int = 64
    lora_dropout: float = 0.05
    eval_steps: int = 50
    save_steps: int = 100
    warmup_steps: int = 20
    weight_decay: float = 0.01
    auto_collect: bool = False
    auto_improve: bool = False
    web_search: bool = False
    use_ui_data: bool = True
    ui_data_file: str = "training-data-ui.jsonl"
    use_reasoning_data: bool = True
    reasoning_data_file: str = "training-data-reasoning.jsonl"
    use_task_data: bool = True
    task_data_file: str = "training-data-tasks.jsonl"
    use_search_data: bool = True
    search_data_file: str = "training-data-search.jsonl"
    use_device_data: bool = True
    device_data_file: str = "training-data-device.jsonl"
    use_voice_data: bool = True
    voice_data_file: str = "training-data-voice.jsonl"
    use_system_data: bool = True
    system_data_file: str = "training-data-system.jsonl"
    use_vision_data: bool = True
    vision_data_file: str = "training-data-vision.jsonl"
    use_screen_data: bool = True
    screen_data_file: str = "training-data-screen.jsonl"
    use_persuasion_data: bool = True
    persuasion_data_file: str = "training-data-persuasion.jsonl"
    use_emotional_data: bool = True
    emotional_data_file: str = "training-data-emotional.jsonl"
    use_evolved_data: bool = True
    evolved_data_file: str = "training-data-evolved.jsonl"
    use_self_evolved_data: bool = True
    self_evolved_data_file: str = "training-data-self_evolved.jsonl"
    topics: List[str] = field(default_factory=lambda: ["AURA AI", "LLM fine-tuning", "HTML CSS JavaScript UI design"])
    quality_threshold: float = 0.80
    max_collections: int = 2
    num_search_results: int = 8
    samples_per_page: int = 5


class DataCollector:
    """Recolector de datos con múltiples fuentes y web scraping."""

    def __init__(self, config: TrainingConfig):
        self.config = config

    def _load_base_items(self, path: Path = REPO_ROOT / "training-data.jsonl") -> List[Dict]:
        items = []
        if not path.exists():
            return items
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        items.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return items

    def collect(self) -> Tuple[str, int]:
        """Recolecta datos combinando fuentes locales + web + UI code + razonamiento + tareas + busqueda + dispositivo."""
        merged: List[Dict] = []

        # 1. Datos locales existentes (Q&A)
        existing = REPO_ROOT / "training-data.jsonl"
        if existing.exists():
            with open(existing, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            merged.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            logger.info(f"Local Q&A data: {len(merged)} samples")

        # 2. Datos de UI (código HTML/CSS/JS de apps existentes)
        if self.config.use_ui_data:
            ui_data_file = REPO_ROOT / self.config.ui_data_file
            if not ui_data_file.exists():
                logger.info("UI data not found, generating from existing HTML files...")
                try:
                    from aura_ui_collector import collect_ui_data
                    collect_ui_data(
                        output_file=self.config.ui_data_file,
                        max_files=15,
                        max_pairs_per_file=15,
                    )
                except Exception as e:
                    logger.warning(f"UI collection failed: {e}")

            if ui_data_file.exists():
                ui_count = 0
                with open(ui_data_file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                merged.append(json.loads(line))
                                ui_count += 1
                            except json.JSONDecodeError:
                                continue
                logger.info(f"UI code data: {ui_count} samples")

        # 3. Búsqueda web (si está habilitada)
        if self.config.web_search:
            from aura_web_collector import KnowledgeCollector
            collector = KnowledgeCollector(
                topics=self.config.topics,
                output_file="training-data-web.jsonl",
                num_results=self.config.num_search_results,
                samples_per_page=self.config.samples_per_page,
            )
            web_qa = collector.collect_from_topics()
            merged.extend(web_qa)
            logger.info(f"Web data: {len(web_qa)} samples")

        # 4. Razonamiento avanzado
        if self.config.use_reasoning_data:
            reasoning_file = REPO_ROOT / self.config.reasoning_data_file
            if not reasoning_file.exists():
                logger.info("Generating reasoning data...")
                try:
                    from reasoning_trainer import ReasoningTrainer
                    trainer = ReasoningTrainer()
                    items = trainer.generate_batch(count=50)
                    trainer.save_to_jsonl(items, reasoning_file)
                except Exception as e:
                    logger.warning(f"Reasoning data generation failed: {e}")
            if reasoning_file.exists():
                with open(reasoning_file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                merged.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
                logger.info(f"Reasoning data loaded")

        # 5. Tareas simuladas avanzadas
        if self.config.use_task_data:
            task_file = REPO_ROOT / self.config.task_data_file
            if not task_file.exists():
                logger.info("Generating task simulation data...")
                try:
                    from task_simulation_engine import TaskSimulationEngine
                    engine = TaskSimulationEngine()
                    tasks = engine.generate_batch(count=50)
                    engine.save_to_jsonl(tasks, task_file)
                except Exception as e:
                    logger.warning(f"Task simulation data generation failed: {e}")
            if task_file.exists():
                with open(task_file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                merged.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
                logger.info(f"Task simulation data loaded")

        # 6. Búsqueda avanzada estructurada
        if self.config.use_search_data:
            search_file = REPO_ROOT / self.config.search_data_file
            if not search_file.exists():
                logger.info("Generating advanced search data...")
                try:
                    from advanced_search_engine import AdvancedSearchEngine
                    engine = AdvancedSearchEngine()
                    tasks = engine.generate_batch(count=50)
                    engine.save_to_jsonl(tasks, search_file)
                except Exception as e:
                    logger.warning(f"Advanced search data generation failed: {e}")
            if search_file.exists():
                with open(search_file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                merged.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
                logger.info(f"Advanced search data loaded")

        # 7. Datos de apps del dispositivo
        if self.config.use_device_data:
            device_file = REPO_ROOT / self.config.device_data_file
            if not device_file.exists():
                logger.info("Generating device app connector data...")
                try:
                    from device_app_connector import DeviceAppConnector
                    connector = DeviceAppConnector()
                    items = connector.generate_batch(count=50)
                    connector.save_to_jsonl(items, device_file)
                except Exception as e:
                    logger.warning(f"Device app data generation failed: {e}")
            if device_file.exists():
                with open(device_file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                merged.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
                logger.info(f"Device app data loaded")

        # 8. Datos de voz y comandos por voz
        if self.config.use_voice_data:
            voice_file = REPO_ROOT / self.config.voice_data_file
            if not voice_file.exists():
                logger.info("Generating voice training data...")
                try:
                    from voice_trainer import VoiceTrainer
                    trainer = VoiceTrainer()
                    items = trainer.generate_batch(count=50)
                    trainer.save_to_jsonl(items, voice_file)
                except Exception as e:
                    logger.warning(f"Voice data generation failed: {e}")
            if voice_file.exists():
                with open(voice_file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                merged.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
                logger.info(f"Voice data loaded")

        # 9. Datos de control del sistema
        if self.config.use_system_data:
            system_file = REPO_ROOT / self.config.system_data_file
            if not system_file.exists():
                logger.info("Generating system controller data...")
                try:
                    from system_controller_trainer import SystemControllerTrainer
                    trainer = SystemControllerTrainer(platform="windows")
                    items = trainer.generate_batch(count=50)
                    trainer.save_to_jsonl(items, system_file)
                except Exception as e:
                    logger.warning(f"System controller data generation failed: {e}")
            if system_file.exists():
                with open(system_file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                merged.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
                logger.info(f"System controller data loaded")

        # 10. Datos de memoria y perfil de usuario
        memory_file = REPO_ROOT / "training-data-memory.jsonl"
        if not memory_file.exists():
            logger.info("Generating memory training data...")
            try:
                memory_items = generate_memory_training_data()
                with open(memory_file, "w", encoding="utf-8") as f:
                    for item in memory_items:
                        f.write(json.dumps(item, ensure_ascii=False) + "\n")
            except Exception as e:
                logger.warning(f"Memory data generation failed: {e}")
        if memory_file.exists():
            with open(memory_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            merged.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            logger.info(f"Memory data loaded")

        # 11. Datos de visión (imágenes, OCR, UI)
        if self.config.use_vision_data:
            vision_file = REPO_ROOT / self.config.vision_data_file
            if not vision_file.exists():
                logger.info("Generating vision training data...")
                try:
                    from vision_trainer import VisionTrainer
                    trainer = VisionTrainer()
                    items = trainer.generate_batch(count=50)
                    trainer.save_to_jsonl(items, vision_file)
                except Exception as e:
                    logger.warning(f"Vision data generation failed: {e}")
            if vision_file.exists():
                with open(vision_file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                merged.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
                logger.info(f"Vision data loaded")

        # 12. Datos de análisis de pantalla/UI
        if self.config.use_screen_data:
            screen_file = REPO_ROOT / self.config.screen_data_file
            if not screen_file.exists():
                logger.info("Generating screen understanding data...")
                try:
                    from screen_understanding import ScreenUnderstanding
                    analyzer = ScreenUnderstanding()
                    items = analyzer.generate_batch(count=50)
                    analyzer.save_to_jsonl(items, screen_file)
                except Exception as e:
                    logger.warning(f"Screen data generation failed: {e}")
            if screen_file.exists():
                with open(screen_file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                merged.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
                logger.info(f"Screen data loaded")

        # 13. Datos de persuasión y comunicación empática
        if self.config.use_persuasion_data:
            persuasion_file = REPO_ROOT / self.config.persuasion_data_file
            if not persuasion_file.exists():
                logger.info("Generating persuasion training data...")
                try:
                    from persuasion_engine import PersuasionEngine
                    engine = PersuasionEngine()
                    items = engine.generate_batch(count=50)
                    engine.save_to_jsonl(items, persuasion_file)
                except Exception as e:
                    logger.warning(f"Persuasion data generation failed: {e}")
            if persuasion_file.exists():
                with open(persuasion_file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                merged.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
                logger.info(f"Persuasion data loaded")

        # 14. Datos de memoria emocional
        if self.config.use_emotional_data:
            emotional_file = REPO_ROOT / self.config.emotional_data_file
            if not emotional_file.exists():
                logger.info("Generating emotional memory training data...")
                try:
                    from emotional_memory import EmotionalMemory
                    memory = EmotionalMemory()
                    items = memory.generate_batch(count=50)
                    memory.save_to_jsonl(items, emotional_file)
                except Exception as e:
                    logger.warning(f"Emotional data generation failed: {e}")
            if emotional_file.exists():
                with open(emotional_file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                merged.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
                logger.info(f"Emotional data loaded")

        # 15. Datos evolucionados (personalidades, contexto, lógica)
        if self.config.use_evolved_data:
            evolved_file = REPO_ROOT / self.config.evolved_data_file
            if not evolved_file.exists():
                logger.info("Generating evolved training data...")
                try:
                    from training_evolution import TrainingEvolution
                    evolver = TrainingEvolution()
                    base_items = self._load_base_items()
                    personalities = ["scientist", "poet", "professor", "storyteller", "friend", "technician"]
                    items = evolver.evolve(base_items=base_items, personalities=personalities, count=50)
                    evolver.save_to_jsonl(items, evolved_file)
                except Exception as e:
                    logger.warning(f"Evolved data generation failed: {e}")
            if evolved_file.exists():
                with open(evolved_file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                merged.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
                logger.info(f"Evolved data loaded")

        # 16. Datos de autoevolución
        if self.config.use_self_evolved_data:
            self_evolved_file = REPO_ROOT / self.config.self_evolved_data_file
            if not self_evolved_file.exists():
                logger.info("Generating self-evolved training data...")
                try:
                    from self_evolution import SelfEvolution
                    evolver = SelfEvolution()
                    base_path = REPO_ROOT / "training-data.jsonl"
                    result = evolver.evolve(dataset_path=base_path, iterations=1, count=30)
                    if result.get("total_items", 0) > 0:
                        items = evolver.load_jsonl(Path(str(DEFAULT_OUTPUT)))
                        evolver.save_to_jsonl(items, self_evolved_file)
                except Exception as e:
                    logger.warning(f"Self-evolved data generation failed: {e}")
            if self_evolved_file.exists():
                with open(self_evolved_file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                merged.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
                logger.info(f"Self-evolved data loaded")

        # 17. Deduplicar
        seen = set()
        unique: List[Dict] = []
        for item in merged:
            key = json.dumps({"t": item.get("text", ""), "o": item.get("output", "")}, sort_keys=True)
            if key not in seen:
                seen.add(key)
                unique.append(item)

        # 9. Guardar
        data_path = REPO_ROOT / "training-data-collected.jsonl"
        with open(data_path, "w", encoding="utf-8") as f:
            for item in unique:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        logger.info(f"Total collected: {len(unique)} unique samples -> {data_path}")
        return str(data_path), len(unique)


class ModelTrainer:
    """Fine-tuning con LoRA + cuantización, optimizado para CPU/GPU."""

    def __init__(self, config: TrainingConfig):
        self.config = config
        self.tokenizer = None
        self.model = None
        self.device = None
        self.is_loaded = False

    def _load(self) -> None:
        """Carga modelo + tokenizer con configuración de memoria óptima."""
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Device: {self.device}")

        model_src = self.config.model_path or self.config.model_id
        logger.info(f"Loading model: {model_src}")

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_src, trust_remote_code=True
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        bnb_config = None
        if self.config.use_4bit and self.device.type == "cuda":
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
            )

        self.model = AutoModelForCausalLM.from_pretrained(
            model_src,
            quantization_config=bnb_config,
            device_map="auto" if self.device.type == "cuda" else None,
            trust_remote_code=True,
            torch_dtype=torch.float16 if self.device.type == "cuda" else torch.float32,
            low_cpu_mem_usage=True if self.device.type == "cpu" else False,
        )

        # Apply LoRA
        if self.config.use_lora:
            from peft import LoraConfig, get_peft_model, TaskType

            lora_cfg = LoraConfig(
                task_type=TaskType.CAUSAL_LM,
                r=self.config.lora_r,
                lora_alpha=self.config.lora_alpha,
                lora_dropout=self.config.lora_dropout,
                target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
                bias="none",
            )
            self.model = get_peft_model(self.model, lora_cfg)

        # Gradient checkpointing for memory efficiency
        if self.config.use_gradient_checkpointing and hasattr(self.model, "gradient_checkpointing_enable"):
            try:
                self.model.gradient_checkpointing_enable()
            except Exception:
                pass

        self.is_loaded = True

    def train(self, data_path: str, test_mode: bool = False) -> str:
        """Ejecuta el entrenamiento con configuración optimizada."""
        if not self.is_loaded:
            self._load()

        import torch
        from datasets import Dataset
        from transformers import (
            TrainingArguments,
            Trainer,
            DataCollatorForLanguageModeling,
        )

        logger.info("Preparing dataset...")
        texts = []
        with open(data_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    text = entry.get("text", "")
                    output = entry.get("output", "")
                    if text and output:
                        texts.append(f"User: {text}\nAssistant: {output}\n")
                except json.JSONDecodeError:
                    continue

        if not texts:
            logger.error("No training data")
            return ""

        if test_mode:
            texts = texts[:10]
            self.config.epochs = 1
            self.config.batch_size = 2
            self.config.max_length = 256

        # Tokenize
        tokenized = self.tokenizer(
            texts, truncation=True, max_length=self.config.max_length, padding="max_length"
        )

        # Split 90/10
        split = int(len(texts) * 0.9)
        train_ds = Dataset.from_dict({
            "input_ids": tokenized["input_ids"][:split],
            "attention_mask": tokenized["attention_mask"][:split],
        })
        eval_ds = Dataset.from_dict({
            "input_ids": tokenized["input_ids"][split:],
            "attention_mask": tokenized["attention_mask"][split:],
        })

        # Output dir with timestamp
        ts = int(time.time())
        output_dir = Path(self.config.output_dir) / f"run-{ts}"
        output_dir.mkdir(parents=True, exist_ok=True)

        grad_accum = max(1, 4 // self.config.batch_size)

        training_args = TrainingArguments(
            output_dir=str(output_dir),
            num_train_epochs=self.config.epochs,
            per_device_train_batch_size=self.config.batch_size,
            per_device_eval_batch_size=self.config.batch_size,
            gradient_accumulation_steps=grad_accum,
            learning_rate=self.config.lr,
            weight_decay=self.config.weight_decay,
            fp16=self.device.type == "cuda",
            bf16=False,
            logging_steps=5,
            eval_strategy="steps",
            eval_steps=self.config.eval_steps,
            save_strategy="steps",
            save_steps=self.config.save_steps,
            save_total_limit=2,
            warmup_steps=min(self.config.warmup_steps, 50),
            report_to="none",
            remove_unused_columns=False,
            dataloader_pin_memory=False,
            torch_compile=False,
            optim="adamw_torch",
            lr_scheduler_type="cosine",
        )

        data_collator = DataCollatorForLanguageModeling(
            tokenizer=self.tokenizer, mlm=False
        )

        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_ds,
            eval_dataset=eval_ds,
            data_collator=data_collator,
        )

        logger.info(f"Training: {len(train_ds)} train, {len(eval_ds)} eval, {self.config.epochs} epochs")
        start = time.time()
        trainer.train()
        elapsed = time.time() - start
        logger.info(f"Training complete: {elapsed:.1f}s")

        # Save
        self.model.save_pretrained(output_dir)
        self.tokenizer.save_pretrained(output_dir)

        # Compute final metrics
        eval_results = trainer.evaluate()
        perplexity = math.exp(eval_results.get("eval_loss", 0))

        metrics = {
            "epoch": self.config.epochs,
            "train_samples": len(train_ds),
            "eval_samples": len(eval_ds),
            "eval_loss": eval_results.get("eval_loss", 0),
            "perplexity": perplexity,
            "training_time_sec": elapsed,
            "device": str(self.device),
            "lora_params": sum(1 for _ in self.model.parameters() if _.requires_grad),
            "total_params": sum(p.numel() for p in self.model.parameters()),
        }

        with open(output_dir / "metrics.json", "w") as f:
            json.dump(metrics, f, indent=2)

        logger.info(f"Metrics: loss={metrics['eval_loss']:.4f}, ppl={perplexity:.2f}")
        return str(output_dir)


class ModelEvaluator:
    """Evalúa el modelo entrenado con métricas automáticas."""

    def __init__(self, config: TrainingConfig):
        self.config = config

    def evaluate(self, model_path: str) -> Dict[str, Any]:
        """Evalúa el modelo con datos de test y métricas de calidad."""
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM

        logger.info(f"Evaluating model: {model_path}")

        tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float16 if device.type == "cuda" else torch.float32,
            device_map=None if device.type == "cpu" else "auto",
            trust_remote_code=True,
            low_cpu_mem_usage=True,
        )
        if device.type == "cpu":
            model = model.to(device)
        model.eval()

        # Load eval data
        eval_texts = []
        data_file = REPO_ROOT / "training-data-collected.jsonl"
        if not data_file.exists():
            data_file = REPO_ROOT / "training-data.jsonl"
        if data_file.exists():
            with open(data_file, encoding="utf-8") as f:
                lines = f.readlines()
            split = int(len(lines) * 0.9)
            for line in lines[split:]:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    eval_texts.append((entry.get("text", ""), entry.get("output", "")))
                except json.JSONDecodeError:
                    continue

        if not eval_texts:
            eval_texts = [
                ("What is AURA?", "AURA is an autonomous AI ecosystem."),
                ("How to create AME?", "Use the /api/ame-core endpoint."),
            ]

        # Evaluate Q&A accuracy (exact match / keyword overlap)
        correct = 0
        total = 0
        for question, expected in eval_texts[:50]:
            prompt = f"User: {question}\nAssistant: "
            inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
            try:
                with torch.no_grad():
                    out = model.generate(**inputs, max_new_tokens=128, temperature=0.3, do_sample=False)
                response = tokenizer.decode(out[0], skip_special_tokens=True)
                response = response.replace(prompt, "").strip()
            except Exception as e:
                logger.warning(f"Generation failed for question '{question[:50]}': {e}")
                response = ""

            # Simple keyword overlap
            expected_words = set(expected.lower().split())
            response_words = set(response.lower().split())
            overlap = len(expected_words & response_words) / max(len(expected_words), 1)
            if overlap > 0.3:
                correct += 1
            total += 1

        accuracy = correct / total if total > 0 else 0

        # Compute perplexity on a sample
        ppl = 0.0
        if eval_texts:
            sample = eval(f"User: {eval_texts[0][0]}\nAssistant: {eval_texts[0][1]}\n")
            inputs = tokenizer(sample, return_tensors="pt", truncation=True, max_length=256)
            with torch.no_grad():
                outputs = model(**inputs, labels=inputs["input_ids"])
                ppl = math.exp(outputs.loss.item()) if outputs.loss.item() < 20 else float("inf")

        metrics = {
            "qa_accuracy": round(accuracy, 4),
            "qa_correct": correct,
            "qa_total": total,
            "perplexity": round(ppl, 2) if ppl != float("inf") else "inf",
            "evaluated_samples": len(eval_texts),
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(f"Evaluation: accuracy={accuracy:.2%}, ppl={metrics['perplexity']}")
        return metrics


class AutonomousTrainer:
    """
    Orquestador completo: collect → train → evaluate → improve.
    Loop autónomo con auto-mejora iterativa.
    """

    def __init__(self, config: Optional[TrainingConfig] = None):
        self.config = config or TrainingConfig()
        self.trainer = ModelTrainer(self.config)
        self.collector = DataCollector(self.config)
        self.evaluator = ModelEvaluator(self.config)
        self.iteration = 0
        self.history: List[Dict] = self._load_history()

    def _load_history(self) -> List[Dict]:
        if METRICS_FILE.exists():
            with open(METRICS_FILE) as f:
                return json.load(f)
        return []

    def _save_history(self) -> None:
        METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(METRICS_FILE, "w") as f:
            json.dump(self.history, f, indent=2)

    def run_automatic(self, test_mode: bool = False) -> Dict:
        """Ejecuta el pipeline autónomo completo con auto-mejora."""
        logger.info("=" * 60)
        logger.info("  AURA AUTONOMOUS TRAINING PIPELINE")
        logger.info("=" * 60)

        results: Dict[str, Any] = {
            "iterations": [],
            "final_model": None,
            "final_metrics": None,
        }

        for iteration in range(1, self.config.max_collections + 1):
            self.iteration = iteration
            logger.info(f"\n{'='*60}")
            logger.info(f"  ITERATION {iteration}/{self.config.max_collections}")
            logger.info(f"{'='*60}")

            # 1. Collect data
            if self.config.web_search or self.config.auto_collect:
                data_path, count = self.collector.collect()
                logger.info(f"Collected {count} training samples")
            else:
                data_path = str(REPO_ROOT / "training-data.jsonl")

            # 2. Train
            model_path = self.trainer.train(data_path, test_mode=test_mode)
            logger.info(f"Model trained: {model_path}")

            # 3. Evaluate
            metrics = self.evaluator.evaluate(model_path)
            metrics["iteration"] = iteration
            metrics["model_path"] = model_path
            results["iterations"].append(metrics)
            self.history.append(metrics)
            self._save_history()

            logger.info(f"Iteration {iteration} metrics: {json.dumps(metrics, indent=2)}")

            # 4. Check quality threshold
            qa_acc = metrics.get("qa_accuracy", 0)
            if qa_acc >= self.config.quality_threshold:
                logger.info(f"✅ Quality threshold reached ({qa_acc:.2%} >= {self.config.quality_threshold:.2%})")
                results["final_model"] = model_path
                results["final_metrics"] = metrics
                break
            else:
                logger.info(f"⚠️ Quality below threshold ({qa_acc:.2%} < {self.config.quality_threshold:.2%})")
                if iteration < self.config.max_collections:
                    logger.info("Collecting more data and retrying...")
                    self.config.topics = self._expand_topics(metrics)
                else:
                    logger.warning("Max iterations reached — using best model so far")

            results["final_model"] = model_path
            results["final_metrics"] = metrics

        # Save final config
        self._save_final_config(results)
        return results

    def _expand_topics(self, metrics: Dict) -> List[str]:
        """Expand topics for next iteration based on evaluation gaps."""
        base_topics = self.config.topics
        new_topics = list(base_topics)

        if metrics.get("qa_accuracy", 1) < 0.5:
            new_topics.extend(["machine learning basics", "artificial intelligence tutorial"])
        if metrics.get("perplexity", 0) == "inf" or metrics.get("perplexity", 0) > 100:
            new_topics.extend(["technical documentation", "software engineering best practices"])

        logger.info(f"Expanded topics for next iteration: {new_topics}")
        return new_topics

    def _save_final_config(self, results: Dict) -> None:
        """Guarda configuración final del entrenamiento."""
        config = {
            "final_model": results["final_model"],
            "final_metrics": results["final_metrics"],
            "iterations": len(results["iterations"]),
            "config": asdict(self.config),
            "created_at": datetime.now().isoformat(),
            "history": self.history,
        }
        config_path = OUTPUT_BASE / "autonomous_training_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2, default=str)
        logger.info(f"Config saved: {config_path}")

    def run_evaluate_only(self, model_path: str) -> Dict:
        """Solo evalúa un modelo existente."""
        return self.evaluator.evaluate(model_path)

    def show_metrics(self) -> None:
        """Muestra métricas de entrenamientos anteriores."""
        if not self.history:
            print("No metrics found. Run training first.")
            return

        print(f"\n{'Iter':<6} {'Accuracy':<12} {'Perplexity':<12} {'Loss':<10} {'Model'}")
        print("-" * 80)
        for m in self.history:
            acc = f"{m.get('qa_accuracy', 0):.2%}"
            ppl = str(m.get("perplexity", "—"))
            loss = f"{m.get('eval_loss', 0):.4f}"
            path = m.get("model_path", "—")
            print(f"{m.get('iteration', '?'):<6} {acc:<12} {ppl:<12} {loss:<10} {path}")


# ---------------------------------------------------------------------- #
#  MEMORY TRAINING DATA GENERATOR
# ---------------------------------------------------------------------- #
def generate_memory_training_data(count: int = 50) -> List[Dict]:
    """Genera datos de entrenamiento para memoria y perfil de usuario."""
    memory_templates = [
        {
            "template": "El usuario prefiere recibir respuestas en formato {format} y con tono {tone}.",
            "variables": {
                "format": ["lista", "párrafos cortos", "tabla", "código con comentarios"],
                "tone": ["técnico", "casual", "formal", "amigable", "conciliador"],
            },
        },
        {
            "template": "Recordar que el usuario trabaja en {project} y su rol es {role}.",
            "variables": {
                "project": ["AURA", "AME", "proyecto Alpha", "infraestructura cloud", "investigación IA"],
                "role": ["desarrollador", "investigador", "arquitecto", "devops", "manager"],
            },
        },
        {
            "template": "El usuario tiene una reunión de {meeting_type} los {day} a las {time}.",
            "variables": {
                "meeting_type": ["sprint", "cliente", "equipo", "revisión de código", "planificación"],
                "day": ["lunes", "martes", "miércoles", "jueves", "viernes"],
                "time": ["09:00", "10:30", "14:00", "16:00", "18:00"],
            },
        },
        {
            "template": "El usuario aprendió {skill} y prefiere usar {tool} para {task}.",
            "variables": {
                "skill": ["Python asíncrono", "Docker multi-stage", "Kubernetes", "React hooks", "SQL tuning"],
                "tool": ["VS Code", "PyCharm", "Vim", "Postman", "DBeaver"],
                "task": ["desarrollo", "debugging", "testing", "prototipado", "análisis"],
            },
        },
        {
            "template": "El usuario mencionó que le gusta {hobby} y odia {annoyance}.",
            "variables": {
                "hobby": ["la música synthwave", "el café solo", "los puzzles lógicos", "el código limpio", "la ciencia ficción"],
                "annoyance": ["el ruido", "las reuniones sin agenda", "el código espagueti", "las notificaciones", "el calor"],
            },
        },
        {
            "template": "Relación: {person} es {relation} del usuario y trabaja en {company}.",
            "variables": {
                "person": ["María", "Carlos", "Ana", "Roberto", "Laura"],
                "relation": ["compañero", "jefe", "cliente", "mentor", "amigo"],
                "company": ["TechCorp", "DataSystems", "CloudNine", "StartupXYZ", "Freelance"],
            },
        },
        {
            "template": "Error recurrente: {error}. Solución aplicada: {fix}.",
            "variables": {
                "error": ["ImportError de módulo", "Timeout en API", "Memory leak en worker", "CORS en frontend", "Permiso denegado en carpeta"],
                "fix": ["Reiniciar servicio", "Agregar retry con backoff", "Actualizar librería", "Verificar headers", "Ejecutar como administrador"],
            },
        },
        {
            "template": "El usuario tiene como objetivo personal: {goal} y como objetivo profesional: {goal2}.",
            "variables": {
                "goal": ["leer 12 libros este año", "hacer ejercicio 3 veces por semana", "aprender japonés", "ahorrar para un coche"],
                "goal2": ["lanzar un producto SaaS", "obtener certificación cloud", "hablar en una conferencia", "aumentar salario un 20%"],
            },
        },
    ]

    items = []
    for i in range(count):
        template = random.choice(memory_templates)
        text = template["template"]
        variables = template.get("variables", {})
        for var, values in variables.items():
            if isinstance(values, list) and values:
                val = random.choice(values)
                if isinstance(val, int):
                    val = str(val)
                text = text.replace("{" + var + "}", val)

        memory_type = random.choice(["preference", "fact", "habit", "relationship", "project", "goal"])
        items.append({
            "text": f"Recuerda: {text}",
            "output": f"Memoria almacenada.\nTipo: {memory_type}\nContenido: {text}\nAcción: Actualizar perfil y memoria a largo plazo.",
            "metadata": {
                "source": "memory_trainer",
                "memory_type": memory_type,
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            },
        })
    return items


# ---------------------------------------------------------------------- #
#  CLI
# ---------------------------------------------------------------------- #
def cmd_auto(args: argparse.Namespace) -> None:
    config = TrainingConfig(
        model_path=args.model_path,
        epochs=args.epochs,
        lr=args.lr,
        batch_size=args.batch_size,
        max_length=args.max_length,
        use_lora=not args.no_lora,
        use_4bit=not args.no_4bit,
        use_gradient_checkpointing=not args.no_grad_ckpt,
        use_ui_data=not getattr(args, "no_ui_data", False),
        use_reasoning_data=not getattr(args, "no_reasoning_data", False),
        use_task_data=not getattr(args, "no_task_data", False),
        use_search_data=not getattr(args, "no_search_data", False),
        use_device_data=not getattr(args, "no_device_data", False),
        use_voice_data=not getattr(args, "no_voice_data", False),
        use_system_data=not getattr(args, "no_system_data", False),
        use_vision_data=not getattr(args, "no_vision_data", False),
        use_screen_data=not getattr(args, "no_screen_data", False),
        use_persuasion_data=not getattr(args, "no_persuasion_data", False),
        use_emotional_data=not getattr(args, "no_emotional_data", False),
        use_evolved_data=not getattr(args, "no_evolved_data", False),
        use_self_evolved_data=not getattr(args, "no_self_evolved_data", False),
        auto_collect=True,
        auto_improve=not getattr(args, "no_auto_improve", False) and getattr(args, "auto_improve", False),
        web_search=not getattr(args, "no_web_search", False) and getattr(args, "web_search", False),
        topics=args.topics,
        quality_threshold=args.quality_threshold,
        max_collections=args.max_collections,
        output_dir=args.output,
    )
    trainer = AutonomousTrainer(config)
    results = trainer.run_automatic(test_mode=getattr(args, "test", False))

    print(f"\n{'='*60}")
    print(f"  ENTRENAMIENTO AUTÓNOMO COMPLETADO")
    print(f"{'='*60}")
    print(f"  Iteraciones: {len(results['iterations'])}")
    final = results["final_metrics"]
    if final:
        print(f"  Accuracy:  {final.get('qa_accuracy', '—')}")
        print(f"  Perplexity: {final.get('perplexity', '—')}")
        print(f"  Loss:      {final.get('eval_loss', '—')}")
    print(f"  Modelo:    {results['final_model']}")
    print(f"  Config:    {OUTPUT_BASE / 'autonomous_training_config.json'}")


def cmd_evaluate(args: argparse.Namespace) -> None:
    config = TrainingConfig(model_path=args.model_path)
    trainer = AutonomousTrainer(config)
    metrics = trainer.run_evaluate_only(args.model)
    print(json.dumps(metrics, indent=2))


def cmd_metrics(args: argparse.Namespace) -> None:
    config = TrainingConfig()
    trainer = AutonomousTrainer(config)
    trainer.show_metrics()


def cmd_web_collect(args: argparse.Namespace) -> None:
    config = TrainingConfig(
        web_search=True,
        topics=args.topics,
        num_search_results=args.num_results,
        samples_per_page=args.samples_per_page,
    )
    collector = DataCollector(config)
    data_path, count = collector.collect()
    print(f"\n[OK] Collected {count} samples → {data_path}")


def main():
    p = argparse.ArgumentParser(
        description="AURA Autonomous Trainer — auto-collect + train + evaluate + improve",
    )
    sub = p.add_subparsers(dest="command")

    s_auto = sub.add_parser("auto", help="Pipeline autónomo completo (default)")
    s_auto.add_argument("--model-path", default="models/qwen-1.5b")
    s_auto.add_argument("--output", default="fine-tuned-ame")
    s_auto.add_argument("--epochs", type=int, default=5)
    s_auto.add_argument("--lr", type=float, default=8e-5)
    s_auto.add_argument("--batch-size", type=int, default=4)
    s_auto.add_argument("--max-length", type=int, default=2048)
    s_auto.add_argument("--no-lora", action="store_true")
    s_auto.add_argument("--no-4bit", action="store_true")
    s_auto.add_argument("--no-grad-ckpt", action="store_true")
    s_auto.add_argument("--quality-threshold", type=float, default=0.80)
    s_auto.add_argument("--max-collections", type=int, default=2)
    s_auto.add_argument("--topics", nargs="+", default=["AURA AI", "LLM fine-tuning", "HTML CSS JavaScript UI design"])
    s_auto.add_argument("--web-search", action="store_true")
    s_auto.add_argument("--auto-improve", action="store_true")
    s_auto.add_argument("--num-results", type=int, default=8)
    s_auto.add_argument("--samples-per-page", type=int, default=5)
    s_auto.add_argument("--no-ui-data", action="store_true")
    s_auto.add_argument("--no-reasoning-data", action="store_true")
    s_auto.add_argument("--no-task-data", action="store_true")
    s_auto.add_argument("--no-search-data", action="store_true")
    s_auto.add_argument("--no-device-data", action="store_true")
    s_auto.add_argument("--no-voice-data", action="store_true")
    s_auto.add_argument("--no-system-data", action="store_true")
    s_auto.add_argument("--no-vision-data", action="store_true")
    s_auto.add_argument("--no-screen-data", action="store_true")
    s_auto.add_argument("--no-persuasion-data", action="store_true")
    s_auto.add_argument("--no-emotional-data", action="store_true")
    s_auto.add_argument("--no-evolved-data", action="store_true")
    s_auto.add_argument("--no-self-evolved-data", action="store_true")
    s_auto.add_argument("--no-web-search", action="store_true")
    s_auto.add_argument("--no-auto-improve", action="store_true")
    s_auto.add_argument("--test", action="store_true", help="Dry run con datos mínimos")
    s_auto.set_defaults(func=cmd_auto)

    s_eval = sub.add_parser("evaluate", help="Evaluar modelo existente")
    s_eval.add_argument("--model", required=True, help="Ruta del modelo a evaluar")
    s_eval.add_argument("--model-path", default="models/qwen-1.5b")
    s_eval.set_defaults(func=cmd_evaluate)

    s_metrics = sub.add_parser("metrics", help="Mostrar métricas históricas")
    s_metrics.set_defaults(func=cmd_metrics)

    s_web = sub.add_parser("web-collect", help="Solo coleccionar datos de internet")
    s_web.add_argument("--topics", nargs="+", default=["AURA AI", "LLM fine-tuning"])
    s_web.add_argument("--num-results", type=int, default=8)
    s_web.add_argument("--samples-per-page", type=int, default=5)
    s_web.set_defaults(func=cmd_web_collect)

    args = p.parse_args()

    if not args.command:
        args.command = "auto"
        args.func = cmd_auto
        # Set defaults for auto command
        for action in s_auto._actions:
            if not hasattr(args, action.dest):
                setattr(args, action.dest, action.default)

    if args.command == "evaluate":
        cmd_evaluate(args)
        return

    if hasattr(args, "func"):
        args.func(args)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
