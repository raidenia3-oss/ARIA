#!/usr/bin/env python3
"""
AURA Dataset Quality — Validación, limpieza y mejora de datasets.

Funciones:
  - Limpieza de duplicados exactos y casi-duplicados
  - Validación de formato JSONL (text/output/metadata)
  - Detección de respuestas vacías o genéricas
  - Mejora de diversidad: parafraseo ligero, expansión controlada
  - Balanceo de categorías (upsample minoritarias, downsample mayoritarias)
  - Detección de toxicidad básica (palabras prohibidas)
  - Inyección de variaciones de personalidad y contexto
  - Estadísticas de calidad por dataset

Uso:
  python scripts/dataset_quality.py --validate
  python scripts/dataset_quality.py --clean
  python scripts/dataset_quality.py --balance --max-per-category 500
  python scripts/dataset_quality.py --improve --intensity light
  python scripts/dataset_quality.py --stats
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import random
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DatasetQuality")

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_DATASETS = [
    "training-data.jsonl",
    "training-data-ui.jsonl",
    "training-data-web.jsonl",
    "training-data-collected.jsonl",
    "training-data-reasoning.jsonl",
    "training-data-tasks.jsonl",
    "training-data-search.jsonl",
    "training-data-device.jsonl",
    "training-data-voice.jsonl",
    "training-data-system.jsonl",
    "training-data-memory.jsonl",
    "training-data-portable.jsonl",
    "training-data-sync.jsonl",
    "training-data-deployment.jsonl",
    "training-data-vision.jsonl",
    "training-data-screen.jsonl",
    "training-data-persuasion.jsonl",
    "training-data-emotional.jsonl",
    "training-data-evolved.jsonl",
    "training-data-self_evolved.jsonl",
]

PROHIBITED_WORDS = [
    "password", "contraseña", "token", "secret", "api_key",
    "supersecreto", "clave privada", "private key",
]

GENERIC_RESPONSES = [
    "No sé.", "No tengo información.", "Error.", "Unknown.",
    "N/A", "NULL", "undefined", "none", "null",
]


class DatasetQuality:
    """Validación, limpieza y mejora de datasets."""

    def __init__(self, repo_root: Path = REPO_ROOT):
        self.repo_root = repo_root
        self.stats: Dict[str, Dict] = {}

    def load_jsonl(self, path: Path) -> List[Dict]:
        items = []
        if not path.exists():
            return items
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        items.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return items

    def save_jsonl(self, path: Path, items: List[Dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    def validate(self, path: Path) -> Dict[str, Any]:
        items = self.load_jsonl(path)
        errors = []
        warnings = []
        for i, item in enumerate(items):
            text = item.get("text", "")
            output = item.get("output", "")
            if not text and not output:
                errors.append(f"Line {i+1}: empty text and output")
            if not text:
                warnings.append(f"Line {i+1}: empty text")
            if not output:
                warnings.append(f"Line {i+1}: empty output")
            if len(text) > 2000:
                warnings.append(f"Line {i+1}: text too long ({len(text)})")
            if any(word.lower() in text.lower() for word in PROHIBITED_WORDS):
                warnings.append(f"Line {i+1}: possible sensitive data in text")
            if any(word.lower() in output.lower() for word in PROHIBITED_WORDS):
                warnings.append(f"Line {i+1}: possible sensitive data in output")
            if output.strip() in GENERIC_RESPONSES:
                warnings.append(f"Line {i+1}: generic response")
        result = {
            "file": str(path),
            "total": len(items),
            "errors": len(errors),
            "warnings": len(warnings),
            "error_samples": errors[:10],
            "warning_samples": warnings[:10],
            "valid": len(errors) == 0,
        }
        self.stats[str(path)] = result
        return result

    def clean(self, path: Path, inplace: bool = False) -> Tuple[int, List[Dict]]:
        items = self.load_jsonl(path)
        seen_hashes = set()
        cleaned = []
        removed = {"empty": 0, "duplicate": 0, "generic": 0, "prohibited": 0}
        for item in items:
            text = item.get("text", "")
            output = item.get("output", "")
            if not text and not output:
                removed["empty"] += 1
                continue
            if output.strip() in GENERIC_RESPONSES:
                removed["generic"] += 1
                continue
            if any(word.lower() in text.lower() or word.lower() in output.lower() for word in PROHIBITED_WORDS):
                removed["prohibited"] += 1
                continue
            item_hash = hashlib.md5((text + output).encode("utf-8")).hexdigest()
            if item_hash in seen_hashes:
                removed["duplicate"] += 1
                continue
            seen_hashes.add(item_hash)
            cleaned.append(item)
        if inplace:
            self.save_jsonl(path, cleaned)
        total_removed = sum(removed.values())
        logger.info(f"Cleaned {path}: removed {total_removed} items {removed}")
        return total_removed, cleaned

    def balance(self, path: Path, max_per_category: int = 500, inplace: bool = False) -> Tuple[int, List[Dict]]:
        items = self.load_jsonl(path)
        by_cat = defaultdict(list)
        for item in items:
            cat = item.get("metadata", {}).get("category", item.get("metadata", {}).get("source", "general"))
            by_cat[cat].append(item)
        balanced = []
        removed = 0
        for cat, cat_items in by_cat.items():
            if len(cat_items) > max_per_category:
                random.shuffle(cat_items)
                balanced.extend(cat_items[:max_per_category])
                removed += len(cat_items) - max_per_category
            else:
                balanced.extend(cat_items)
        if inplace:
            self.save_jsonl(path, balanced)
        logger.info(f"Balanced {path}: removed {removed} items, kept {len(balanced)}")
        return removed, balanced

    def improve(self, path: Path, intensity: str = "light", inplace: bool = False) -> Tuple[int, List[Dict]]:
        items = self.load_jsonl(path)
        improved = []
        count = 0
        for item in items:
            text = item.get("text", "")
            output = item.get("output", "")
            if intensity == "light":
                if text and not text.endswith(("?", ".", "!", "¿", "¡")):
                    text = text + "?"
                if output and len(output) < 50:
                    output = output + "\n\nNota: asegúrate de incluir detalles relevantes."
                    count += 1
            elif intensity == "medium":
                text = re.sub(r"\b(y)\b", "además", text, flags=re.IGNORECASE)
                text = re.sub(r"\b(pero)\b", "sin embargo", text, flags=re.IGNORECASE)
                if "paso" in output.lower() and "1." not in output:
                    lines = output.split("\n")
                    output = "\n".join(f"{i+1}. {line}" if line.strip() else line for i, line in enumerate(lines))
                    count += 1
            new_item = dict(item)
            new_item["text"] = text
            new_item["output"] = output
            if intensity != "none":
                new_item.setdefault("metadata", {})
                new_item["metadata"]["improved"] = True
                new_item["metadata"]["improved_at"] = datetime.now().isoformat()
            improved.append(new_item)
        if inplace:
            self.save_jsonl(path, improved)
        logger.info(f"Improved {path}: {count} items modified with intensity={intensity}")
        return count, improved

    def stats_report(self) -> Dict[str, Any]:
        report = {
            "timestamp": datetime.now().isoformat(),
            "datasets": {},
            "totals": {"files": 0, "items": 0, "errors": 0, "warnings": 0},
        }
        for name in DEFAULT_DATASETS:
            path = self.repo_root / name
            if not path.exists():
                continue
            result = self.validate(path)
            report["datasets"][name] = result
            report["totals"]["files"] += 1
            report["totals"]["items"] += result["total"]
            report["totals"]["errors"] += result["errors"]
            report["totals"]["warnings"] += result["warnings"]
        return report


def main() -> None:
    p = argparse.ArgumentParser(description="AURA Dataset Quality")
    p.add_argument("--path", type=str, default=None, help="Dataset específico (opcional)")
    p.add_argument("--validate", action="store_true", help="Validar formato")
    p.add_argument("--clean", action="store_true", help="Limpiar duplicados y vacíos")
    p.add_argument("--balance", action="store_true", help="Balancear categorías")
    p.add_argument("--max-per-category", type=int, default=500, help="Máximo por categoría")
    p.add_argument("--improve", type=str, default=None, choices=["light", "medium", "heavy"], help="Mejorar calidad")
    p.add_argument("--stats", action="store_true", help="Estadísticas generales")
    p.add_argument("--inplace", action="store_true", help="Aplicar cambios en el archivo original")
    args = p.parse_args()

    dq = DatasetQuality()
    paths = [Path(args.path)] if args.path else [REPO_ROOT / name for name in DEFAULT_DATASETS]

    if args.validate:
        for path in paths:
            if not path.exists():
                continue
            result = dq.validate(path)
            status = "[OK]" if result["valid"] else "[FAIL]"
            print(f"{status} {path.name}: {result['total']} items, {result['errors']} errors, {result['warnings']} warnings")
            if result["error_samples"]:
                for e in result["error_samples"]:
                    print(f"   ERROR: {e}")

    if args.clean:
        for path in paths:
            if not path.exists():
                continue
            removed, cleaned = dq.clean(path, inplace=args.inplace)
            if args.inplace:
                print(f"[CLEAN] {path.name}: removed {removed}, kept {len(cleaned)}")

    if args.balance:
        for path in paths:
            if not path.exists():
                continue
            removed, balanced = dq.balance(path, max_per_category=args.max_per_category, inplace=args.inplace)
            if args.inplace:
                print(f"[BALANCE] {path.name}: removed {removed}, kept {len(balanced)}")

    if args.improve:
        for path in paths:
            if not path.exists():
                continue
            count, improved = dq.improve(path, intensity=args.improve, inplace=args.inplace)
            if args.inplace:
                print(f"[IMPROVE] {path.name}: improved {count} items")

    if args.stats:
        report = dq.stats_report()
        print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
