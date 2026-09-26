#!/usr/bin/env python3
"""
AURA Evolution Loop — Orquestador del ciclo continuo de automejora.

Ciclo:
  1. Recolectar/mejorar datasets (todos los módulos)
  2. Entrenar modelo (aura_autonomous_trainer / finetune-model)
  3. Evaluar rendimiento real (ModelEvaluator)
  4. Detectar debilidades (SelfEvolution)
  5. Generar datasets focalizados (training_evolution + self_evolution)
  6. Reentrenar con datasets mejorados
  7. Medir mejora iterativa
  8. Guardar histórico y modelo final
  9. Repetir hasta alcanzar target_accuracy

Uso:
  python scripts/aura_evolution_loop.py --target-accuracy 0.75 --max-cycles 5
  python scripts/aura_evolution_loop.py --fast --target-accuracy 0.65
  python scripts/aura_evolution_loop.py --resume
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import random
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EvolutionLoop")

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_BASE = REPO_ROOT / "fine-tuned-ame"
METRICS_FILE = OUTPUT_BASE / "training_metrics.json"
EVOLUTION_HISTORY = REPO_ROOT / "evolution_history.jsonl"
CYCLE_HISTORY = REPO_ROOT / "cycle_history.jsonl"
BEST_MODEL_LINK = OUTPUT_BASE / "best_model"

DEFAULT_DATASETS = [
    "training-data.jsonl",
    "training-data-ui.jsonl",
    "training-data-web.jsonl",
    "training-data-collected.jsonl",
    "training-data-reasoning.jsonl",
    "training-data-tasks.jsonl",
    "training-data-search.jsonl",
    "training-data-device.jsonl",
    "training-data-voice.jsonl",
    "training-data-system.jsonl",
    "training-data-memory.jsonl",
    "training-data-portable.jsonl",
    "training-data-sync.jsonl",
    "training-data-deployment.jsonl",
    "training-data-vision.jsonl",
    "training-data-screen.jsonl",
    "training-data-persuasion.jsonl",
    "training-data-emotional.jsonl",
    "training-data-evolved.jsonl",
    "training-data-self_evolved.jsonl",
]


def run(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    logger.info(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def load_jsonl(path: Path) -> List[Dict]:
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


def append_jsonl(path: Path, items: List[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if path.exists() else "w"
    with open(path, mode, encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


class EvolutionLoop:
    """Ciclo continuo de evolución del modelo."""

    def __init__(
        self,
        target_accuracy: float = 0.75,
        max_cycles: int = 5,
        fast: bool = False,
        resume: bool = False,
        cloud: bool = False,
        cloud_provider: str = "runpod",
        cloud_gpu: str = "rt4090",
        idle_wait: bool = False,
    ):
        self.target_accuracy = target_accuracy
        self.max_cycles = max_cycles
        self.fast = fast
        self.resume = resume
        self.cloud = cloud
        self.cloud_provider = cloud_provider
        self.cloud_gpu = cloud_gpu
        self.idle_wait = idle_wait
        self.venv = REPO_ROOT / "venv-training" / "Scripts" / "python.exe"
        if not self.venv.exists():
            self.venv = Path(sys.executable)
        self.history: List[Dict] = []
        self.best_accuracy = 0.0
        self.best_model = None
        self._load_history()

    def _load_history(self) -> None:
        if self.resume and CYCLE_HISTORY.exists():
            with open(CYCLE_HISTORY, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            self.history.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            if self.history:
                self.best_accuracy = max((h.get("accuracy", 0) for h in self.history), default=0.0)
                self.best_model = self.history[-1].get("model_path")

    def _save_cycle(self, cycle: Dict) -> None:
        append_jsonl(CYCLE_HISTORY, [cycle])
        if cycle.get("accuracy", 0) > self.best_accuracy:
            self.best_accuracy = cycle["accuracy"]
            self.best_model = cycle.get("model_path")
            if self.best_model and Path(self.best_model).exists():
                if BEST_MODEL_LINK.exists():
                    BEST_MODEL_LINK.unlink()
                BEST_MODEL_LINK.symlink_to(Path(self.best_model).resolve())

    def run(self) -> Dict[str, Any]:
        logger.info("=" * 60)
        logger.info("  AURA EVOLUTION LOOP")
        logger.info(f"  Target accuracy: {self.target_accuracy}")
        logger.info(f"  Max cycles: {self.max_cycles}")
        logger.info("=" * 60)

        start_time = time.time()
        final_results = {
            "start_time": datetime.now().isoformat(),
            "target_accuracy": self.target_accuracy,
            "max_cycles": self.max_cycles,
            "cycles": [],
            "best_accuracy": self.best_accuracy,
            "best_model": self.best_model,
            "status": "running",
        }

        for cycle_num in range(1, self.max_cycles + 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"  CYCLE {cycle_num}/{self.max_cycles}")
            logger.info(f"{'='*60}")

            cycle_start = time.time()
            cycle = self._run_cycle(cycle_num)
            cycle["cycle"] = cycle_num
            cycle["elapsed_sec"] = round(time.time() - cycle_start, 1)
            cycle["timestamp"] = datetime.now().isoformat()

            self.history.append(cycle)
            self._save_cycle(cycle)
            final_results["cycles"].append(cycle)

            accuracy = cycle.get("accuracy", 0)
            logger.info(
                f"Cycle {cycle_num} done: accuracy={accuracy:.2%}, "
                f"model={cycle.get('model_path')}, time={cycle['elapsed_sec']}s"
            )

            if accuracy >= self.target_accuracy:
                logger.info(f"✅ Target accuracy reached: {accuracy:.2%} >= {self.target_accuracy:.2%}")
                final_results["status"] = "completed"
                final_results["best_accuracy"] = accuracy
                final_results["best_model"] = cycle.get("model_path")
                break

            if cycle_num == self.max_cycles:
                final_results["status"] = "max_cycles_reached"
                logger.info(f"⚠️ Max cycles reached. Best accuracy: {self.best_accuracy:.2%}")

        final_results["end_time"] = datetime.now().isoformat()
        final_results["total_elapsed_sec"] = round(time.time() - start_time, 1)
        final_results["best_accuracy"] = self.best_accuracy
        final_results["best_model"] = str(self.best_model) if self.best_model else None

        self._save_final_report(final_results)
        return final_results

    def _run_cycle(self, cycle_num: int) -> Dict[str, Any]:
        cycle: Dict[str, Any] = {"cycle": cycle_num}
        base_data = REPO_ROOT / "training-data-collected.jsonl"
        if not base_data.exists():
            base_data = REPO_ROOT / "training-data.jsonl"

        # 1. Regenerar datasets sintéticos si es cycle 1 o si accuracy es baja
        if cycle_num == 1 or self.best_accuracy < self.target_accuracy:
            logger.info("[1/6] Regenerating evolved datasets...")
            evolved = self._regenerate_evolved(base_data)
            cycle["evolved_samples"] = evolved

        # 2. Autoevolución focalizada
        logger.info("[2/6] Running self-evolution...")
        evo_result = self._run_self_evolution(base_data, cycle_num)
        cycle["evolution"] = evo_result

        # 3. Entrenar
        logger.info("[3/6] Training model...")
        train_result = self._run_training(base_data, cycle_num)
        cycle["model_path"] = train_result.get("model_path")
        cycle["training_metrics"] = train_result.get("metrics", {})

        # 4. Evaluar
        logger.info("[4/6] Evaluating model...")
        eval_metrics = self._run_evaluation(cycle.get("model_path"))
        cycle["evaluation"] = eval_metrics
        cycle["accuracy"] = eval_metrics.get("qa_accuracy", 0)

        # 5. Si accuracy baja, expandir datasets
        if cycle["accuracy"] < self.target_accuracy:
            logger.info("[5/6] Expanding datasets with weak areas...")
            expanded = self._expand_weak_areas(eval_metrics, base_data)
            cycle["expanded_samples"] = expanded
        else:
            cycle["expanded_samples"] = 0

        # 6. Guardar ciclo
        cycle["dataset_count"] = count_jsonl(base_data)
        return cycle

    def _regenerate_evolved(self, base_data: Path) -> int:
        try:
            result = run([
                str(self.venv), str(REPO_ROOT / "scripts" / "training_evolution.py"),
                "--base", str(base_data),
                "--count", "80" if not self.fast else "40",
                "--output", str(REPO_ROOT / "training-data-evolved.jsonl"),
                "--personalities", "scientist,poet,professor,storyteller,friend,technician",
            ])
            if result.returncode != 0:
                logger.warning(f"training_evolution failed: {result.stderr[:300]}")
                return 0
            return count_jsonl(REPO_ROOT / "training-data-evolved.jsonl")
        except Exception as e:
            logger.warning(f"Evolved regeneration failed: {e}")
            return 0

    def _run_self_evolution(self, base_data: Path, cycle_num: int) -> Dict[str, Any]:
        try:
            result = run([
                str(self.venv), str(REPO_ROOT / "scripts" / "self_evolution.py"),
                "evolve",
                "--dataset", str(base_data),
                "--iterations", "1",
                "--count", "40" if not self.fast else "20",
            ])
            if result.returncode != 0:
                logger.warning(f"self_evolution failed: {result.stderr[:300]}")
                return {"status": "failed"}
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                return {"status": "ok", "raw": result.stdout[:200]}
        except Exception as e:
            logger.warning(f"Self evolution failed: {e}")
            return {"status": "error", "message": str(e)}

    def _run_training(self, data_path: Path, cycle_num: int) -> Dict[str, Any]:
        if self.cloud:
            return self._run_training_cloud(data_path, cycle_num)
        return self._run_training_local(data_path, cycle_num)

    def _run_training_local(self, data_path: Path, cycle_num: int) -> Dict[str, Any]:
        output_dir = OUTPUT_BASE / f"cycle-{cycle_num}"
        output_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            str(self.venv), str(REPO_ROOT / "scripts" / "aura_autonomous_trainer.py"),
            "auto",
            "--model-path", "models/qwen-1.5b",
            "--output", str(output_dir),
            "--epochs", "1" if self.fast else "2",
            "--lr", "8e-5",
            "--batch-size", "2" if self.fast else "4",
            "--max-length", "256" if self.fast else "512",
            "--max-collections", "1",
            "--no-web-search",
        ]
        if self.fast:
            cmd.append("--test")
        result = run(cmd, cwd=REPO_ROOT)
        if result.returncode != 0:
            logger.warning(f"Training failed: rc={result.returncode}")
            return {"status": "failed", "stderr": result.stderr[:500]}

        metrics_path = output_dir / "autonomous_training_config.json"
        if metrics_path.exists():
            with open(metrics_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            return {
                "status": "ok",
                "model_path": str(output_dir),
                "metrics": config_data.get("final_metrics", {}),
            }
        return {"status": "ok", "model_path": str(output_dir), "metrics": {}}

    def _run_training_cloud(self, data_path: Path, cycle_num: int) -> Dict[str, Any]:
        try:
            from cloud_trainer import CloudTrainer
            from cloud_sync import sync_to_cloud
            from idle_detector import IdleDetector

            if self.idle_wait:
                detector = IdleDetector()
                logger.info("Waiting for system idle before cloud training...")
                while not detector.is_idle()["is_idle"]:
                    logger.info("System active, waiting 60s...")
                    time.sleep(60)

            sync_result = sync_to_cloud()
            logger.info(f"Sync to cloud: {sync_result.get('status')}")

            trainer = CloudTrainer(provider=self.cloud_provider)
            script_args = (
                f"auto --model-path models/qwen-1.5b --output fine-tuned-ame/cycle-{cycle_num} "
                f"--epochs 1 --lr 8e-5 --batch-size 2 --max-length 256 --max-collections 1 --no-web-search --test"
            )
            result = trainer.run(
                gpu=self.cloud_gpu,
                script="scripts/aura_autonomous_trainer.py",
                script_args=script_args,
            )
            logger.info(f"Cloud training launched: {result}")
            return {
                "status": "cloud_launched",
                "cloud_provider": self.cloud_provider,
                "cloud_gpu": self.cloud_gpu,
                "cycle_num": cycle_num,
                "cloud_result": result,
                "sync": sync_result,
            }
        except Exception as e:
            logger.warning(f"Cloud training failed: {e}")
            return {"status": "cloud_failed", "error": str(e)}

    def _run_evaluation(self, model_path: Optional[str]) -> Dict[str, Any]:
        if not model_path or not Path(model_path).exists():
            return {"qa_accuracy": 0, "perplexity": float("inf"), "status": "no_model"}
        try:
            result = run([
                str(self.venv), str(REPO_ROOT / "scripts" / "aura_autonomous_trainer.py"),
                "evaluate",
                "--model", model_path,
                "--model-path", "models/qwen-1.5b",
            ])
            if result.returncode != 0:
                logger.warning(f"Evaluation failed: {result.stderr[:300]}")
                return {"qa_accuracy": 0, "perplexity": float("inf"), "status": "error"}
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                return {"qa_accuracy": 0, "perplexity": float("inf"), "status": "parse_error"}
        except Exception as e:
            logger.warning(f"Evaluation error: {e}")
            return {"qa_accuracy": 0, "perplexity": float("inf"), "status": "exception"}

    def _expand_weak_areas(self, eval_metrics: Dict, base_data: Path) -> int:
        # Expandir con datos de personalidad y emocionales si la accuracy es baja
        try:
            result = run([
                str(self.venv), str(REPO_ROOT / "scripts" / "training_evolution.py"),
                "--base", str(base_data),
                "--count", "60" if not self.fast else "30",
                "--output", str(REPO_ROOT / "training-data-evolved.jsonl"),
                "--personalities", "scientist,professor,technician",
                "--no-difficult",
            ])
            if result.returncode == 0:
                return count_jsonl(REPO_ROOT / "training-data-evolved.jsonl")
        except Exception as e:
            logger.warning(f"Weak area expansion failed: {e}")
        return 0

    def _save_final_report(self, results: Dict) -> None:
        report_path = OUTPUT_BASE / "evolution_loop_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"Final report saved: {report_path}")


def main() -> None:
    p = argparse.ArgumentParser(description="AURA Evolution Loop")
    p.add_argument("--target-accuracy", type=float, default=0.75, help="Objetivo de accuracy")
    p.add_argument("--max-cycles", type=int, default=5, help="Ciclos máximos")
    p.add_argument("--fast", action="store_true", help="Modo rápido (menos datos, menos epochs)")
    p.add_argument("--resume", action="store_true", help="Reanudar desde último ciclo")
    p.add_argument("--cloud", action="store_true", help="Entrenar en la nube (RunPod/Modal)")
    p.add_argument("--provider", type=str, default="runpod", choices=["runpod", "modal"])
    p.add_argument("--gpu", type=str, default="rt4090")
    p.add_argument("--idle-wait", action="store_true", help="Esperar a que la PC esté inactiva antes de entrenar")
    args = p.parse_args()

    loop = EvolutionLoop(
        target_accuracy=args.target_accuracy,
        max_cycles=args.max_cycles,
        fast=args.fast,
        resume=args.resume,
        cloud=args.cloud,
        cloud_provider=args.provider,
        cloud_gpu=args.gpu,
        idle_wait=args.idle_wait,
    )
    results = loop.run()

    print(f"\n{'='*60}")
    print(f"  AURA EVOLUTION LOOP COMPLETED")
    print(f"{'='*60}")
    print(f"  Status:         {results['status']}")
    print(f"  Best accuracy:  {results['best_accuracy']:.2%}")
    print(f"  Best model:     {results['best_model']}")
    print(f"  Cycles:         {len(results['cycles'])}")
    print(f"  Total time:     {results.get('total_elapsed_sec', 0):.1f}s")
    print(f"  Report:         {OUTPUT_BASE / 'evolution_loop_report.json'}")


if __name__ == "__main__":
    main()
