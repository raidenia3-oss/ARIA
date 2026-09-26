#!/usr/bin/env python3
"""
AURA Self Evolution — Automejora y autoevolución del modelo.

Capacidades:
  - Autoevaluación de rendimiento en categorías de entrenamiento
  - Detección de debilidades (categorías con baja precisión simulada)
  - Generación de entrenamiento focalizado en debilidades
  - Medición de mejora iterativa entre ciclos
  - Ajuste automático de hiperparámetros según rendimiento
  - Historial de evoluciones con métricas
  - Recomendaciones de priorización de datasets
  - Simulación de fine-tuning incremental

Dataset: training-data-self_evolved.jsonl

Uso:
  python scripts/self_evolution.py --evaluate training-data.jsonl --category ocr
  python scripts/self_evolution.py --evolve --iterations 3 --target-accuracy 0.85
  python scripts/self_evolution.py --history
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import random
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SelfEvolution")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "training-data-self_evolved.jsonl"
EVOLUTION_HISTORY = REPO_ROOT / "evolution_history.jsonl"

WEAKNESS_THRESHOLD = 0.70
IMPROVEMENT_TARGET = 0.05
MAX_HYPERPARAMETER_ADJUSTMENTS = 5

HYPERPARAMETER_RANGES = {
    "lr": [1e-5, 3e-5, 5e-5, 8e-5, 1e-4, 2e-4],
    "lora_r": [4, 8, 16, 32, 64],
    "lora_alpha": [16, 32, 64, 128],
    "batch_size": [1, 2, 4, 8],
    "epochs": [1, 2, 3, 5, 8, 10],
}


class SelfEvolution:
    """Automejora y autoevolución del modelo."""

    def __init__(self):
        self.history: List[Dict] = []
        self.current_hyperparams = {
            "lr": 8e-5,
            "lora_r": 16,
            "lora_alpha": 64,
            "batch_size": 2,
            "epochs": 5,
        }
        self.category_scores: Dict[str, float] = {}

    def load_jsonl(self, path: Path) -> List[Dict]:
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

    def simulate_evaluate(self, items: List[Dict], category: Optional[str] = None) -> Dict[str, float]:
        scores = defaultdict(list)
        for item in items:
            cat = item.get("metadata", {}).get("category", "general")
            if category and cat != category:
                continue
            length = len(item.get("text", "")) + len(item.get("output", ""))
            base_score = min(1.0, 0.5 + (length / 2000.0) + random.uniform(-0.1, 0.1))
            scores[cat].append(base_score)
        result = {}
        for cat, vals in scores.items():
            result[cat] = round(sum(vals) / len(vals), 3) if vals else 0.0
        return result

    def evaluate(self, dataset_path: Path, category: Optional[str] = None) -> Dict[str, Any]:
        items = self.load_jsonl(dataset_path)
        if not items:
            return {"error": "No items found", "path": str(dataset_path)}
        scores = self.simulate_evaluate(items, category)
        overall = round(sum(scores.values()) / len(scores), 3) if scores else 0.0
        result = {
            "dataset": str(dataset_path),
            "category": category or "all",
            "overall_accuracy": overall,
            "category_scores": scores,
            "weaknesses": [cat for cat, score in scores.items() if score < WEAKNESS_THRESHOLD],
            "strengths": [cat for cat, score in scores.items() if score >= 0.85],
            "timestamp": datetime.now().isoformat(),
        }
        self.category_scores = scores
        logger.info(f"Evaluation: overall={overall}, weaknesses={result['weaknesses']}")
        return result

    def detect_weaknesses(self, evaluation: Dict) -> List[str]:
        return evaluation.get("weaknesses", [])

    def generate_focused_training(self, weaknesses: List[str], base_items: List[Dict], count: int = 50) -> List[Dict]:
        if not weaknesses:
            logger.info("No weaknesses detected. Generating general reinforcement.")
            weaknesses = ["general"]
        items = []
        per_weakness = max(1, count // len(weaknesses))
        for weakness in weaknesses:
            related = [i for i in base_items if i.get("metadata", {}).get("category", "general") == weakness]
            if not related:
                related = base_items
            for _ in range(per_weakness):
                base = random.choice(related)
                reinforced = {
                    "text": f"[Entrenamiento focalizado - {weakness}] {base.get('text', '')}",
                    "output": f"[Fortalecimiento de {weakness}]\n{base.get('output', '')}\n\nPuntos clave a recordar:\n1. [Punto crítico]\n2. [Punto crítico]\n3. [Punto crítico]",
                    "metadata": {
                        "source": "self_evolution",
                        "focus": weakness,
                        "reinforced": True,
                        "timestamp": datetime.now().isoformat(),
                    },
                }
                items.append(reinforced)
        return items[:count]

    def adjust_hyperparameters(self, evaluation: Dict) -> Dict[str, Any]:
        overall = evaluation.get("overall_accuracy", 0.0)
        adjustments = {}
        if overall < 0.60:
            adjustments["lr"] = self._closest(HYPERPARAMETER_RANGES["lr"], self.current_hyperparams["lr"] * 0.5)
            adjustments["epochs"] = self._closest(HYPERPARAMETER_RANGES["epochs"], self.current_hyperparams["epochs"] + 2)
            adjustments["batch_size"] = self._closest(HYPERPARAMETER_RANGES["batch_size"], max(1, self.current_hyperparams["batch_size"] - 1))
        elif overall < 0.75:
            adjustments["lr"] = self._closest(HYPERPARAMETER_RANGES["lr"], self.current_hyperparams["lr"] * 0.8)
            adjustments["lora_r"] = self._closest(HYPERPARAMETER_RANGES["lora_r"], self.current_hyperparams["lora_r"] * 2)
        elif overall > 0.90:
            adjustments["lr"] = self._closest(HYPERPARAMETER_RANGES["lr"], self.current_hyperparams["lr"] * 1.2)
            adjustments["epochs"] = max(1, self.current_hyperparams["epochs"] - 1)
        for key, value in adjustments.items():
            self.current_hyperparams[key] = value
        return {"adjustments": adjustments, "new_hyperparams": self.current_hyperparams}

    def _closest(self, options: List[Any], target: Any) -> Any:
        return min(options, key=lambda x: abs(x - target))

    def evolve(self, dataset_path: Path, iterations: int = 3, target_accuracy: float = 0.85, count: int = 50) -> Dict[str, Any]:
        base_items = self.load_jsonl(dataset_path)
        evolution_log = {
            "start_time": datetime.now().isoformat(),
            "iterations": iterations,
            "target_accuracy": target_accuracy,
            "cycles": [],
        }
        current_items = base_items[:]
        best_accuracy = 0.0
        best_items = current_items[:]
        for i in range(iterations):
            logger.info(f"Evolution cycle {i+1}/{iterations}")
            eval_result = self._evaluate_items(current_items)
            weaknesses = self.detect_weaknesses(eval_result)
            focused = self.generate_focused_training(weaknesses, base_items, count=count)
            current_items = current_items + focused
            if len(current_items) > 3000:
                current_items = current_items[-3000:]
            new_eval = self._evaluate_items(current_items)
            hp_adjust = self.adjust_hyperparameters(new_eval)
            cycle = {
                "cycle": i + 1,
                "accuracy_before": eval_result.get("overall_accuracy", 0.0),
                "accuracy_after": new_eval.get("overall_accuracy", 0.0),
                "weaknesses": weaknesses,
                "new_items": len(focused),
                "hyperparameters": hp_adjust,
                "timestamp": datetime.now().isoformat(),
            }
            evolution_log["cycles"].append(cycle)
            if new_eval.get("overall_accuracy", 0.0) > best_accuracy:
                best_accuracy = new_eval.get("overall_accuracy", 0.0)
                best_items = current_items[:]
            if new_eval.get("overall_accuracy", 0.0) >= target_accuracy:
                logger.info(f"Target accuracy {target_accuracy} reached at cycle {i+1}")
                break
        output_path = Path(DEFAULT_OUTPUT)
        mode = "a" if output_path.exists() else "w"
        with open(output_path, mode, encoding="utf-8") as f:
            for item in best_items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        with open(EVOLUTION_HISTORY, "a", encoding="utf-8") as f:
            f.write(json.dumps(evolution_log, ensure_ascii=False) + "\n")
        logger.info(f"Evolution complete. Best accuracy: {best_accuracy}. Items: {len(best_items)}")
        return {
            "best_accuracy": best_accuracy,
            "total_items": len(best_items),
            "cycles": evolution_log["cycles"],
            "final_hyperparams": self.current_hyperparams,
        }

    def _evaluate_items(self, items: List[Dict]) -> Dict[str, Any]:
        scores = self.simulate_evaluate(items)
        overall = round(sum(scores.values()) / len(scores), 3) if scores else 0.0
        return {
            "overall_accuracy": overall,
            "category_scores": scores,
            "weaknesses": [cat for cat, score in scores.items() if score < WEAKNESS_THRESHOLD],
            "strengths": [cat for cat, score in scores.items() if score >= 0.85],
        }

    def get_history(self, limit: int = 10) -> List[Dict]:
        entries = []
        if EVOLUTION_HISTORY.exists():
            with open(EVOLUTION_HISTORY, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        return entries[-limit:]


def cmd_evaluate(args: argparse.Namespace) -> None:
    evo = SelfEvolution()
    result = evo.evaluate(Path(args.dataset), category=args.category)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_evolve(args: argparse.Namespace) -> None:
    evo = SelfEvolution()
    result = evo.evolve(
        dataset_path=Path(args.dataset),
        iterations=args.iterations,
        target_accuracy=args.target_accuracy,
        count=args.count,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_history(args: argparse.Namespace) -> None:
    evo = SelfEvolution()
    entries = evo.get_history(limit=args.limit)
    for entry in entries:
        print(json.dumps(entry, indent=2, ensure_ascii=False))


def main() -> None:
    p = argparse.ArgumentParser(description="AURA Self Evolution")
    sub = p.add_subparsers(dest="command")

    s_eval = sub.add_parser("evaluate", help="Evaluar dataset")
    s_eval.add_argument("--dataset", type=str, required=True, help="Ruta del dataset")
    s_eval.add_argument("--category", type=str, default=None, help="Categoría específica")
    s_eval.set_defaults(func=cmd_evaluate)

    s_evolve = sub.add_parser("evolve", help="Ejecutar ciclo de autoevolución")
    s_evolve.add_argument("--dataset", type=str, required=True, help="Dataset base")
    s_evolve.add_argument("--iterations", type=int, default=3)
    s_evolve.add_argument("--target-accuracy", type=float, default=0.85)
    s_evolve.add_argument("--count", type=int, default=50)
    s_evolve.set_defaults(func=cmd_evolve)

    s_hist = sub.add_parser("history", help="Ver historial de evoluciones")
    s_hist.add_argument("--limit", type=int, default=10)
    s_hist.set_defaults(func=cmd_history)

    args = p.parse_args()
    if args.command is None:
        p.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
