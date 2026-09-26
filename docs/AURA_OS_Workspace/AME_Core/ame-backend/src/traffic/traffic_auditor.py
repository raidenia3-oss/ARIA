#!/usr/bin/env python3
"""
traffic_auditor.py — Auditor del motor de generación de tráfico.
Verifica:
  a) Contenido generado sin texto vacío, variables rotas o placeholders.
  b) Enlaces de redirección UTM correctamente formados.
  Lanza PASS/FAIL.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

TRAFFIC_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = TRAFFIC_DIR / "output"


def check_output_files() -> int:
    """a) Verificar que el contenido generado no tenga texto plano roto."""
    errors = 0
    if not OUTPUT_DIR.exists():
        print("ERROR: output/ no existe")
        return 1
    files = sorted(OUTPUT_DIR.glob("trends_*.json"))
    if not files:
        print("ERROR: No hay archivos de tendencias generados")
        return 1
    print(f"  Revisando {len(files)} archivos de salida...")
    for fpath in files:
        try:
            data = json.loads(fpath.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, Exception) as e:
            print(f"  ERROR: {fpath.name} no es JSON válido: {e}")
            errors += 1
            continue
        meta = data.get("meta", {})
        trends = data.get("trends", [])
        if not trends:
            print(f"  ERROR: {fpath.name} — lista de trends vacía")
            errors += 1
            continue
        for idx, trend in enumerate(trends):
            # revisar campos obligatorios
            required = ["id", "original_title", "title", "source_url", "landing_url", "category", "generated_at"]
            for field in required:
                val = trend.get(field)
                if not val or (isinstance(val, str) and val.strip() == ""):
                    print(f"  ERROR: {fpath.name}[{idx}] campo '{field}' vacío o ausente")
                    errors += 1
            # revisar que title no contenga placeholders
            title = trend.get("title", "")
            if "{" in title or "}" in title:
                print(f"  ERROR: {fpath.name}[{idx}] title contiene placeholders: {title}")
                errors += 1
            # revisar category válido
            valid_cats = {"herramienta", "modelo", "tutorial", "noticia", "open-source"}
            if trend.get("category") not in valid_cats:
                print(f"  ERROR: {fpath.name}[{idx}] categoría inválida: {trend.get('category')}")
                errors += 1
    return errors


def check_utm_links() -> int:
    """b) Verificar que los enlaces UTM estén correctamente formados."""
    errors = 0
    files = sorted(OUTPUT_DIR.glob("trends_*.json"))
    if not files:
        return 1
    for fpath in files:
        data = json.loads(fpath.read_text(encoding="utf-8"))
        for idx, trend in enumerate(data.get("trends", [])):
            url = trend.get("landing_url", "")
            # Debe contener todos los parámetros UTM
            required_params = ["utm_source", "utm_medium", "utm_campaign", "utm_content"]
            for param in required_params:
                if param not in url:
                    print(f"  ERROR: {fpath.name}[{idx}] landing_url sin '{param}': {url}")
                    errors += 1
            # Debe empezar con el base correcto
            if not url.startswith("https://aura-ia.vercel.app/recurso?"):
                print(f"  ERROR: {fpath.name}[{idx}] landing_url no apunta a landing: {url}")
                errors += 1
            # No debe contener espacios
            if " " in url:
                print(f"  ERROR: {fpath.name}[{idx}] landing_url contiene espacios: {url}")
                errors += 1
    return errors


def main() -> int:
    print("=== Traffic Auditor ===\n")
    total_errors = 0

    print("[a] Contenido generado (sin vacíos ni placeholders):")
    total_errors += check_output_files()

    print("\n[b] Enlaces UTM:")
    total_errors += check_utm_links()

    print(f"\n=== TOTAL: {total_errors} errores ===")
    return 1 if total_errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
