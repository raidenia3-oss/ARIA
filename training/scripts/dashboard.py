"""
Dashboard de métricas de entrenamiento AURA.

Lee training/data/benchmark_results.json, training/output/evaluation_report.json,
training/data/feedback.jsonl y training/data/interactions.jsonl, e imprime
un resumen en consola.

Uso:
    python training/scripts/dashboard.py
"""

from __future__ import annotations

import argparse
import json
import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("dashboard")

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "training" / "data"
OUTPUT = ROOT / "training" / "output"

BENCHMARK_PATH = DATA / "benchmark_results.json"
EVALUATION_PATH = OUTPUT / "evaluation_report.json"
FEEDBACK_PATH = DATA / "feedback.jsonl"
INTERACTIONS_PATH = DATA / "interactions.jsonl"
HIGH_QUALITY_PATH = DATA / "high_quality_pairs.jsonl"


def load_json(path: Path) -> Dict[str, Any]:
    """Carga un archivo JSON."""
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Carga un archivo JSONL."""
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


def print_section(title: str) -> None:
    """Imprime un separador de sección."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Dashboard de métricas de entrenamiento AURA.")
    args = parser.parse_args()

    # 1) Benchmark del router
    print_section("1. Benchmark del Router")
    benchmark = load_json(BENCHMARK_PATH)
    if benchmark:
        print(f"  Total queries: {benchmark.get('total_queries', 0)}")
        print(f"  Avg latencia: {benchmark.get('avg_latency_ms', 0)}ms")
        print(f"  Precisión complejidad: {benchmark.get('complexity_accuracy', 0) * 100:.1f}%")
        provider_stats = benchmark.get("provider_stats", {})
        for provider, stats in provider_stats.items():
            print(f"  [{provider}] count={stats.get('count', 0)} avg={stats.get('avg_latency_ms', 0)}ms")
    else:
        print("  (sin datos)")

    # 2) Evaluación del modelo
    print_section("2. Evaluación del Modelo")
    evaluation = load_json(EVALUATION_PATH)
    if evaluation:
        metrics = evaluation.get("metrics", {})
        print(f"  Base avg latencia: {metrics.get('base_avg_latency_ms', 0)}ms")
        print(f"  Fine-tuned avg latencia: {metrics.get('ft_avg_latency_ms', 0)}ms")
        print(f"  Base avg score: {metrics.get('base_avg_score', 0)}")
        print(f"  Fine-tuned avg score: {metrics.get('ft_avg_score', 0)}")
        print(f"  Win rate fine-tuned: {metrics.get('win_rate_ft', 0) * 100:.1f}%")
        print(f"  Ties: {metrics.get('ties', 0)}")
    else:
        print("  (sin datos - ejecuta evaluate_model.py)")

    # 3) Feedback
    print_section("3. Feedback de Usuarios")
    feedback = load_jsonl(FEEDBACK_PATH)
    if feedback:
        up = sum(1 for f in feedback if f.get("feedback") == "up")
        down = sum(1 for f in feedback if f.get("feedback") == "down")
        print(f"  Total: {len(feedback)} | Up: {up} | Down: {down}")
        if feedback:
            print(f"  Ratio positivo: {up / len(feedback) * 100:.1f}%")
    else:
        print("  (sin datos)")

    # 4) Interacciones
    print_section("4. Interacciones del Router")
    interactions = load_jsonl(INTERACTIONS_PATH)
    if interactions:
        providers = Counter(i.get("provider", "unknown") for i in interactions)
        complexities = Counter(i.get("complexity", "unknown") for i in interactions)
        errors = sum(1 for i in interactions if i.get("provider") == "error")
        print(f"  Total: {len(interactions)} | Errores: {errors}")
        print(f"  Proveedores: {dict(providers)}")
        print(f"  Complejidad: {dict(complexities)}")
    else:
        print("  (sin datos)")

    # 5) Alta calidad
    print_section("5. Pares de Alta Calidad")
    high_quality = load_jsonl(HIGH_QUALITY_PATH)
    print(f"  Pares exportados: {len(high_quality)}")

    # 6) Próximo entrenamiento recomendado
    print_section("6. Próximo Entrenamiento")
    new_samples = len(interactions) + len(feedback)
    print(f"  Muestras nuevas disponibles: {new_samples}")
    if new_samples >= 20:
        print("  -> RECOMENDADO: ejecutar orchestrator.py --skip-synthetic")
    else:
        print(f"  -> Faltan {20 - new_samples} muestras para recomendar entrenamiento")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())