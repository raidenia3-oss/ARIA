"""BLOQUE 86 - Edge-AI package re-exports (100% local, offline)."""
from backend.edge_ai.dataset import DatasetFormatter, TrainingExample
from backend.edge_ai.engine import (
    OfflineLoRATrainer,
    get_edge_trainer,
    reset_edge_trainer,
)
from backend.edge_ai.trainer import LoRAAdapter, TrainingRun

__all__ = [
    "DatasetFormatter", "TrainingExample", "LoRAAdapter", "TrainingRun",
    "OfflineLoRATrainer", "get_edge_trainer", "reset_edge_trainer",
]

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
