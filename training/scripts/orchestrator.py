"""
Orquestador del ciclo completo de entrenamiento AURA.

Ejecuta:
1. Generación de datos sintéticos (opcional)
2. Validación del dataset
3. Benchmark del router
4. Entrenamiento ligero (1 epoch)
5. Exporta logs y métricas a training/output/orchestrator_report.json

Uso:
    python training/scripts/orchestrator.py [--skip-synthetic] [--skip-benchmark] [--epochs N]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("orchestrator")

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "training" / "scripts"
DATA = ROOT / "training" / "data"
OUTPUT = ROOT / "training" / "output"

DEFAULT_DATASET = DATA / "training-data.jsonl"
SYNTHETIC_DATASET = DATA / "synthetic_generated.jsonl"
FINAL_DATASET = DATA / "continual_dataset.jsonl"

# Rutas alternativas del dataset base (según la estructura real del repo).
_ALT_DATASETS = [
    ROOT / "data" / "training" / "training-data.jsonl",
    ROOT / "data" / "training" / "training-data-collected.jsonl",
    ROOT / "training-data.jsonl",
]


def resolve_default_dataset() -> Path:
    """Devuelve la primera ruta de dataset que exista."""
    candidates = [DEFAULT_DATASET] + _ALT_DATASETS
    for path in candidates:
        if path.exists():
            return path
    return DEFAULT_DATASET


def run_script(script: str, args: List[str], timeout: int = 3600) -> Dict[str, Any]:
    """Ejecuta un script Python y captura stdout/stderr."""
    cmd = [sys.executable, str(SCRIPTS / script)] + args
    logger.info("Ejecutando: %s", " ".join(cmd))
    start = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(ROOT),
        )
        elapsed = time.time() - start
        return {
            "script": script,
            "returncode": proc.returncode,
            "stdout": proc.stdout[-2000:],
            "stderr": proc.stderr[-2000:],
            "elapsed_s": round(elapsed, 2),
        }
    except subprocess.TimeoutExpired:
        return {
            "script": script,
            "returncode": -1,
            "stdout": "",
            "stderr": f"Timeout después de {timeout}s",
            "elapsed_s": timeout,
        }


def merge_datasets() -> Path:
    """Combina el dataset base con el sintético (si existe) en continual_dataset.jsonl."""
    sources = [resolve_default_dataset()]
    if SYNTHETIC_DATASET.exists():
        sources.append(SYNTHETIC_DATASET)

    seen = set()
    total = 0
    with open(FINAL_DATASET, "w", encoding="utf-8") as out:
        for src in sources:
            if not src.exists():
                logger.warning("Dataset no encontrado: %s", src)
                continue
            with open(src, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        key = (obj.get("text", ""), obj.get("output", ""))
                        if key in seen:
                            continue
                        seen.add(key)
                        out.write(line + "\n")
                        total += 1
                    except json.JSONDecodeError:
                        continue
    logger.info("Dataset final: %d muestras -> %s", total, FINAL_DATASET)
    return FINAL_DATASET


def main() -> int:
    parser = argparse.ArgumentParser(description="Orquestador del ciclo de entrenamiento AURA.")
    parser.add_argument("--skip-synthetic", action="store_true", help="Omitir generación de datos sintéticos")
    parser.add_argument("--skip-benchmark", action="store_true", help="Omitir benchmark del router")
    parser.add_argument("--epochs", type=int, default=1, help="Número de épocas de entrenamiento")
    parser.add_argument("--max-samples", type=int, default=100, help="Máximo de muestras de entrenamiento")
    args = parser.parse_args()

    OUTPUT.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)

    report: Dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "steps": {},
    }

    # 1) Datos sintéticos (opcional)
    if not args.skip_synthetic and not SYNTHETIC_DATASET.exists():
        logger.info("Paso 1: Generando datos sintéticos...")
        report["steps"]["synthetic"] = run_script("synthetic_data_generator.py", [], timeout=600)
    else:
        logger.info("Paso 1: Omitiendo datos sintéticos (flag o ya existen)")
        report["steps"]["synthetic"] = {"skipped": True}

    # 2) Dataset final (merge)
    logger.info("Paso 2: Construyendo dataset final...")
    final_path = merge_datasets()

    # 3) Validación
    logger.info("Paso 3: Validando dataset...")
    report["steps"]["validate"] = run_script(
        "validate_dataset.py",
        ["--path", str(final_path), "--output", str(DATA / "validation_report.json")],
        timeout=120,
    )

    # 4) Benchmark (opcional)
    if not args.skip_benchmark:
        logger.info("Paso 4: Ejecutando benchmark del router...")
        report["steps"]["benchmark"] = run_script(
            "benchmark_router.py",
            ["--queries", "20", "--output", str(DATA / "benchmark_results.json")],
            timeout=300,
        )
    else:
        logger.info("Paso 4: Omitiendo benchmark (flag)")
        report["steps"]["benchmark"] = {"skipped": True}

    # 5) Entrenamiento
    logger.info("Paso 5: Entrenando modelo ligero (%d epochs)...", args.epochs)
    train_log = OUTPUT / "train_light.log"
    train_cmd = [
        sys.executable,
        str(SCRIPTS / "train_aura_light.py"),
        "--model-name", "Qwen/Qwen2.5-0.5B-Instruct",
        "--dataset-path", str(final_path),
        "--epochs", str(args.epochs),
        "--batch-size", "1",
        "--max-seq-length", "256",
        "--lora-r", "4",
        "--max-samples", str(args.max_samples),
    ]
    logger.info("Ejecutando: %s", " ".join(train_cmd))
    start = time.time()
    try:
        with open(train_log, "w", encoding="utf-8") as log_f:
            proc = subprocess.run(
                train_cmd,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                timeout=1800,  # 30 min
                cwd=str(ROOT),
            )
        report["steps"]["train"] = {
            "returncode": proc.returncode,
            "log": str(train_log),
            "elapsed_s": round(time.time() - start, 2),
        }
    except subprocess.TimeoutExpired:
        report["steps"]["train"] = {
            "returncode": -1,
            "log": str(train_log),
            "elapsed_s": 1800,
            "error": "Timeout (30 min)",
        }

    # Resumen
    ok = all(
        step.get("returncode", 0) == 0
        for step in report["steps"].values()
        if "returncode" in step
    )
    report["status"] = "OK" if ok else "PARTIAL"

    out_path = OUTPUT / "orchestrator_report.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info("Reporte guardado en %s", out_path)
    logger.info("Estado: %s", report["status"])
    for name, step in report["steps"].items():
        if "returncode" in step:
            logger.info("  %s: rc=%d (%.1fs)", name, step["returncode"], step.get("elapsed_s", 0))
        else:
            logger.info("  %s: %s", name, "skipped" if step.get("skipped") else "ok")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())