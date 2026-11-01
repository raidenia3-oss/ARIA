# -*- coding: utf-8 -*-
"""ARIA OS - AI Training Engine.

Motor de entrenamiento para IA asistente personal.
Gestiona fine-tuning, RLHF, aprendizaje continuo y datasets propios.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("ARIA.AI.Training")


@dataclass
class TrainingExample:
    """Ejemplo de entrenamiento para el asistente personal."""
    input: str
    output: str
    context: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    rating: Optional[float] = None


@dataclass
class TrainingJob:
    job_id: str
    status: str  # pending, running, completed, failed
    method: str  # lora, qlora, instruction, rlhf, full
    dataset_size: int
    epochs: int
    learning_rate: float
    progress: float = 0.0
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


class AITrainingEngine:
    """Motor de entrenamiento para IA asistente personal.

    Permite:
    - Crear datasets de interacciones usuario-IA
    - Fine-tuning (LoRA, QLoRA, instruction, RLHF)
    - Aprendizaje continuo desde feedback
    - Evaluación de modelos
    """

    def __init__(
        self,
        data_dir: str = "data/training",
        model_dir: str = "models",
    ) -> None:
        self.data_dir = Path(data_dir)
        self.model_dir = Path(model_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        self._examples: List[TrainingExample] = []
        self._jobs: Dict[str, TrainingJob] = {}
        self._feedback_buffer: List[Dict[str, Any]] = []
        self._load_examples()

    # ------------------------------------------------------------------ #
    # Dataset management
    # ------------------------------------------------------------------ #
    def add_example(
        self,
        input_text: str,
        output_text: str,
        context: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        rating: Optional[float] = None,
    ) -> str:
        """Agrega un ejemplo al dataset de entrenamiento."""
        ex = TrainingExample(
            input=input_text,
            output=output_text,
            context=context,
            metadata=metadata or {},
            rating=rating,
        )
        self._examples.append(ex)
        self._save_examples()
        return ex.input[:50]

    def add_feedback(
        self,
        user_input: str,
        model_response: str,
        reward: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Registra feedback del usuario para aprendizaje continuo."""
        self._feedback_buffer.append({
            "input": user_input,
            "output": model_response,
            "reward": reward,
            "metadata": metadata or {},
            "timestamp": time.time(),
        })
        if len(self._feedback_buffer) > 10000:
            self._feedback_buffer = self._feedback_buffer[-5000:]

    def get_dataset(self, min_rating: Optional[float] = None) -> List[Dict[str, str]]:
        """Retorna el dataset filtrado por rating mínimo."""
        data = []
        for ex in self._examples:
            if min_rating is not None and (ex.rating is None or ex.rating < min_rating):
                continue
            data.append({"input": ex.input, "output": ex.output, "context": ex.context or ""})
        return data

    def export_dataset(self, path: str, format: str = "jsonl") -> bool:
        """Exporta el dataset a archivo."""
        try:
            with open(path, "w", encoding="utf-8") as f:
                for ex in self._examples:
                    record = {
                        "input": ex.input,
                        "output": ex.output,
                        "context": ex.context or "",
                        "metadata": ex.metadata,
                        "rating": ex.rating,
                    }
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            return True
        except Exception as exc:
            logger.error(f"Export dataset error: {exc}")
            return False

    # ------------------------------------------------------------------ #
    # Training jobs
    # ------------------------------------------------------------------ #
    async def start_training(
        self,
        method: str = "lora",
        epochs: int = 3,
        learning_rate: float = 5e-5,
        batch_size: int = 8,
        min_rating: Optional[float] = None,
    ) -> str:
        """Inicia un trabajo de entrenamiento."""
        job_id = f"job_{int(time.time())}"
        dataset = self.get_dataset(min_rating=min_rating)

        job = TrainingJob(
            job_id=job_id,
            status="pending",
            method=method,
            dataset_size=len(dataset),
            epochs=epochs,
            learning_rate=learning_rate,
        )
        self._jobs[job_id] = job

        asyncio.create_task(self._run_training(job, dataset))
        return job_id

    async def _run_training(
        self,
        job: TrainingJob,
        dataset: List[Dict[str, str]],
    ) -> None:
        """Ejecuta el entrenamiento de forma asíncrona."""
        job.status = "running"
        try:
            from backend.training.fine_tuning_pipeline import FineTuningPipeline
            pipeline = FineTuningPipeline(model_path=str(self.model_dir))

            if job.method == "qlora":
                result = await pipeline.qlora_train(dataset)
            elif job.method == "instruction":
                result = await pipeline.instruction_tune(dataset)
            elif job.method == "rlhf":
                result = await pipeline.rlhf_train(dataset)
            else:
                result = await pipeline.train(
                    dataset, epochs=job.epochs, lr=job.learning_rate,
                    batch_size=8, method=job.method,
                )

            job.metrics = result
            job.progress = 100.0
            job.status = "completed"
            job.completed_at = time.time()
            logger.info(f"Training job {job.job_id} completed")
        except Exception as exc:
            logger.error(f"Training job {job.job_id} failed: {exc}")
            job.status = "failed"
            job.metrics = {"error": str(exc)}

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        job = self._jobs.get(job_id)
        if not job:
            return None
        return {
            "job_id": job.job_id,
            "status": job.status,
            "method": job.method,
            "progress": job.progress,
            "dataset_size": job.dataset_size,
            "epochs": job.epochs,
            "created_at": job.created_at,
            "completed_at": job.completed_at,
            "metrics": job.metrics,
        }

    def list_jobs(self) -> List[Dict[str, Any]]:
        return [self.get_job_status(jid) for jid in self._jobs]

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    def _examples_file(self) -> Path:
        return self.data_dir / "training_examples.json"

    def _load_examples(self) -> None:
        pf = self._examples_file()
        if not pf.exists():
            return
        try:
            raw = json.loads(pf.read_text(encoding="utf-8"))
            self._examples = [
                TrainingExample(**d) for d in raw
            ]
            logger.info(f"Loaded {len(self._examples)} training examples")
        except Exception as exc:
            logger.warning(f"Error loading examples: {exc}")

    def _save_examples(self) -> None:
        pf = self._examples_file()
        try:
            pf.write_text(
                json.dumps([e.__dict__ for e in self._examples], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning(f"Error saving examples: {exc}")

    # ------------------------------------------------------------------ #
    # Stats
    # ------------------------------------------------------------------ #
    def stats(self) -> Dict[str, Any]:
        return {
            "examples": len(self._examples),
            "jobs": len(self._jobs),
            "feedback_buffer": len(self._feedback_buffer),
            "data_dir": str(self.data_dir),
        }
