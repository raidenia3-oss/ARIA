"""
Validador de datasets de entrenamiento AURA.

Verifica que cada línea de un JSONL tenga los campos ``text`` y ``output``,
y reporta estadísticas: total, duplicados, vacíos y longitud promedio.

Uso:
    python training/scripts/validate_dataset.py --path training/data/continual_dataset.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("validate_dataset")


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Carga un archivo JSONL y devuelve la lista de objetos."""
    records: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    records.append(obj)
                else:
                    logger.warning("Línea %d: no es un objeto JSON (tipo %s)", line_no, type(obj).__name__)
            except json.JSONDecodeError as exc:
                logger.warning("Línea %d: JSON inválido: %s", line_no, exc)
    return records


def validate(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Valida los registros y devuelve el reporte."""
    total = len(records)
    missing_text = 0
    missing_output = 0
    empty_text = 0
    empty_output = 0
    text_lengths: List[int] = []
    output_lengths: List[int] = []
    seen_texts: Counter = Counter()

    for rec in records:
        text = rec.get("text")
        output = rec.get("output")

        if text is None:
            missing_text += 1
        elif isinstance(text, str) and not text.strip():
            empty_text += 1
        elif isinstance(text, str):
            text_lengths.append(len(text))
            seen_texts[text.strip()] += 1

        if output is None:
            missing_output += 1
        elif isinstance(output, str) and not output.strip():
            empty_output += 1
        elif isinstance(output, str):
            output_lengths.append(len(output))

    duplicates = sum(1 for count in seen_texts.values() if count > 1)
    duplicate_entries = sum(count - 1 for count in seen_texts.values() if count > 1)

    avg_text_len = round(sum(text_lengths) / len(text_lengths), 2) if text_lengths else 0.0
    avg_output_len = round(sum(output_lengths) / len(output_lengths), 2) if output_lengths else 0.0

    return {
        "total_samples": total,
        "valid_samples": total - missing_text - missing_output - empty_text - empty_output,
        "missing_text": missing_text,
        "missing_output": missing_output,
        "empty_text": empty_text,
        "empty_output": empty_output,
        "duplicates": duplicates,
        "duplicate_entries": duplicate_entries,
        "avg_text_length": avg_text_len,
        "avg_output_length": avg_output_len,
        "min_text_length": min(text_lengths) if text_lengths else 0,
        "max_text_length": max(text_lengths) if text_lengths else 0,
        "min_output_length": min(output_lengths) if output_lengths else 0,
        "max_output_length": max(output_lengths) if output_lengths else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida un dataset JSONL de entrenamiento AURA.")
    parser.add_argument("--path", required=True, help="Ruta al archivo JSONL")
    parser.add_argument("--output", default="training/data/validation_report.json", help="Ruta del reporte JSON de salida")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        logger.error("Archivo no encontrado: %s", path)
        return 1

    logger.info("Cargando %s ...", path)
    records = load_jsonl(path)
    logger.info("Registros cargados: %d", len(records))

    report = validate(records)
    report["source"] = str(path)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info("Reporte guardado en %s", out_path)
    logger.info(
        "Total: %d | Válidos: %d | Duplicados: %d | Vacíos: %d | Long. prom. text: %.2f",
        report["total_samples"],
        report["valid_samples"],
        report["duplicates"],
        report["empty_text"] + report["empty_output"],
        report["avg_text_length"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())