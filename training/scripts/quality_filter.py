"""
Filtro de calidad para entrenamiento AURA.

Lee training/data/interactions.jsonl y training/data/feedback.jsonl, asigna
un score de calidad a cada interacción y exporta solo los pares con score >= 2
a training/data/high_quality_pairs.jsonl.

Reglas de score:
  - feedback=up: +2
  - feedback=down: -3
  - provider=cloud y latency < 2s: +1
  - complexity=high: +1

Uso:
    python training/scripts/quality_filter.py
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("quality_filter")

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "training" / "data"

INTERACTIONS_PATH = DATA / "interactions.jsonl"
FEEDBACK_PATH = DATA / "feedback.jsonl"
OUTPUT_PATH = DATA / "high_quality_pairs.jsonl"


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Carga un archivo JSONL."""
    records: List[Dict[str, Any]] = []
    if not path.exists():
        logger.warning("Archivo no encontrado: %s", path)
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


def load_feedback_map(feedback_records: List[Dict[str, Any]]) -> Dict[str, str]:
    """Construye un mapa prompt -> feedback (up/down)."""
    feedback_map: Dict[str, str] = {}
    for rec in feedback_records:
        prompt = rec.get("prompt", "")
        value = rec.get("feedback", "")
        if prompt and value in ("up", "down"):
            feedback_map[prompt] = value
    return feedback_map


def compute_score(interaction: Dict[str, Any], feedback_map: Dict[str, str]) -> int:
    """Calcula el score de calidad de una interacción."""
    score = 0
    prompt = interaction.get("prompt", "")

    # Feedback del usuario
    fb = feedback_map.get(prompt)
    if fb == "up":
        score += 2
    elif fb == "down":
        score -= 3

    # Proveedor cloud con baja latencia
    provider = interaction.get("provider", "")
    latency = interaction.get("latency_ms", 0)
    if provider in ("cloud", "gemini", "groq", "openrouter", "deepseek", "nvidia", "mistral", "huggingface"):
        if latency and latency < 2000:
            score += 1

    # Complejidad alta
    if interaction.get("complexity") == "high":
        score += 1

    return score


def main() -> int:
    parser = argparse.ArgumentParser(description="Filtro de calidad para entrenamiento AURA.")
    parser.add_argument("--min-score", type=int, default=2, help="Score mínimo para incluir")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Ruta de salida")
    args = parser.parse_args()

    interactions = load_jsonl(INTERACTIONS_PATH)
    feedback_records = load_jsonl(FEEDBACK_PATH)
    feedback_map = load_feedback_map(feedback_records)

    logger.info("Interacciones: %d | Feedback: %d", len(interactions), len(feedback_records))

    scored: List[Dict[str, Any]] = []
    for inter in interactions:
        score = compute_score(inter, feedback_map)
        inter["quality_score"] = score
        scored.append(inter)

    # Filtrar por score
    high_quality = [i for i in scored if i["quality_score"] >= args.min_score]

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for item in high_quality:
            pair = {
                "text": item.get("prompt", ""),
                "output": item.get("response", ""),
                "quality_score": item["quality_score"],
                "provider": item.get("provider", ""),
                "complexity": item.get("complexity", ""),
            }
            f.write(json.dumps(pair, ensure_ascii=False) + "\n")

    # Estadísticas
    score_dist = defaultdict(int)
    for i in scored:
        score_dist[i["quality_score"]] += 1

    logger.info("Exportados %d pares de alta calidad -> %s", len(high_quality), out_path)
    logger.info("Distribución de scores: %s", dict(sorted(score_dist.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())