"""
Continual Trainer for AURA Small Model.

Workflow:
1. Read interaction logs from SmartAIRouter (JSONL).
2. Filter high-quality pairs (cloud responses, high complexity, short latency).
3. Optionally validate/augment with external API for correctness.
4. Merge with existing synthetic/base dataset.
5. Run lightweight QLoRA fine-tuning on CPU (small rank, short sequences).
6. Export LoRA adapters for local inference.

Goal: Keep the small model improving without burning CPU for hours.
We do frequent, tiny updates instead of rare, huge trainings.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class TrainConfig:
    base_model: str = "Qwen/Qwen2.5-0.5B-Instruct"
    dataset_path: str = "training/data/continual_dataset.jsonl"
    output_dir: str = "fine-tuned-ame"
    lora_r: int = 4
    lora_alpha: int = 16
    lora_dropout: float = 0.05
    max_seq_length: int = 256
    batch_size: int = 1
    gradient_accumulation_steps: int = 4
    num_epochs: int = 1
    learning_rate: float = 2e-4
    warmup_steps: int = 3
    load_in_4bit: bool = True
    device: str = "cpu"
    seed: int = 3407


class ContinualTrainer:
    def __init__(self, cfg: Optional[TrainConfig] = None) -> None:
        self.cfg = cfg or TrainConfig()
        self.log_path = "training/data/interactions.jsonl"
        self.synthetic_path = "training/data/synthetic_generated.jsonl"
        self.training_dir = Path("training/scripts")
        self.train_script = self.training_dir / "train_aura_light.py"

    def build_dataset(self, min_complexity: str = "medium", max_samples: int = 500) -> str:
        pairs: List[Dict[str, str]] = []
        levels = {"low": 0, "medium": 1, "high": 2}
        min_level = levels.get(min_complexity, 1)

        for source in [self.synthetic_path, self.log_path]:
            if not os.path.exists(source):
                continue
            with open(source, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    text = obj.get("text") or obj.get("prompt")
                    output = obj.get("output") or obj.get("response")
                    complexity = obj.get("complexity", "medium")
                    if not text or not output:
                        continue
                    if levels.get(complexity, 1) < min_level:
                        continue
                    if len(output.split()) < 5 or len(output) > 2000:
                        continue
                    pairs.append({"text": text, "output": output})
                    if len(pairs) >= max_samples:
                        break
            if len(pairs) >= max_samples:
                break

        # Deduplicate by output
        seen = set()
        unique = []
        for p in pairs:
            key = p["output"].strip().lower()
            if key not in seen:
                seen.add(key)
                unique.append(p)

        out_path = self.cfg.dataset_path
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            for p in unique:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
        print(f"[continual] Dataset built: {len(unique)} samples -> {out_path}")
        return out_path

    def run_training(self, dataset_path: Optional[str] = None) -> bool:
        dataset_path = dataset_path or self.cfg.dataset_path
        if not os.path.exists(dataset_path):
            print(f"[continual] Dataset not found: {dataset_path}")
            return False

        if not self.train_script.exists():
            print(f"[continual] Missing training script: {self.train_script}")
            return False

        env = os.environ.copy()
        env.update({
            "AURA_TRAINING_MODEL_NAME": self.cfg.base_model,
            "AURA_TRAINING_DATASET_PATH": dataset_path,
            "AURA_TRAINING_OUTPUT_DIR": self.cfg.output_dir,
        })

        print(f"[continual] Starting training on {self.cfg.device}...")
        start = time.time()
        try:
            proc = subprocess.run(
                [sys.executable, str(self.train_script)],
                env=env,
                cwd=str(Path(".").resolve()),
                capture_output=True,
                text=True,
            )
            print(proc.stdout)
            if proc.returncode != 0:
                print("[continual] Training failed:")
                print(proc.stderr)
                return False
        except Exception as exc:
            print(f"[continual] Training exception: {exc}")
            return False

        elapsed = time.time() - start
        print(f"[continual] Training finished in {elapsed:.1f}s")
        return True

    def merge_with_base(self, base_dataset: str = "training-data.jsonl") -> str:
        if not os.path.exists(self.cfg.dataset_path):
            return base_dataset
        merged_path = "training/data/merged_training.jsonl"
        seen = set()
        with open(merged_path, "w", encoding="utf-8") as out:
            for src in [base_dataset, self.cfg.dataset_path]:
                if not os.path.exists(src):
                    continue
                with open(src, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        key = (obj.get("text", "") + "|||" + obj.get("output", "")).strip().lower()
                        if key in seen:
                            continue
                        seen.add(key)
                        out.write(json.dumps(obj, ensure_ascii=False) + "\n")
        print(f"[continual] Merged dataset -> {merged_path} ({len(seen)} unique samples)")
        return merged_path


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Continual Trainer")
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--train-only", action="store_true")
    parser.add_argument("--merge", action="store_true")
    parser.add_argument("--min-complexity", default="medium")
    parser.add_argument("--max-samples", type=int, default=500)
    parser.add_argument("--epochs", type=int, default=1)
    args = parser.parse_args()

    trainer = ContinualTrainer()

    if args.merge:
        trainer.merge_with_base()
        return 0

    dataset_path = trainer.build_dataset(min_complexity=args.min_complexity, max_samples=args.max_samples)
    if args.build_only:
        return 0

    trainer.cfg.num_epochs = args.epochs
    ok = trainer.run_training(dataset_path)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
