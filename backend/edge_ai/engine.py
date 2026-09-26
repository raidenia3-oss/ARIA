"""BLOQUE 86 - OfflineLoRATrainer core (parte 2/2, local CPU-only)."""
from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, List, Optional

from backend.edge_ai.dataset import TrainingExample
from backend.edge_ai.trainer import (
    MAX_EPOCHS,
    MAX_EXAMPLES,
    MAX_STEPS_PER_EPOCH,
    LoRAAdapter,
    TrainingRun,
)


class OfflineLoRATrainer:
    def __init__(self, max_examples: int = MAX_EXAMPLES) -> None:
        self.max_examples = max(1, min(max_examples, MAX_EXAMPLES))
        self._lock = threading.Lock()
        self._runs: Dict[str, TrainingRun] = {}
        self._adapters: Dict[str, LoRAAdapter] = {}
        self._active_id: str = ""
        self._watchers: List[Callable[[Dict[str, Any]], None]] = []

    def on_event(self, cb: Callable[[Dict[str, Any]], None]) -> None:
        with self._lock:
            self._watchers.append(cb)

    def _emit(self, evt: Dict[str, Any]) -> None:
        with self._lock:
            cbs = list(self._watchers)
        for cb in cbs:
            try:
                cb(evt)
            except Exception:
                pass

    def train(self, examples: List[TrainingExample], rank: int = 8,
              epochs: int = 2, base_model: str = "aura-slm-local") -> Dict[str, Any]:
        if not examples:
            raise ValueError("dataset vacio")
        rank = max(1, min(int(rank), 64))
        epochs = max(1, min(int(epochs), MAX_EPOCHS))
        data = examples[: self.max_examples]
        run = TrainingRun(status="running", started_at=time.time())
        with self._lock:
            self._runs[run.run_id] = run
        loss = 2.5
        steps = min(MAX_STEPS_PER_EPOCH, max(1, len(data))) * epochs
        for _ in range(steps):
            loss = max(0.05, loss * 0.985 - 0.001 * rank)
            run.loss_history.append(round(loss, 4))
        adapter = LoRAAdapter(base_model=base_model, rank=rank,
                              examples=len(data), final_loss=run.loss_history[-1])
        with self._lock:
            self._adapters[adapter.adapter_id] = adapter
        run.status = "completed"
        run.finished_at = time.time()
        run.adapter_id = adapter.adapter_id
        self._emit({"type": "trained", "run_id": run.run_id,
                    "adapter_id": adapter.adapter_id, "offline_only": True})
        return {"run": run.to_dict(), "adapter": adapter.to_dict()}

    def evaluate(self, adapter_id: str) -> Dict[str, Any]:
        with self._lock:
            ad = self._adapters.get(adapter_id)
            active = self._adapters.get(self._active_id) if self._active_id else None
        if ad is None:
            return {"evaluated": False, "reason": "not found"}
        baseline = active.final_loss if active else 2.5
        gain = round(baseline - ad.final_loss, 4)
        return {"evaluated": True, "adapter_id": adapter_id,
                "final_loss": ad.final_loss, "baseline_loss": baseline,
                "gain": gain, "better": gain >= 0, "offline_only": True}

    def hot_swap(self, adapter_id: str) -> Dict[str, Any]:
        with self._lock:
            ad = self._adapters.get(adapter_id)
            if ad is None:
                return {"swapped": False, "reason": "not found"}
            prev = self._active_id
            active = self._adapters.get(prev) if prev else None
            if active is not None and ad.final_loss > active.final_loss:
                return {"swapped": False, "reason": "regression vs active",
                        "offline_only": True}
            if prev and prev in self._adapters:
                self._adapters[prev].active = False
            ad.active = True
            self._active_id = adapter_id
        self._emit({"type": "hot_swap", "adapter_id": adapter_id,
                    "previous": prev, "offline_only": True})
        return {"swapped": True, "adapter_id": adapter_id,
                "previous": prev, "offline_only": True}

    def rollback(self) -> Dict[str, Any]:
        with self._lock:
            if not self._active_id:
                return {"rolled_back": False, "reason": "no active adapter"}
            cur = self._active_id
            if cur in self._adapters:
                self._adapters[cur].active = False
            self._active_id = ""
        return {"rolled_back": True, "previous": cur, "offline_only": True}

    def runs(self) -> List[TrainingRun]:
        with self._lock:
            return list(self._runs.values())

    def adapters(self) -> List[LoRAAdapter]:
        with self._lock:
            return list(self._adapters.values())

    def active(self) -> Optional[LoRAAdapter]:
        with self._lock:
            return self._adapters.get(self._active_id) if self._active_id else None


_global_edge: Optional[OfflineLoRATrainer] = None
_edge_lock = threading.Lock()


def get_edge_trainer() -> OfflineLoRATrainer:
    global _global_edge
    with _edge_lock:
        if _global_edge is None:
            _global_edge = OfflineLoRATrainer()
        return _global_edge


def reset_edge_trainer() -> None:
    global _global_edge
    with _edge_lock:
        _global_edge = None
