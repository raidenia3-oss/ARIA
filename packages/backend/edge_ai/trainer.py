"""BLOQUE 86 - Offline LoRA training pipeline + hot-swap (local, CPU-only)."""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from backend.edge_ai.dataset import TrainingExample

MAX_EXAMPLES = 5000
MAX_EPOCHS = 5
MAX_STEPS_PER_EPOCH = 200


@dataclass
class LoRAAdapter:
    adapter_id: str = ""
    base_model: str = "aura-slm-local"
    rank: int = 8
    examples: int = 0
    final_loss: float = 0.0
    created_at: float = 0.0
    active: bool = False

    def __post_init__(self) -> None:
        if not self.adapter_id:
            self.adapter_id = uuid.uuid4().hex[:12]
        if not self.created_at:
            self.created_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "adapter_id": self.adapter_id, "base_model": self.base_model,
            "rank": self.rank, "examples": self.examples,
            "final_loss": self.final_loss, "created_at": self.created_at,
            "active": self.active, "offline_only": True,
        }


@dataclass
class TrainingRun:
    run_id: str = ""
    status: str = "queued"
    loss_history: List[float] = field(default_factory=list)
    started_at: float = 0.0
    finished_at: float = 0.0
    adapter_id: str = ""

    def __post_init__(self) -> None:
        if not self.run_id:
            self.run_id = uuid.uuid4().hex[:12]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id, "status": self.status,
            "loss_history": list(self.loss_history),
            "started_at": self.started_at, "finished_at": self.finished_at,
            "adapter_id": self.adapter_id, "offline_only": True,
        }
