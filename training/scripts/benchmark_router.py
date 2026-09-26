"""
Benchmark del SmartAIRouter de AURA.

Carga el router en modo ``hybrid``, ejecuta un conjunto de consultas
predefinidas (5 low, 10 medium, 5 high) y mide la latencia de
enrutamiento/clasificación por consulta y por proveedor decidido.
Guarda los resultados en ``training/data/benchmark_results.json``.

Uso:
    python training/scripts/benchmark_router.py --queries 20
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("benchmark_router")

# 5 low, 10 medium, 5 high = 20 consultas predefinidas
PREDEFINED_QUERIES: List[Dict[str, str]] = [
    # --- LOW (5) ---
    {"complexity": "low", "prompt": "¿Qué hora es?"},
    {"complexity": "low", "prompt": "Hola, ¿cómo estás?"},
    {"complexity": "low", "prompt": "¿Qué puedes hacer?"},
    {"complexity": "low", "prompt": "Abre el navegador"},
    {"complexity": "low", "prompt": "Lista los archivos del directorio actual"},
    # --- MEDIUM (10) ---
    {"complexity": "medium", "prompt": "Explica brevemente qué es un modelo de lenguaje"},
    {"complexity": "medium", "prompt": "¿Cuál es la capital de Francia y su población?"},
    {"complexity": "medium", "prompt": "Resume el concepto de aprendizaje por refuerzo"},
    {"complexity": "medium", "prompt": "¿Cómo funciona una red neuronal convolucional?"},
    {"complexity": "medium", "prompt": "Dame 3 consejos para mejorar la productividad"},
    {"complexity": "medium", "prompt": "¿Qué diferencias hay entre Python y JavaScript?"},
    {"complexity": "medium", "prompt": "Explica qué es la computación en la nube"},
    {"complexity": "medium", "prompt": "¿Cómo se entrena un modelo de clasificación de texto?"},
    {"complexity": "medium", "prompt": "Describe el ciclo de vida del desarrollo de software"},
    {"complexity": "medium", "prompt": "¿Qué es el overfitting y cómo evitarlo?"},
    # --- HIGH (5) ---
    {"complexity": "high", "prompt": "Analiza en profundidad la arquitectura de un sistema distribuido de microservicios y propón mejoras"},
    {"complexity": "high", "prompt": "Diseña una estrategia de optimización de rendimiento para una base de datos PostgreSQL con millones de registros"},
    {"complexity": "high", "prompt": "Investiga y compara en detalle los frameworks de machine learning más usados en producción en 2025"},
    {"complexity": "high", "prompt": "Planifica una arquitectura de seguridad de red para una empresa con múltiples sucursales y acceso remoto"},
    {"complexity": "high", "prompt": "Implementa un algoritmo de recomendación colaborativa explicando cada paso del razonamiento"},
]


def load_router() -> Any:
    """Carga SmartAIRouter en modo hybrid."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from training.scripts.smart_ai_router import SmartAIRouter

    return SmartAIRouter(mode="hybrid")


def run_benchmark(router: Any, queries: List[Dict[str, str]]) -> Dict[str, Any]:
    """Ejecuta las consultas y mide la latencia de enrutamiento/clasificación."""
    results: List[Dict[str, Any]] = []
    provider_latencies: Dict[str, List[float]] = {}
    provider_counts: Dict[str, int] = {}
    complexity_correct = 0

    for q in queries:
        prompt = q["prompt"]
        expected = q["complexity"]

        # Medir solo la latencia de clasificación + decisión del router
        # (sin llamadas externas a proveedores).
        start = time.time()
        complexity = router._estimate_complexity(prompt)
        provider, model, reason = router._decide_provider(
            complexity=complexity,
            force_provider=None,
            force_model=None,
        )
        latency = (time.time() - start) * 1000

        if complexity == expected:
            complexity_correct += 1

        results.append(
            {
                "prompt": prompt,
                "expected_complexity": expected,
                "detected_complexity": complexity,
                "provider": provider,
                "model": model,
                "reason": reason,
                "latency_ms": round(latency, 2),
            }
        )
        provider_latencies.setdefault(provider, []).append(latency)
        provider_counts[provider] = provider_counts.get(provider, 0) + 1

    # Estadísticas por proveedor
    provider_stats: Dict[str, Any] = {}
    for provider, lats in provider_latencies.items():
        provider_stats[provider] = {
            "count": provider_counts.get(provider, 0),
            "avg_latency_ms": round(sum(lats) / len(lats), 2) if lats else 0.0,
            "min_latency_ms": round(min(lats), 2) if lats else 0.0,
            "max_latency_ms": round(max(lats), 2) if lats else 0.0,
        }

    all_lats = [r["latency_ms"] for r in results]
    return {
        "total_queries": len(results),
        "avg_latency_ms": round(sum(all_lats) / len(all_lats), 2) if all_lats else 0.0,
        "min_latency_ms": round(min(all_lats), 2) if all_lats else 0.0,
        "max_latency_ms": round(max(all_lats), 2) if all_lats else 0.0,
        "complexity_accuracy": round(complexity_correct / len(results), 4) if results else 0.0,
        "provider_stats": provider_stats,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark del SmartAIRouter de AURA.")
    parser.add_argument("--queries", type=int, default=20, help="Número de consultas (usa las predefinidas)")
    parser.add_argument("--output", default="training/data/benchmark_results.json", help="Ruta del JSON de salida")
    args = parser.parse_args()

    # Usar las consultas predefinidas (20: 5 low, 10 medium, 5 high)
    queries = PREDEFINED_QUERIES[: args.queries] if args.queries <= len(PREDEFINED_QUERIES) else PREDEFINED_QUERIES

    logger.info("Cargando SmartAIRouter en modo hybrid ...")
    router = load_router()
    logger.info("Router cargado. Ejecutando %d consultas ...", len(queries))

    report = run_benchmark(router, queries)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info("Resultados guardados en %s", out_path)
    logger.info(
        "Total: %d | Avg latencia: %.2f ms | Precisión complejidad: %.2f%% | Proveedores: %s",
        report["total_queries"],
        report["avg_latency_ms"],
        report["complexity_accuracy"] * 100,
        list(report["provider_stats"].keys()),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())