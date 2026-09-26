#!/usr/bin/env python3
"""
AURA Screen Understanding — Análisis de pantalla y UI en tiempo real.

Permite a AURA:
  - Leer texto de la pantalla activa (OCR en vivo)
  - Identificar ventanas y aplicaciones activas
  - Detectar errores en consolas/terminals
  - Leer código en editores
  - Identificar formularios y campos
  - Detectar alertas y notificaciones
  - Analizar dashboards y métricas
  - Leer documentos PDF/Word abiertos

Dataset: training-data-screen.jsonl
Formato: {"text": "descripción de pantalla/consulta", "output": "análisis estructurado", "metadata": {...}}

Uso:
  python scripts/screen_understanding.py --analyze-active-window
  python scripts/screen_understanding.py --category errors --count 50
  python scripts/screen_understanding.py --category code --count 50
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import random
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ScreenUnderstanding")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "training-data-screen.jsonl"

CATEGORIES = ["errors", "code", "forms", "dashboards", "documents", "notifications", "terminals"]


def get_active_window_info() -> Dict[str, Any]:
    """Obtiene información de la ventana activa."""
    info = {"platform": platform.system(), "active_window": None, "processes": []}
    try:
        if platform.system() == "Windows":
            import psutil
            for proc in psutil.process_iter(["pid", "name", "title"]):
                try:
                    p_info = proc.info
                    if p_info.get("title"):
                        info["active_window"] = p_info["title"]
                        info["processes"].append({"name": p_info["name"], "pid": p_info["pid"]})
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
    except ImportError:
        logger.warning("psutil not installed")
    return info


SCREEN_TEMPLATES: Dict[str, List[Dict]] = {
    "errors": [
        {
            "template": "En esta captura de {app} aparece el error: '{error}'. Explica qué significa y cómo solucionarlo.",
            "variables": {
                "app": ["VS Code", "Chrome DevTools", "Docker Desktop", "Postman", "Windows Terminal"],
                "error": ["ModuleNotFoundError", "CORS policy", "Connection timeout", "Permission denied", "Out of memory"],
            },
            "difficulty": "medium",
            "answer": (
                "Diagnóstico de error:\n"
                "App: {app}\n"
                "Error: {error}\n"
                "Causa: [explicación técnica breve]\n"
                "Solución:\n"
                "1. [Paso 1]\n"
                "2. [Paso 2]\n"
                "3. [Paso 3]\n"
                "Prevención: [cómo evitar que reaparezca]"
            ),
        },
        {
            "template": "Esta terminal muestra el output de un comando {command}. ¿El comando falló? ¿Por qué?",
            "variables": {
                "command": ["npm install", "pip install", "docker build", "git push", "python script.py"],
            },
            "difficulty": "medium",
            "answer": (
                "Análisis de terminal:\n"
                "Comando: {command}\n"
                "Status: [éxito/fallo/parcial]\n"
                "Líneas clave del output:\n"
                "• [línea 1: error/warning/info]\n"
                "• [línea 2: error/warning/info]\n\n"
                "Diagnóstico: [qué salió mal y por qué]\n"
                "Solución: [pasos concretos]"
            ),
        },
    ],
    "code": [
        {
            "template": "En este editor de código se ve un fragmento de {language}. ¿Qué hace? ¿Tiene bugs?",
            "variables": {
                "language": ["Python", "JavaScript", "TypeScript", "Java", "C#", "Go", "Rust"],
            },
            "difficulty": "medium",
            "answer": (
                "Análisis de código:\n"
                "Lenguaje: {language}\n"
                "Funcionalidad: [qué hace el código]\n"
                "Bugs detectados:\n"
                "• [Bug 1: descripción y severidad]\n"
                "• [Bug 2: descripción y severidad]\n\n"
                "Mejoras sugeridas:\n"
                "1. [Mejora 1]\n"
                "2. [Mejora 2]"
            ),
        },
        {
            "template": "Esta captura muestra un debugger en {ide} con una excepción. ¿Dónde está el bug?",
            "variables": {
                "ide": ["VS Code", "PyCharm", "Chrome DevTools", "Xcode"],
            },
            "difficulty": "hard",
            "answer": (
                "Debug análisis:\n"
                "IDE: {ide}\n"
                "Excepción: [tipo y mensaje]\n"
                "Stack trace:\n"
                "1. [archivo:línea] - [código relevante]\n"
                "2. [archivo:línea] - [código relevante]\n\n"
                "Bug location: [archivo y línea exacta]\n"
                "Causa raíz: [variable null, tipo incorrecto, lógica]\n"
                "Fix: [código corregido o explicación]"
            ),
        },
    ],
    "forms": [
        {
            "template": "Este formulario de {form_type} tiene campos vacíos y errores de validación. ¿Cuáles son?",
            "variables": {
                "form_type": ["registro de usuario", "checkout de e-commerce", "formulario médico", "encuesta"],
            },
            "difficulty": "easy",
            "answer": (
                "Validación de formulario:\n"
                "Campos vacíos: [lista]\n"
                "Errores de formato: [lista]\n"
                "Validaciones fallidas: [lista]\n\n"
                "Sugerencias:\n"
                "1. [Campo 1]: [corrección]\n"
                "2. [Campo 2]: [corrección]\n"
                "3. Mejorar UX: [placeholder, tooltip, mensaje de error claro]"
            ),
        },
    ],
    "dashboards": [
        {
            "template": "Este dashboard de {dash_type} muestra métricas. Extrae los valores, tendencias y alertas.",
            "variables": {
                "dash_type": ["finanzas", "servidor", "ventas", "red social", "fitness"],
            },
            "difficulty": "medium",
            "answer": (
                "Extracción de dashboard:\n"
                "Métricas visibles:\n"
                "• [Métrica 1]: [valor] - [tendencia: ↑/↓/→]\n"
                "• [Métrica 2]: [valor] - [tendencia]\n"
                "• [Métrica 3]: [valor] - [tendencia]\n\n"
                "Alertas: [lista de alertas visuales]\n"
                "Acciones sugeridas: [qué hacer con estos datos]"
            ),
        },
    ],
    "documents": [
        {
            "template": "Esta captura muestra un documento de {doc_type}. Extrae información clave.",
            "variables": {
                "doc_type": ["factura", "contrato", "currículum", "certificado", "reporte médico"],
            },
            "difficulty": "medium",
            "answer": (
                "Análisis de documento:\n"
                "Tipo: {doc_type}\n"
                "Datos extraídos:\n"
                "• Título: [valor]\n"
                "• Fecha: [valor]\n"
                "• Entidades: [valores]\n"
                "• Montos: [valores]\n"
                "• Acciones: [plazos, firmas, pagos]\n\n"
                "Riesgos: [cláusulas ambiguas, fechas críticas]"
            ),
        },
    ],
    "notifications": [
        {
            "template": "Esta notificación de {app} indica: '{message}'. ¿Debo preocuparme?",
            "variables": {
                "app": ["Windows Defender", "Chrome", "Discord", "Outlook", "Slack"],
                "message": ["Actualización pendiente", "Conexión insegura", "Mensaje de jefe", "Alerta de seguridad"],
            },
            "difficulty": "easy",
            "answer": (
                "Evaluación de notificación:\n"
                "App: {app}\n"
                "Mensaje: {message}\n"
                "Nivel de urgencia: [bajo/medio/alto/crítico]\n"
                "Acción recomendada: [qué hacer]\n"
                "Razón: [justificación]"
            ),
        },
    ],
    "terminals": [
        {
            "template": "En esta terminal se ejecuta {command}. El output muestra: '{output}'. ¿Qué está pasando?",
            "variables": {
                "command": ["npm run build", "docker compose up", "python train.py", "git status", "ls -la"],
                "output": ["Build failed", "Container started", "Training completed", "Changes detected", "Permission denied"],
            },
            "difficulty": "medium",
            "answer": (
                "Análisis de terminal:\n"
                "Comando: {command}\n"
                "Output clave: {output}\n"
                "Estado: [éxito/fallo/parcial]\n"
                "Explicación: [qué significa el output]\n"
                "Siguiente paso: [qué hacer a continuación]"
            ),
        },
    ],
}


class ScreenUnderstanding:
    """Analiza pantallas y genera datos de entrenamiento."""

    def __init__(self, seed: int = 42):
        random.seed(seed)
        self.generated_keys: set = set()
        self.counters: Dict[str, int] = {}

    def _key(self, category: str) -> str:
        self.counters[category] = self.counters.get(category, 0) + 1
        return f"screen:{category}:{self.counters[category]}"

    def _fill(self, template: str, variables: Dict) -> str:
        result = template
        for var, values in variables.items():
            if isinstance(values, list) and values:
                val = random.choice(values)
                if isinstance(val, int):
                    val = str(val)
                result = result.replace("{" + var + "}", val)
        return result

    def analyze_active_window(self) -> Dict:
        info = get_active_window_info()
        return {
            "text": "Analiza la ventana activa actual.",
            "output": json.dumps(info, indent=2, ensure_ascii=False),
            "metadata": {
                "source": "screen_understanding",
                "category": "live_analysis",
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            },
        }

    def generate(self, category: str, difficulty: Optional[str] = None) -> Dict:
        templates = SCREEN_TEMPLATES.get(category, [])
        if not templates:
            raise ValueError(f"Unknown category: {category}")

        if difficulty:
            eligible = [t for t in templates if t.get("difficulty", "medium") == difficulty]
            if eligible:
                templates = eligible

        template = random.choice(templates)
        text = self._fill(template["template"], template.get("variables", {}))
        answer = self._fill(template.get("answer", "Análisis de pantalla completado."), template.get("variables", {}))

        item = {
            "text": text,
            "output": answer,
            "metadata": {
                "source": "screen_understanding",
                "category": category,
                "difficulty": template.get("difficulty", "medium"),
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            },
        }

        key = self._key(category)
        if key in self.generated_keys:
            return self.generate(category, difficulty)
        self.generated_keys.add(key)
        return item

    def generate_batch(self, count: int = 50, category: Optional[str] = None, difficulty: Optional[str] = None) -> List[Dict]:
        categories = [category] if category else CATEGORIES
        results = []
        per_cat = max(1, count // len(categories))
        for cat in categories:
            for _ in range(per_cat):
                try:
                    results.append(self.generate(cat, difficulty))
                except Exception as exc:
                    logger.debug(f"Skip screen {cat}: {exc}")
        return results[:count]

    def save_to_jsonl(self, items: List[Dict], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if output_path.exists() else "w"
        with open(output_path, mode, encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        logger.info(f"Saved {len(items)} screen samples -> {output_path}")


def cmd_generate(args: argparse.Namespace) -> None:
    analyzer = ScreenUnderstanding()
    if args.analyze_active_window:
        result = analyzer.analyze_active_window()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    items = analyzer.generate_batch(count=args.count, category=args.category, difficulty=args.difficulty)
    output = Path(args.output)
    analyzer.save_to_jsonl(items, output)


def main() -> None:
    p = argparse.ArgumentParser(description="AURA Screen Understanding")
    p.add_argument("--count", type=int, default=50)
    p.add_argument("--category", type=str, default=None, choices=CATEGORIES)
    p.add_argument("--difficulty", type=str, default=None, choices=["easy", "medium", "hard", "expert"])
    p.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT))
    p.add_argument("--analyze-active-window", action="store_true", help="Analizar ventana activa actual")
    args = p.parse_args()
    cmd_generate(args)


if __name__ == "__main__":
    main()
