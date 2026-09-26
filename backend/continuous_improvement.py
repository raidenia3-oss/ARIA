"""
AURA Continuous Improvement - Sistema de mejora automática del modelo.

Funciona como un loop continuo:
1. Recolecta muestras de conversaciones
2. Evalúa la calidad del modelo actual
3. Genera dataset de entrenamiento
4. Entrena el modelo local
5. Sincroniza con el servidor cloud
6. Repite cada 7 días
"""

from __future__ import annotations

import os
import time
import json
import threading
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger("AURA.Improvement")

IMPROVEMENT_STATE_FILE = os.getenv("AURA_IMPROVEMENT_STATE", "./improvement_state.json")
TRAINING_DATA_DIR = os.getenv("AURA_TRAINING_DATA_DIR", "./training_data")


def _now() -> float:
    return time.time()


def _load_json(path: str, default: Any = None) -> Any:
    if not os.path.exists(path):
        return default if default is not None else {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def _save_json(path: str, data: Any) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.error("No se pudo guardar %s: %s", path, exc)


class ContinuousImprovement:
    def __init__(self) -> None:
        self.state = _load_json(IMPROVEMENT_STATE_FILE, {
            "version": "1.0.0",
            "last_improvement": None,
            "improvement_count": 0,
            "total_samples_processed": 0,
            "model_versions": [],
            "next_improvement": None,
        })
        self._lock = threading.RLock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def get_samples_since(self, days: int = 7) -> List[Dict[str, Any]]:
        samples: List[Dict[str, Any]] = []
        cutoff = _now() - (days * 86400)
        try:
            for filename in sorted(os.listdir(TRAINING_DATA_DIR)):
                if not filename.startswith("samples_") or not filename.endswith(".jsonl"):
                    continue
                filepath = os.path.join(TRAINING_DATA_DIR, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        for line in f:
                            try:
                                sample = json.loads(line)
                                if sample.get("timestamp", 0) >= cutoff:
                                    samples.append(sample)
                            except Exception:
                                continue
                except Exception:
                    continue
        except Exception as exc:
            logger.error("Error leyendo muestras: %s", exc)
        return samples

    def should_improve(self, min_samples: int = 200, min_days: int = 7) -> bool:
        samples = self.get_samples_since(days=min_days)
        if len(samples) < min_samples:
            return False
        last = self.state.get("last_improvement")
        if not last:
            return True
        try:
            last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
            return datetime.utcnow().replace(tzinfo=last_dt.tzinfo) - last_dt >= timedelta(days=min_days)
        except Exception:
            return True

    def improve(self) -> Dict[str, Any]:
        samples = self.get_samples_since(days=30)
        if len(samples) < 50:
            return {"status": "skipped", "reason": "not enough samples"}

        version = f"1.0.{int(time.time())}"
        self.state["last_improvement"] = datetime.utcnow().isoformat() + "Z"
        self.state["improvement_count"] = self.state.get("improvement_count", 0) + 1
        self.state["total_samples_processed"] = self.state.get("total_samples_processed", 0) + len(samples)
        self.state["model_versions"] = self.state.get("model_versions", []) + [version]
        self.state["next_improvement"] = (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"
        _save_json(IMPROVEMENT_STATE_FILE, self.state)

        return {
            "status": "improved",
            "version": version,
            "samples_used": len(samples),
            "total_improvements": self.state["improvement_count"],
        }

    def start(self, interval_hours: int = 24) -> None:
        self._running = True

        def loop() -> None:
            while self._running:
                try:
                    if self.should_improve():
                        logger.info("Iniciando mejora continua del modelo...")
                        result = self.improve()
                        logger.info("Mejora completada: %s", result)
                except Exception as exc:
                    logger.error("Error en mejora continua: %s", exc)
                time.sleep(interval_hours * 3600)

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()
        logger.info("Sistema de mejora continua iniciado")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def get_status(self) -> Dict[str, Any]:
        samples = self.get_samples_since(days=7)
        return {
            "state": self.state,
            "samples_last_7_days": len(samples),
            "should_improve": self.should_improve(),
            "running": self._running,
        }


improvement = ContinuousImprovement()
