#!/usr/bin/env python3
"""Run a training job for AURA.

Expected env/args:
- AURA_TRAINING_MODEL_NAME
- AURA_TRAINING_DATASET_PATH
- AURA_TRAINING_OUTPUT_DIR
- AURA_TRAINING_STATUS_FILE (optional JSON file path for status updates)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AURA training job")
    parser.add_argument("--model_name", default=os.getenv("AURA_TRAINING_MODEL_NAME", "Qwen/Qwen2.5-1.5B-Instruct"))
    parser.add_argument("--dataset_path", default=os.getenv("AURA_TRAINING_DATASET_PATH", "aura_merged_training.jsonl"))
    parser.add_argument("--output_dir", default=os.getenv("AURA_TRAINING_OUTPUT_DIR", "fine-tuned-ame"))
    parser.add_argument("--status_file", default=os.getenv("AURA_TRAINING_STATUS_FILE", ""))
    return parser.parse_args()


def write_status(status_file: str, payload: dict) -> None:
    if not status_file:
        return
    try:
        with open(status_file, "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except Exception:
        pass


def main() -> int:
    args = parse_args()
    write_status(args.status_file, {"status": "starting", "model_name": args.model_name, "dataset_path": args.dataset_path, "output_dir": args.output_dir, "started_at": time.time()})

    try:
        write_status(args.status_file, {"status": "running", "started_at": time.time()})
        import train_aura
        write_status(args.status_file, {"status": "finished", "finished_at": time.time(), "metrics": "ok"})
        return 0
    except Exception as exc:
        write_status(args.status_file, {"status": "failed", "finished_at": time.time(), "metrics": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(main())
