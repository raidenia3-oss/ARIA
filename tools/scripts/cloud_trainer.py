#!/usr/bin/env python3
"""
AURA Cloud Trainer — Entrenamiento en la nube con múltiples proveedores.

Soporta:
  - RunPod (community/secure pods)
  - Modal (serverless GPU)
  - Local fallback

Uso:
  python scripts/cloud_trainer.py --provider runpod --gpu rt4090 --script scripts/finetune-model.py --args "--data training-data.jsonl --epochs 1 --test"
  python scripts/cloud_trainer.py --provider modal --gpu a100 --script scripts/aura_autonomous_trainer.py --args "auto --epochs 1 --test"
  python scripts/cloud_trainer.py --status
  python scripts/cloud_trainer.py --sync --direction upload
  python scripts/cloud_trainer.py --sync --direction download
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import platform
import random
import string
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CloudTrainer")

REPO_ROOT = Path(__file__).resolve().parent.parent
CLOUD_STATE_FILE = REPO_ROOT / "cloud_state.json"

PROVIDERS = {
    "runpod": {
        "name": "RunPod",
        "gpus": {
            "rt4090": {"id": "NVIDIA GeForce RTX 4090", "vram": "24GB", "price_hr": 0.34},
            "a100-40": {"id": "NVIDIA A100 40GB", "vram": "40GB", "price_hr": 1.19},
            "a100-80": {"id": "NVIDIA A100 80GB", "vram": "80GB", "price_hr": 1.89},
            "h100": {"id": "NVIDIA H100 80GB", "vram": "80GB", "price_hr": 2.39},
        },
    },
    "modal": {
        "name": "Modal",
        "gpus": {
            "t4": {"id": "T4", "vram": "16GB", "price_hr": 0.59},
            "l4": {"id": "L4", "vram": "24GB", "price_hr": 0.80},
            "a10": {"id": "A10", "vram": "24GB", "price_hr": 1.10},
            "a100-40": {"id": "A100 40GB", "vram": "40GB", "price_hr": 2.10},
            "a100-80": {"id": "A100 80GB", "vram": "80GB", "price_hr": 2.50},
            "h100": {"id": "H100", "vram": "80GB", "price_hr": 3.95},
        },
    },
}


class CloudState:
    """Persist provider selection and last job metadata."""

    def __init__(self, path: Path = CLOUD_STATE_FILE):
        self.path = path
        self.data: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                self.data = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


class RunPodClient:
    """Cliente mínimo para RunPod."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("RUNPOD_API_KEY", "")
        if not self.api_key:
            logger.warning("RUNPOD_API_KEY not set. RunPod features will be limited.")

    def estimate_cost(self, gpu: str, hours: float = 1.0) -> float:
        gpus = PROVIDERS.get("runpod", {}).get("gpus", {})
        info = gpus.get(gpu, {})
        return info.get("price_hr", 0.0) * hours

    def generate_pod_name(self) -> str:
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        return f"aura-train-{suffix}"

    def build_pod_command(self, gpu: str, script: str, script_args: str, image: str = "runpod/pytorch:2.1.0-cuda12.1-cudnn8-devel") -> List[str]:
        name = self.generate_pod_name()
        gpu_id = PROVIDERS.get("runpod", {}).get("gpus", {}).get(gpu, {}).get("id", gpu)
        return [
            "runpod", "pod", "create",
            "--name", name,
            "--image", image,
            "--gpu", gpu_id,
            "--env", "HF_HUB_DISABLE_SYMLINKS_WARNING=1",
            "--volume", str(REPO_ROOT / "cloud_work") + ":/workspace",
            "--command", f"bash -lc 'cd /workspace && python {script} {script_args}'",
        ]


