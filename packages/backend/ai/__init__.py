"""BLOQUE 101 - Local Edge Fine-Tuning, LoRA Adaptation & On-Device Neural Optimization."""
from backend.ai.fine_tuning import (
    DEFAULT_MAX_RAM_MB,
    DEFAULT_MAX_VRAM_MB,
    MAX_ADAPTER_RANK,
    MAX_DATASET_SAMPLES,
    FineTuningEngine,
    HardwareBudget,
    LoraAdapter,
    LoraAdapterManager,
    LoraDatasetSynthesizer,
    TrainingSample,
    get_engine,
    reset_engine,
)

__all__ = [
    "DEFAULT_MAX_RAM_MB", "DEFAULT_MAX_VRAM_MB", "MAX_ADAPTER_RANK",
    "MAX_DATASET_SAMPLES", "FineTuningEngine", "HardwareBudget",
    "LoraAdapter", "LoraAdapterManager", "LoraDatasetSynthesizer",
    "TrainingSample", "get_engine", "reset_engine",
]

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
