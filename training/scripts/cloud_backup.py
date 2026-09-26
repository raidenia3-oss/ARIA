"""
Backup automático a Hugging Face Hub.

Sube fine-tuned-ame/aura_finetuned_lora/ a HF Hub (requiere HF_TOKEN).
Opcionalmente sube models/qwen-0.5b/ si se pasa --include-base.

Uso:
    python training/scripts/cloud_backup.py
    python training/scripts/cloud_backup.py --include-base
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cloud_backup")

ROOT = Path(__file__).resolve().parents[2]
LORA_DIR = ROOT / "fine-tuned-ame" / "aura_finetuned_lora"
MODEL_DIR = ROOT / "models" / "qwen-0.5b"
BACKUP_DIR = ROOT / "fine-tuned-ame" / "backups"
CLOUD_MANIFEST = BACKUP_DIR / "cloud_manifest.json"


def load_cloud_manifest() -> list:
    if not CLOUD_MANIFEST.exists():
        return []
    try:
        with open(CLOUD_MANIFEST, "r", encoding="utf-8") as f:
            return json.load(f).get("backups", [])
    except Exception:
        return []


def save_cloud_manifest(backups: list) -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    with open(CLOUD_MANIFEST, "w", encoding="utf-8") as f:
        json.dump({"backups": backups}, f, ensure_ascii=False, indent=2)


def upload_to_hf(local_path: Path, repo_id: str, token: str, path_in_repo: str) -> bool:
    try:
        from huggingface_hub import HfApi, upload_folder
    except ImportError:
        logger.error("huggingface_hub no instalado. Ejecuta: pip install huggingface_hub")
        return False

    api = HfApi(token=token)
    try:
        upload_folder(
            folder_path=str(local_path),
            repo_id=repo_id,
            repo_type="model",
            path_in_repo=path_in_repo,
            token=token,
        )
        return True
    except Exception as exc:
        logger.error("Fallo upload a HF Hub: %s", exc)
        return False


def cloud_backup(include_base: bool = False) -> int:
    token = os.getenv("HF_TOKEN")
    if not token:
        logger.warning("HF_TOKEN no configurado. Omitiendo backup en la nube.")
        return 0

    if not LORA_DIR.exists():
        logger.error("No existe LoRA en %s", LORA_DIR)
        return 1

    ts = datetime.now().isoformat()
    ok = upload_to_hf(
        local_path=LORA_DIR,
        repo_id=os.getenv("HF_USERNAME", "user") + "/aura-lora",
        token=token,
        path_in_repo=f"backups/{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    )
    if not ok:
        return 1

    manifest = load_cloud_manifest()
    manifest.append({
        "timestamp": ts,
        "type": "lora",
        "local_path": str(LORA_DIR),
    })

    if include_base and MODEL_DIR.exists():
        ok_base = upload_to_hf(
            local_path=MODEL_DIR,
            repo_id=os.getenv("HF_USERNAME", "user") + "/aura-base",
            token=token,
            path_in_repo="models/qwen-0.5b",
        )
        if ok_base:
            manifest.append({
                "timestamp": ts,
                "type": "base",
                "local_path": str(MODEL_DIR),
            })

    save_cloud_manifest(manifest)
    logger.info("Backup en la nube completado.")
    return 0


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Backup de modelos AURA a HF Hub")
    parser.add_argument("--include-base", action="store_true", help="Incluir modelo base")
    args = parser.parse_args()
    return cloud_backup(include_base=args.include_base)


if __name__ == "__main__":
    raise SystemExit(main())