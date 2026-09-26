"""
Monitor de entrenamiento y producción AURA.

Lee training/data/ y fine-tuned-ame/ y reporta:
- Último entrenamiento (fecha, epochs, samples)
- Cantidad de pares de alta calidad disponibles
- Sugerencia: "entrenar ahora" / "esperar más datos"

Uso:
    python training/scripts/monitor.py
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("monitor")

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "training" / "data"
OUTPUT = ROOT / "training" / "output"
LORA_DIR = ROOT / "fine-tuned-ame" / "aura_finetuned_lora"
BACKUP_DIR = ROOT / "fine-tuned-ame" / "backups"


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    if not path.exists():
        return records
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    records.append(obj)
            except json.JSONDecodeError:
                continue
    return records


def get_last_training() -> Dict[str, Any]:
    """Obtiene información del último entrenamiento."""
    report_path = OUTPUT / "orchestrator_report.json"
    report = load_json(report_path)
    if not report:
        return {"status": "no_data"}

    train_step = report.get("steps", {}).get("train", {})
    return {
        "status": "ok",
        "timestamp": report.get("timestamp"),
        "returncode": train_step.get("returncode"),
        "elapsed_s": train_step.get("elapsed_s"),
        "log": train_step.get("log"),
    }


def count_high_quality() -> int:
    """Cuenta pares de alta calidad exportados."""
    path = DATA / "high_quality_pairs.jsonl"
    records = load_jsonl(path)
    return len(records)


def count_feedback() -> Dict[str, int]:
    """Cuenta feedback positivo/negativo."""
    path = DATA / "feedback.jsonl"
    records = load_jsonl(path)
    up = sum(1 for r in records if r.get("feedback") == "up")
    down = sum(1 for r in records if r.get("feedback") == "down")
    return {"total": len(records), "up": up, "down": down}


def count_interactions() -> int:
    """Cuenta interacciones registradas."""
    path = DATA / "interactions.jsonl"
    return len(load_jsonl(path))


def get_backup_info() -> Dict[str, Any]:
    """Obtiene información de backups."""
    if not BACKUP_DIR.exists():
        return {"backups": 0, "latest": None}

    backups = sorted([d for d in BACKUP_DIR.iterdir() if d.is_dir()])
    return {
        "backups": len(backups),
        "latest": str(backups[-1].name) if backups else None,
    }


def recommend_training() -> str:
    """Recomienda si entrenar ahora o esperar."""
    interactions = count_interactions()
    feedback = count_feedback()
    high_quality = count_high_quality()

    # Necesitamos al menos 20 muestras nuevas o 10 pares de alta calidad
    if high_quality >= 10:
        return "ENTRENAR AHORA"
    if interactions + feedback["total"] >= 20:
        return "ENTRENAR AHORA"

    needed = max(0, 20 - (interactions + feedback["total"]))
    return f"ESPERAR MAS DATOS (faltan {needed} muestras)"


def print_report() -> None:
    """Imprime el reporte completo."""
    print("\n" + "=" * 60)
    print("  MONITOR AURA - Estado del Sistema")
    print("=" * 60)

    # 1. Último entrenamiento
    print("\n[Ultimo Entrenamiento]")
    training = get_last_training()
    if training.get("status") == "ok":
        print(f"  Fecha: {training.get('timestamp', 'N/A')}")
        print(f"  Return code: {training.get('returncode', 'N/A')}")
        print(f"  Duracion: {training.get('elapsed_s', 0)}s")
        print(f"  Log: {training.get('log', 'N/A')}")
    else:
        print("  (sin datos)")

    # 2. Modelo local
    print("\n[Modelo Local]")
    print(f"  LoRA existe: {LORA_DIR.exists()}")
    if LORA_DIR.exists():
        adapter = LORA_DIR / "adapter_model.safetensors"
        if adapter.exists():
            size_mb = adapter.stat().st_size / 1e6
            print(f"  Tamaño adapter: {size_mb:.2f} MB")

    # 3. Backups
    print("\n[Backups]")
    backup_info = get_backup_info()
    print(f"  Cantidad: {backup_info.get('backups', 0)}")
    print(f"  Ultimo: {backup_info.get('latest', 'N/A')}")

    # 4. Datos de entrenamiento
    print("\n[Datos de Entrenamiento]")
    interactions = count_interactions()
    feedback = count_feedback()
    high_quality = count_high_quality()
    print(f"  Interacciones: {interactions}")
    print(f"  Feedback: {feedback['total']} (up: {feedback['up']}, down: {feedback['down']})")
    print(f"  Pares alta calidad: {high_quality}")

    # 5. Recomendación
    print("\n[Recomendacion]")
    recommendation = recommend_training()
    print(f"  {recommendation}")

    print("\n" + "=" * 60 + "\n")


def main() -> int:
    print_report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())