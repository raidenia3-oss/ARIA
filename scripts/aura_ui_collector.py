#!/usr/bin/env python3
"""
AURA UI Data Collector — Extrae código HTML/CSS/JS de las apps existentes
y genera datos de entrenamiento para que el modelo aprenda a generar interfaces.

Escanea todos los archivos .html del repositorio, extrae componentes, estilos
y estructuras, y genera pares entrenamiento (descripcion -> codigo HTML).

Uso:
  python scripts/aura_ui_collector.py
  python scripts/aura_ui_collector.py --output training-data-ui.jsonl
  python scripts/aura_ui_collector.py --max-files 20
"""

from __future__ import annotations

import os
import re
import sys
import json
import hashlib
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from html.parser import HTMLParser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("AuraUIDataCollector")

REPO_ROOT = Path(__file__).resolve().parent.parent


class UIHTMLParser(HTMLParser):
    """Parser simple para extraer estructura y componentes de HTML."""

    def __init__(self):
        super().__init__()
        self.tags_stack: List[str] = []
        self.components: Dict[str, List[str]] = {}
        self.css_vars: List[str] = []
        self.colors: List[str] = []
        self.fonts: List[str] = []

    def handle_starttag(self, tag, attrs):
        self.tags_stack.append(tag)
        attrs_dict = dict(attrs)
        cls = attrs_dict.get("class", "")
        if cls:
            tag_key = f"{tag}.{cls.split()[0]}" if cls.split() else tag
            self.components.setdefault(tag_key, []).append(tag)

    def handle_endtag(self, tag):
        if self.tags_stack and self.tags_stack[-1] == tag:
            self.tags_stack.pop()


def extract_css_vars(html: str) -> List[str]:
    """Extrae variables CSS definidas con :root."""
    return re.findall(r'--([\w-]+)\s*:\s*([^;]+);', html)


def extract_colors(css: str) -> List[str]:
    """Extrae colores hexadecimales y CSS."""
    return re.findall(r'(#([0-9a-fA-F]{3,8})|rgba?\([^)]+\)|var\([^)]+\))', css)


