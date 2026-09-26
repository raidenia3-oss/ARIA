"""Registry de modelos disponibles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ModelType(str, Enum):
    BASE = "base"
    LORA = "lora"
    GENRE = "genre"
    LANGUAGE = "language"
    ENSEMBLE = "ensemble"


@dataclass
class ModelMetadata:
    model_id: str
    model_type: ModelType
    base_model: str
    version: str
    created_at: str
    trained_at: Optional[str]
    genre: Optional[str]
    language: Optional[str]
    accuracy: float
    perplexity: float
    parameters: int
    quantization: Optional[str]
    hardware_used: str
    training_time_hours: float
    file_size_mb: float
    is_active: bool
    performance_metrics: Dict[str, Any]
    lora_rank: Optional[int]
    lora_alpha: Optional[int]


class ModelRegistry:
    """Registry de modelos disponibles."""

    def __init__(self, db) -> None:
        self.db = db
        self.model_registry: Dict[str, ModelMetadata] = {}

    async def register_model(
        self,
        model_id: str,
        model_type: ModelType,
        base_model: str,
        version: str,
        parameters: int,
        hardware_used: str,
        file_size_mb: float,
        accuracy: float = 0.0,
        genre: Optional[str] = None,
        language: Optional[str] = None,
        quantization: Optional[str] = None,
        lora_rank: Optional[int] = None,
        lora_alpha: Optional[int] = None,
    ) -> None:
        metadata = ModelMetadata(
            model_id=model_id,
            model_type=model_type,
            base_model=base_model,
            version=version,
            created_at=datetime.now().isoformat(),
            trained_at=None,
            genre=genre,
            language=language,
            accuracy=accuracy,
            perplexity=50.0,
            parameters=parameters,
            quantization=quantization,
            hardware_used=hardware_used,
            training_time_hours=0.0,
            file_size_mb=file_size_mb,
            is_active=True,
            performance_metrics={},
            lora_rank=lora_rank,
            lora_alpha=lora_alpha,
        )
        self.model_registry[model_id] = metadata
        await self.db.add_model_metadata(metadata)

    async def get_active_models(self) -> List[Dict[str, Any]]:
        return [self._serialize(m) for m in self.model_registry.values() if m.is_active]

    async def activate_model(self, model_id: str) -> bool:
        if model_id not in self.model_registry:
            return False
        for m in self.model_registry.values():
            m.is_active = False
        self.model_registry[model_id].is_active = True
        return True

    def _serialize(self, metadata: ModelMetadata) -> Dict[str, Any]:
        return {
            "model_id": metadata.model_id,
            "model_type": metadata.model_type.value,
            "base_model": metadata.base_model,
            "version": metadata.version,
            "accuracy": metadata.accuracy,
            "perplexity": metadata.perplexity,
            "parameters": metadata.parameters,
            "quantization": metadata.quantization,
            "hardware_used": metadata.hardware_used,
            "is_active": metadata.is_active,
        }
