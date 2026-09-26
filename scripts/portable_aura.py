#!/usr/bin/env python3
"""
AURA Portable — Entorno portátil de AURA que se ejecuta desde cualquier directorio
sin instalación previa, ideal para USB, servidores remotos o dispositivos secundarios.

Funcionalidades:
  - Detección automática de entorno portable
  - Bootstrap de dependencias mínimas
  - Arranque de AURA en modo standalone
  - Sincronización opcional con instancia principal
  - Modo offline con modelo embebido

Uso:
  python scripts/portable_aura.py --auto
  python scripts/portable_aura.py --train
  python scripts/portable_aura.py --sync --with MAIN-INSTANCE-ID
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PortableAura")

REPO_ROOT = Path(__file__).resolve().parent.parent
PORTABLE_MARKER = REPO_ROOT / ".aura_portable"
PORTABLE_CONFIG = REPO_ROOT / "portable_config.json"


class PortableAura:
    """Gestiona el entorno portable de AURA."""

    def __init__(self):
        self.is_portable = PORTABLE_MARKER.exists()
        self.config: Dict = self._load_config()
        self.instance_id = self.config.get("instance_id", self._generate_instance_id())
        self.linked_to = self.config.get("linked_to")

    def _generate_instance_id(self) -> str:
        import secrets
        return "aura-portable-" + secrets.token_hex(4)

    def _load_config(self) -> Dict:
        if PORTABLE_CONFIG.exists():
            try:
                return json.loads(PORTABLE_CONFIG.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def save_config(self) -> None:
        PORTABLE_CONFIG.write_text(
            json.dumps(self.config, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def initialize(self, model_key: str = "qwen-0.5b") -> None:
        logger.info("Initializing portable AURA...")

        PORTABLE_MARKER.write_text(f"instance_id={self.instance_id}\n")

        dirs = ["models", "fine-tuned-ame", "training-data", "logs", "sync"]
        for d in dirs:
            (REPO_ROOT / d).mkdir(parents=True, exist_ok=True)

        self.config.update({
            "instance_id": self.instance_id,
            "model_key": model_key,
            "platform": platform.system(),
            "initialized": True,
        })
        self.save_config()
        logger.info(f"Portable AURA initialized: {self.instance_id}")

    def bootstrap(self) -> bool:
        logger.info("Bootstrapping portable environment...")
        python_exe = sys.executable

        try:
            import torch
            import transformers
            import peft
            import datasets
            logger.info("Core dependencies already available")
            return True
        except ImportError:
            logger.info("Installing minimal dependencies...")
            deps = [
                "torch>=2.1.0",
                "transformers>=4.40.0",
                "peft>=0.10.0",
                "datasets>=2.19.0",
                "accelerate>=0.30.0",
                "huggingface-hub>=0.23.0",
                "numpy>=1.26.0",
            ]
            import subprocess
            for dep in deps:
                logger.info(f"Installing {dep}")
                subprocess.run([python_exe, "-m", "pip", "install", dep], check=False)
            return True
        except Exception as e:
            logger.error(f"Bootstrap failed: {e}")
            return False

    def run_auto(self) -> None:
        if not self.is_portable:
            self.initialize()
        if not self.bootstrap():
            logger.error("Cannot bootstrap dependencies")
            return

        logger.info(f"Starting AURA Portable [{self.instance_id}]")
        try:
            from aura_autonomous_trainer import AutonomousTrainer, TrainingConfig
            config = TrainingConfig(
                model_path=f"models/{self.config.get('model_key', 'qwen-0.5b')}",
                output_dir="fine-tuned-ame",
                auto_collect=True,
                web_search=False,
                use_ui_data=True,
                use_reasoning_data=True,
                use_task_data=True,
                use_search_data=True,
                use_device_data=True,
            )
            trainer = AutonomousTrainer(config)
            results = trainer.run_automatic()
            logger.info(f"Training complete: {results.get('final_model')}")
        except Exception as e:
            logger.error(f"Auto mode failed: {e}")

    def run_train(self) -> None:
        if not self.is_portable:
            self.initialize()
        self.bootstrap()
        logger.info("Starting training only...")
        try:
            from aura_autonomous_trainer import AutonomousTrainer, TrainingConfig
            config = TrainingConfig(
                model_path=f"models/{self.config.get('model_key', 'qwen-0.5b')}",
                output_dir="fine-tuned-ame",
                auto_collect=False,
            )
            trainer = AutonomousTrainer(config)
            data_path = str(REPO_ROOT / "training-data-collected.jsonl")
            if (REPO_ROOT / "training-data-collected.jsonl").exists():
                output = trainer.trainer.train(data_path)
                logger.info(f"Training complete: {output}")
            else:
                logger.error("No training data found. Run --auto first.")
        except Exception as e:
            logger.error(f"Training failed: {e}")

    def sync_with(self, other_instance_id: str, sync_dir: Optional[Path] = None) -> None:
        sync_path = sync_dir or (REPO_ROOT / "sync")
        sync_path.mkdir(parents=True, exist_ok=True)

        manifest = {
            "instance_id": self.instance_id,
            "linked_to": other_instance_id,
            "platform": platform.system(),
            "model_key": self.config.get("model_key"),
            "datasets": {},
            "timestamp": __import__("datetime").datetime.now().isoformat(),
        }

        for name in ["training-data.jsonl", "training-data-reasoning.jsonl", "training-data-tasks.jsonl",
                      "training-data-search.jsonl", "training-data-device.jsonl"]:
            p = REPO_ROOT / name
            if p.exists():
                manifest["datasets"][name] = {
                    "path": str(p),
                    "size": p.stat().st_size,
                    "lines": sum(1 for _ in open(p, "r", encoding="utf-8")),
                }

        manifest_path = sync_path / f"sync_{self.instance_id}_{__import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"Sync manifest created: {manifest_path}")
        self.linked_to = other_instance_id
        self.config["linked_to"] = other_instance_id
        self.save_config()

    def status(self) -> Dict:
        return {
            "instance_id": self.instance_id,
            "is_portable": self.is_portable,
            "linked_to": self.linked_to,
            "platform": platform.system(),
            "repo_root": str(REPO_ROOT),
            "config": self.config,
        }


def main() -> None:
    p = argparse.ArgumentParser(description="AURA Portable")
    p.add_argument("--auto", action="store_true", help="Pipeline autónomo completo")
    p.add_argument("--train", action="store_true", help="Solo entrenar")
    p.add_argument("--sync", action="store_true", help="Sincronizar con otra instancia")
    p.add_argument("--with", dest="sync_with", type=str, default=None, help="ID de instancia para sincronizar")
    p.add_argument("--init", action="store_true", help="Inicializar entorno portable")
    p.add_argument("--status", action="store_true", help="Mostrar estado")
    args = p.parse_args()

    aura = PortableAura()

    if args.status:
        print(json.dumps(aura.status(), indent=2, ensure_ascii=False))
        return

    if args.init:
        aura.initialize()
        return

    if args.sync and args.sync_with:
        aura.sync_with(args.sync_with)
        return

    if args.auto:
        aura.run_auto()
        return

    if args.train:
        aura.run_train()
        return

    p.print_help()


if __name__ == "__main__":
    main()