class ModalClient:
    """Cliente mínimo para Modal."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("MODAL_TOKEN", "")
        if not self.token:
            logger.warning("MODAL_TOKEN not set. Modal features will be limited.")

    def estimate_cost(self, gpu: str, seconds: float = 3600.0) -> float:
        gpus = PROVIDERS.get("modal", {}).get("gpus", {})
        info = gpus.get(gpu, {})
        price_hr = info.get("price_hr", 0.0)
        return price_hr * (seconds / 3600.0)

    def generate_app_name(self) -> str:
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        return f"aura-train-{suffix}"


class CloudTrainer:
    """Orquestador de entrenamiento en la nube."""

    def __init__(self, provider: str = "runpod"):
        self.provider = provider.lower()
        self.state = CloudState()
        if self.provider == "runpod":
            self.client = RunPodClient()
        elif self.provider == "modal":
            self.client = ModalClient()
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def estimate(self, gpu: str, duration_hours: float = 1.0) -> Dict[str, Any]:
        provider_info = PROVIDERS.get(self.provider, {})
        gpus = provider_info.get("gpus", {})
        info = gpus.get(gpu, {})
        price_hr = info.get("price_hr", 0.0)
        cost = price_hr * duration_hours
        return {
            "provider": self.provider,
            "gpu": gpu,
            "gpu_name": info.get("id", gpu),
            "vram": info.get("vram", "?"),
            "price_hr": price_hr,
            "duration_hours": duration_hours,
            "estimated_cost": round(cost, 2),
            "currency": "USD",
        }

    def run(self, gpu: str, script: str, script_args: str, wait: bool = True) -> Dict[str, Any]:
        logger.info(f"Launching cloud training on {self.provider} with {gpu}")
        estimate = self.estimate(gpu, duration_hours=2.0)
        logger.info(f"Estimated cost: ${estimate['estimated_cost']} USD for ~2 hours")

        if self.provider == "runpod":
            return self._run_runpod(gpu, script, script_args, wait)
        elif self.provider == "modal":
            return self._run_modal(gpu, script, script_args, wait)
        return {"status": "error", "message": "Unsupported provider"}

    def _run_runpod(self, gpu: str, script: str, script_args: str, wait: bool) -> Dict[str, Any]:
        if not self.client.api_key:
            return {"status": "error", "message": "RUNPOD_API_KEY not set"}

        cmd = self.client.build_pod_command(gpu, script, script_args)
        logger.info(f"$ {' '.join(cmd)}")
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
            if proc.returncode != 0:
                return {"status": "error", "message": proc.stderr[:500]}

            pod_id = self._extract_pod_id(proc.stdout)
            self.state.set("runpod_pod_id", pod_id)
            self.state.set("runpod_status", "running")
            return {"status": "launched", "pod_id": pod_id, "provider": "runpod", "gpu": gpu}
        except FileNotFoundError:
            return self._runpod_fallback(gpu, script, script_args, wait)

    def _runpod_fallback(self, gpu: str, script: str, script_args: str, wait: bool) -> Dict[str, Any]:
        logger.warning("runpod CLI not found. Generating manual pod config.")
        gpu_id = PROVIDERS.get("runpod", {}).get("gpus", {}).get(gpu, {}).get("id", gpu)
        config = {
            "provider": "runpod",
            "gpu": gpu,
            "gpu_id": gpu_id,
            "script": script,
            "script_args": script_args,
            "estimated_cost_2h": self.estimate(gpu, 2.0)["estimated_cost"],
            "instructions": [
                "1. Go to https://www.runpod.io/console/pods",
                "2. Click 'Deploy' -> 'GPU Pod'",
                f"3. Select GPU: {gpu_id}",
                "4. Use image: runpod/pytorch:2.1.0-cuda12.1-cudnn8-devel",
                "5. Mount volume: " + str(REPO_ROOT / "cloud_work") + " -> /workspace",
                f"6. Command: python {script} {script_args}",
                "7. Set env: HF_HUB_DISABLE_SYMLINKS_WARNING=1",
            ],
        }
        config_path = REPO_ROOT / "cloud_work" / "runpod_deploy.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return {"status": "manual_required", "config": str(config_path), "provider": "runpod", "gpu": gpu}

    def _run_modal(self, gpu: str, script: str, script_args: str, wait: bool) -> Dict[str, Any]:
        if not self.client.token:
            return {"status": "error", "message": "MODAL_TOKEN not set"}

        gpu_id = PROVIDERS.get("modal", {}).get("gpus", {}).get(gpu, {}).get("id", gpu)
        app_name = self.client.generate_app_name()
        modal_script = REPO_ROOT / "cloud_work" / f"modal_{app_name}.py"
        modal_script.parent.mkdir(parents=True, exist_ok=True)
        code = f'''
import modal

app = modal.App("{app_name}")
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git")
    .pip_install("torch", "transformers", "peft", "datasets", "accelerate", "huggingface_hub")
)

@app.function(gpu="{gpu_id}", image=image, timeout=3600)
def train():
    import subprocess
    cmd = ["python", "{script}"] + "{script_args}".split()
    result = subprocess.run(cmd, capture_output=True, text=True, cwd="/workspace")
    return {{"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}}

if __name__ == "__main__":
    with app.run():
        train.remote()
'''
        with open(modal_script, "w", encoding="utf-8") as f:
            f.write(code)

        logger.info(f"Generated Modal script: {modal_script}")
        logger.info("To run:")
        logger.info(f"  modal deploy {modal_script}")
        logger.info(f"  modal run {modal_script}")

        return {
            "status": "generated",
            "provider": "modal",
            "gpu": gpu,
            "script": str(modal_script),
            "app_name": app_name,
        }

    def sync_datasets(self, direction: str = "upload") -> Dict[str, Any]:
        if self.provider == "runpod":
            return self._sync_runpod(direction)
        return {"status": "skipped", "message": f"Sync not implemented for {self.provider}"}

    def _sync_runpod(self, direction: str) -> Dict[str, Any]:
        work_dir = REPO_ROOT / "cloud_work"
        work_dir.mkdir(parents=True, exist_ok=True)
        if direction == "upload":
            datasets = list(REPO_ROOT.glob("training-data*.jsonl"))
            copied = 0
            for src in datasets:
                dst = work_dir / src.name
                dst.write_bytes(src.read_bytes())
                copied += 1
            logger.info(f"Synced {copied} datasets to cloud_work/")
            return {"status": "ok", "direction": "upload", "files": copied}
        elif direction == "download":
            src = work_dir / "fine-tuned-ame"
            dst = REPO_ROOT / "fine-tuned-ame"
            if src.exists():
                if dst.exists():
                    import shutil
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
                logger.info(f"Downloaded model from cloud_work/fine-tuned-ame to fine-tuned-ame/")
                return {"status": "ok", "direction": "download", "files": 1}
            return {"status": "empty", "message": "No model found in cloud_work/fine-tuned-ame"}
        return {"status": "error", "message": f"Unknown direction: {direction}"}

    def status(self) -> Dict[str, Any]:
        state_data = {
            "provider": self.provider,
            "last_job": self.state.get("runpod_status") or self.state.get("modal_status"),
            "pod_id": self.state.get("runpod_pod_id"),
            "app_name": self.state.get("modal_app_name"),
            "estimated_rt4090_2h": self.estimate("rt4090", 2.0)["estimated_cost"] if self.provider == "runpod" else None,
            "estimated_a100_2h": self.estimate("a100-80", 2.0)["estimated_cost"] if self.provider == "runpod" else None,
        }
        return state_data

    def _extract_pod_id(self, stdout: str) -> Optional[str]:
        for line in stdout.splitlines():
            if "pod" in line.lower() and len(line.strip()) > 5:
                return line.strip()
        return "unknown"


def main() -> None:
    p = argparse.ArgumentParser(description="AURA Cloud Trainer")
    p.add_argument("--provider", type=str, default="runpod", choices=["runpod", "modal"])
    p.add_argument("--gpu", type=str, default="rt4090")
    p.add_argument("--script", type=str, default="scripts/finetune-model.py")
    p.add_argument("--args", type=str, default="")
    p.add_argument("--status", action="store_true")
    p.add_argument("--sync", action="store_true")
    p.add_argument("--direction", type=str, default="upload", choices=["upload", "download"])
    args = p.parse_args()

    trainer = CloudTrainer(provider=args.provider)

    if args.status:
        status = trainer.status()
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return

    if args.sync:
        result = trainer.sync_datasets(direction=args.direction)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    result = trainer.run(gpu=args.gpu, script=args.script, script_args=args.args)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
