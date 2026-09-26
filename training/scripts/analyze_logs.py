"""
Analiza logs de métricas y genera un reporte de observabilidad.

Lee logs/metrics.jsonl y produce:
- throughput
- error rate
- latencia P95
- distribución de proveedores

Uso:
    python training/scripts/analyze_logs.py
"""

from __future__ import annotations

import json
import logging
import os
import statistics
from collections import Counter
from pathlib import Path
from typing import Any, Dict

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("analyze_logs")

ROOT = Path(__file__).resolve().parents[2]
METRICS_FILE = ROOT / "logs" / "metrics.jsonl"
REPORT_FILE = ROOT / "logs" / "observability_report.json"


def load_metrics() -> list[Dict[str, Any]]:
    if not METRICS_FILE.exists():
        return []
    records = []
    with open(METRICS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def analyze(records: list[Dict[str, Any]]) -> Dict[str, Any]:
    total_requests = 0
    errors = 0
    latencies: list[float] = []
    providers: Counter = Counter()

    for rec in records:
        if rec.get("type") == "request_end":
            total_requests += 1
            status = rec.get("status_code", 200)
            if status >= 400:
                errors += 1
            latencies.append(rec.get("latency_ms", 0.0))
            providers[rec.get("provider", "unknown")] += 1

    error_rate = round(errors / total_requests, 4) if total_requests else 0.0
    latency_p95 = 0.0
    if latencies:
        latencies.sort()
        idx = int(len(latencies) * 0.95)
        idx = min(idx, len(latencies) - 1)
        latency_p95 = round(latencies[idx], 2)

    return {
        "timestamp": __import__("datetime").datetime.now().isoformat(),
        "total_requests": total_requests,
        "errors": errors,
        "error_rate": error_rate,
        "latency_p95_ms": latency_p95,
        "providers": dict(providers),
    }


def save_report(report: Dict[str, Any]) -> None:
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    logger.info("Reporte guardado en %s", REPORT_FILE)


def print_report(report: Dict[str, Any]) -> None:
    print("\n" + "=" * 60)
    print("  OBSERVABILITY REPORT")
    print("=" * 60)
    print(f"  Requests: {report.get('total_requests', 0)}")
    print(f"  Errors: {report.get('errors', 0)}")
    print(f"  Error rate: {report.get('error_rate', 0):.2%}")
    print(f"  Latency P95: {report.get('latency_p95_ms', 0):.2f} ms")
    print(f"  Providers: {report.get('providers', {})}")
    print("=" * 60 + "\n")


def main() -> int:
    records = load_metrics()
    if not records:
        logger.warning("No hay métricas en %s", METRICS_FILE)
        return 0
    report = analyze(records)
    save_report(report)
    print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())