"""
Backup y versionado de modelos AURA.

Copia fine-tuned-ame/aura_finetuned_lora/ a fine-tuned-ame/backups/aura_finetuned_lora_<timestamp>/.
Mantiene solo los últimos 5 backups. Registra historial en manifest.json.

Uso:
    python training/scripts/backup_model.py
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backup_model")

ROOT = Path(__file__).resolve().parents[2]
LORA_DIR = ROOT / "fine-tuned-ame" / "aura_finetuned_lora"
BACKUP_DIR = ROOT / "fine-tuned-ame" / "backups"
MANIFEST_PATH = BACKUP_DIR / "manifest.json"
MAX_BACKUPS = 5


def load_manifest() -> List[Dict[str, Any]]:
    """Carga el manifiesto de backups."""
    if not MANIFEST_PATH.exists():
        return []
    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("backups", []) if isinstance(data, dict) else []
    except Exception:
        return []


def save_manifest(backups: List[Dict[str, Any]]) -> None:
    """Guarda el manifiesto de backups."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump({"backups": backups}, f, ensure_ascii=False, indent=2)


def prune_backups(backups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Mantiene solo los últimos MAX_BACKUPS backups."""
    if len(backups) <= MAX_BACKUPS:
        return backups
    # Ordenar por timestamp descendente
    sorted_backups = sorted(backups, key=lambda b: b.get("timestamp", ""), reverse=True)
    to_keep = sorted_backups[:MAX_BACKUPS]
    to_delete = sorted_backups[MAX_BACKUPS:]

    for entry in to_delete:
        backup_path = BACKUP_DIR / entry["name"]
        try:
            if backup_path.exists():
                shutil.rmtree(backup_path)
                logger.info("Eliminado backup antiguo: %s", entry["name"])
        except Exception as exc:
            logger.error("No se pudo eliminar %s: %s", backup_path, exc)

    return to_keep


def backup() -> int:
    """Ejecuta el backup del modelo LoRA."""
    if not LORA_DIR.exists():
        logger.error("No existe el directorio LoRA: %s", LORA_DIR)
        return 1

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"aura_finetuned_lora_{timestamp}"
    backup_path = BACKUP_DIR / backup_name

    logger.info("Iniciando backup: %s", backup_name)

    try:
        shutil.copytree(LORA_DIR, backup_path, dirs_exist_ok=True)
        logger.info("Backup completado en: %s", backup_path)
    except Exception as exc:
        logger.error("Fallo en backup: %s", exc)
        return 1

    # Actualizar manifiesto
    backups = load_manifest()
    backups.append({
        "name": backup_name,
        "timestamp": datetime.now().isoformat(),
        "path": str(backup_path),
        "files": len(list(backup_path.iterdir())),
    })
    pruned = prune_backups(backups)
    save_manifest(pruned)

    logger.info("Backups actuales: %d (max %d)", len(pruned), MAX_BACKUPS)
    return 0


def main() -> int:
    return backup()


if __name__ == "__main__":
    raise SystemExit(main())