def extract_title(html: str) -> Optional[str]:
    match = re.search(r'<title[^>]*>(.*?)</title>', html, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else None


def extract_styles(html: str) -> Optional[str]:
    match = re.search(r'<style[^>]*>(.*?)</style>', html, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else None


def detect_theme(colors: List[str], title: Optional[str]) -> Dict[str, str]:
    """Detecta el tema de la interfaz basado en colores y título."""
    color_texts = [c[0] for c in colors if c[0]]
    theme = {
        "name": "general",
        "primary_color": "#00d4ff",
        "bg_color": "#0a0a1a",
        "text_color": "#e0e0e0",
        "style": "modern",
    }

    all_colors = " ".join(color_texts).lower()
    if "00f0ff" in all_colors or "00d4ff" in all_colors:
        theme["name"] = "cyberpunk"
        theme["primary_color"] = "#00f0ff"
        theme["bg_color"] = "#000000"
        theme["style"] = "neon"
    elif "7b2ff7" in all_colors or "6a0572" in all_colors:
        theme["name"] = "gradient"
        theme["primary_color"] = "#7b2ff7"
        theme["style"] = "gradient"
    elif "1a1a2e" in all_colors or "0f0f23" in all_colors:
        theme["name"] = "dark"
        theme["primary_color"] = "#00d4ff"
        theme["bg_color"] = "#1a1a2e"
        theme["style"] = "dark"
    elif title and any(k in title.lower() for k in ["mobile", "hud", "phone"]):
        theme["name"] = "mobile"
        theme["style"] = "mobile-app"

    return theme


def truncate_html(html: str, max_length: int = 4000) -> str:
    """Trunca HTML manteniendo tags balanceados."""
    if len(html) <= max_length:
        return html
    return html[:max_length] + "\n<!-- truncated -->\n"


def generate_ui_training_pairs(html_content: str, file_path: Path) -> List[Dict]:
    """Genera múltiples pares de entrenamiento UI a partir de un archivo HTML."""
    pairs = []
    title = extract_title(html_content) or file_path.stem
    styles = extract_styles(html_content)
    css_vars = extract_css_vars(html_content)
    colors = extract_colors(styles or html_content)
    theme = detect_theme(colors, title)

    # 1. Par: "Crea una interfaz tipo [tema]" -> HTML completo
    desc_full = f"Crea una interfaz web completa con tema {theme['name']} que se llame '{title}' usando colores {theme['primary_color']} y fondo {theme['bg_color']}. La interfaz debe incluir HTML5 semantico, CSS con variables y estilos modernos, y funcionalidad JavaScript. Genera el codigo completo y funcional."

    pairs.append({
        "text": desc_full,
        "output": truncate_html(html_content, 3500),
        "metadata": {
            "source": "ui_code",
            "file": str(file_path.relative_to(REPO_ROOT)),
            "title": title,
            "theme": theme["name"],
            "component_type": "full_page",
            "task": "ui_generation",
        },
    })

    # 2. Par: "Crea los estilos CSS para [tema]" -> CSS solo
    if styles:
        desc_css = f"Crea los estilos CSS para una interfaz {theme['name']} con colores primarios {theme['primary_color']} y fondo {theme['bg_color']}. Incluye variables CSS, reset de margenes, tipografia moderna, transiciones y efectos. Genera solo el codigo CSS."
        pairs.append({
            "text": desc_css,
            "output": truncate_html(styles, 2000),
            "metadata": {
                "source": "ui_code",
                "file": str(file_path.relative_to(REPO_ROOT)),
                "title": title,
                "theme": theme["name"],
                "component_type": "css_styles",
                "task": "css_generation",
            },
        })

    # 3. Par: Extraer componentes específicos
    parser = UIHTMLParser()
    try:
        parser.feed(html_content)
    except Exception:
        pass

    for tag_name, instances in parser.components.items():
        if "." in tag_name:
            tag_part, cls_part = tag_name.split(".", 1)
            desc_comp = f"Crea un componente HTML5 <{tag_part}> con clase '{cls_part}' para una interfaz {theme['name']}. Debe incluir estilos CSS con fondo {theme['primary_color']} tenue, bordes redondeados, y efectos de hover. Genera HTML y CSS completos."
        else:
            desc_comp = f"Crea un componente HTML5 <{tag_name}> para una interfaz {theme['name']}. Debe ser semantico, con estilos modernos y responsive. Genera HTML y CSS completos."

        # Extraer el HTML del componente (primer match)
        pattern = rf'<{tag_name}[\s>].*?</{tag_name}>'
        match = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)
        if match:
            pairs.append({
                "text": desc_comp,
                "output": match.group(0)[:2000],
                "metadata": {
                    "source": "ui_code",
                    "file": str(file_path.relative_to(REPO_ROOT)),
                    "title": title,
                    "theme": theme["name"],
                    "component_type": tag_name,
                    "task": "component_generation",
                },
            })

    # 4. Par: Layout/description
    desc_layout = f"Describe la estructura de la pagina '{title}' con tema {theme['name']}. Que secciones contiene y como se distribuyen. La pagina usa una paleta de colores con {theme['primary_color']} como color principal y {theme['bg_color']} como fondo. Describe los elementos principales, la tipografia usada y los efectos visuales."
    # Generamos una descripcion simple basada en el titulo
    desc_text = f"La interfaz '{title}' tiene tema {theme['name']} con color principal {theme['primary_color']}. Incluye secciones de navegacion, panel principal, tarjetas de contenido y elementos de interaccion. Usa tipografia monoespaciada moderna y efectos de glow/transicion."

    pairs.append({
        "text": desc_layout,
        "output": desc_text,
        "metadata": {
            "source": "ui_code",
            "file": str(file_path.relative_to(REPO_ROOT)),
            "title": title,
            "theme": theme["name"],
            "component_type": "description",
            "task": "ui_description",
        },
    })

    # 5. Par: Generacion de componentes desde descripción del archivo
    filename_parts = file_path.stem.replace("_", " ").replace("-", " ").title()
    desc_by_name = f"Crea una interfaz web llamada '{filename_parts}' con un diseno moderno y responsivo. Incluye HTML5 completo con semantica, CSS con variables personalizadas y estilos con efectos visuales. Usa una paleta oscura con acentos de color."

    pairs.append({
        "text": desc_by_name,
        "output": truncate_html(html_content, 3500),
        "metadata": {
            "source": "ui_code",
            "file": str(file_path.relative_to(REPO_ROOT)),
            "title": filename_parts,
            "theme": theme["name"],
            "component_type": "full_page",
            "task": "ui_generation",
        },
    })

    return pairs


def find_html_files(root: Path, max_files: int = 15) -> List[Path]:
    """Encuentra archivos HTML relevantes en el repositorio."""
    html_files = []
    exclude_dirs = {
        "node_modules", ".git", "__pycache__", "venv", "venv-training",
        ".venv", "site-packages", "dist", "build", ".next",
    }

    for path in sorted(root.rglob("*.html")):
        if any(part in exclude_dirs for part in path.parts):
            continue
        if "test_" in path.stem:
            continue
        html_files.append(path)
        if len(html_files) >= max_files:
            break

    return html_files


def collect_ui_data(output_file: str = "training-data-ui.jsonl",
                    max_files: int = 15,
                    max_pairs_per_file: int = 15) -> Tuple[str, int]:
    """
    Recolecta datos de UI de archivos HTML existentes y genera
    pares de entrenamiento (descripcion -> codigo HTML/CSS/JS).
    """
    output_path = REPO_ROOT / output_file
    html_files = find_html_files(REPO_ROOT, max_files)

    logger.info(f"HTML files found: {len(html_files)}")
    all_pairs: List[Dict] = []
    seen_hashes: set = set()

    for html_file in html_files:
        try:
            content = html_file.read_text(encoding="utf-8", errors="replace")
            if len(content) < 100:
                continue

            pairs = generate_ui_training_pairs(content, html_file)
            for pair in pairs[:max_pairs_per_file]:
                # Deduplicar por hash del output
                pair_hash = hashlib.md5(
                    pair["output"].encode("utf-8", errors="replace")
                ).hexdigest()
                if pair_hash not in seen_hashes:
                    seen_hashes.add(pair_hash)
                    all_pairs.append(pair)
        except Exception as e:
            logger.warning(f"Error reading {html_file}: {e}")

    # Guardar
    with open(output_path, "w", encoding="utf-8") as f:
        for pair in all_pairs:
            f.write(json.dumps(pair, ensure_ascii=False) + "\n")

    logger.info(f"UI training samples: {len(all_pairs)} → {output_path}")
    return str(output_path), len(all_pairs)


def main():
    parser = argparse.ArgumentParser(description="AURA UI Data Collector")
    parser.add_argument("--output", default="training-data-ui.jsonl",
                        help="Archivo de salida (JSONL)")
    parser.add_argument("--max-files", type=int, default=15,
                        help="Max archivos HTML a escanear")
    parser.add_argument("--max-pairs", type=int, default=15,
                        help="Max pares por archivo")
    args = parser.parse_args()

    path, count = collect_ui_data(
        output_file=args.output,
        max_files=args.max_files,
        max_pairs_per_file=args.max_pairs,
    )

    # Resumen por tipo
    type_counts: Dict[str, int] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            task = entry.get("metadata", {}).get("task", "unknown")
            type_counts[task] = type_counts.get(task, 0) + 1

    print(f"\n{'='*50}")
    print(f"UI Data Collection Complete")
    print(f"  Total samples: {count}")
    print(f"  Output: {path}")
    print(f"  By task type:")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"    {t}: {c}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
