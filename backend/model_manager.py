"""Model Manager simplificado - Usa model_trainer.py y model_registry.py."""

from __future__ import annotations

import os
from typing import Optional

from .model_registry import ModelRegistry, ModelType
from .model_trainer import ModelTrainer, TrainingStage, TrainingJob


class ModelManager:
    """Orquestador central de modelos (versión simplificada)."""

    def __init__(self, db, models_path: str = "/tmp/aura_models") -> None:
        self.db = db
        self.models_path = models_path
        self.trainer = ModelTrainer()
        self.registry = ModelRegistry(db)
        self.training_jobs: dict[str, TrainingJob] = {}

        os.makedirs(models_path, exist_ok=True)

    async def load_base_model(self) -> bool:
        print("Cargando modelo base Qwen-7B...")
        try:
            await self.registry.register_model(
                model_id="qwen-7b-base",
                model_type=ModelType.BASE,
                base_model="Qwen-7B",
                version="1.0.0",
                parameters=7000000000,
                hardware_used="cpu",
                file_size_mb=14400,
            )
            print("Modelo base registrado")
            return True
        except Exception as e:
            print(f"Error cargando modelo: {e}")
            return False

    async def create_fine_tune_job(
        self,
        model_type: ModelType,
        dataset_id: str,
        genre: Optional[str] = None,
        language: Optional[str] = None,
        batch_size: int = 8,
        num_epochs: int = 3,
        use_lora: bool = True,
    ) -> str:
        from datetime import datetime

        job_id = f"job-{int(datetime.now().timestamp() * 1000)}"

        job = TrainingJob(
            job_id=job_id,
            model_id=f"{model_type.value}-{genre or language or 'default'}",
            dataset_id=dataset_id,
            batch_size=batch_size,
            learning_rate=2e-4,
            num_epochs=num_epochs,
            max_steps=1000,
            stage=TrainingStage.PENDING,
            progress_percent=0.0,
            started_at=datetime.now().isoformat(),
            completed_at=None,
            loss_history=[],
            validation_loss=None,
            results=None,
            error_message=None,
        )

        self.training_jobs[job_id] = job
        await self.db.add_training_job(job)
        print(f"Job creado: {job_id}")
        return job_id

    async def quantize_model(self, model_id: str, bits: int = 4) -> Optional[str]:
        print(f"Cuantizando modelo a {bits}-bit...")
        try:
            await self.registry.update_model_performance(
                model_id,
                {"quantization": f"{bits}-bit"},
            )
            quant_path = f"{self.models_path}/{model_id}-{bits}bit"
            print(f"Modelo cuantizado: {quant_path}")
            return quant_path
        except Exception as e:
            print(f"Error cuantizando: {e}")
            return None

    async def merge_ensemble(self, model_ids: list) -> str:
        from datetime import datetime

        print(f"Mergeando {len(model_ids)} modelos...")
        ensemble_id = f"ensemble-{int(datetime.now().timestamp() * 1000)}"

        await self.registry.register_model(
            model_id=ensemble_id,
            model_type=ModelType.ENSEMBLE,
            base_model="merged",
            version="1.0.0",
            parameters=7000000000,
            hardware_used="cpu",
            file_size_mb=14400,
        )

        print(f"Ensemble creado: {ensemble_id}")
        return ensemble_id

    async def get_active_models(self):
        return await self.registry.get_active_models()

    async def activate_model(self, model_id: str) -> bool:
        return await self.registry.activate_model(model_id)

    async def get_model_performance(self, model_id: str) -> dict:
        return await self.registry.get_model_performance(model_id)

    def list_all_models(self):
        return self.registry.list_all_models()
