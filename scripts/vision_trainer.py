#!/usr/bin/env python3
"""
AURA Vision Trainer — Entrenamiento de visión para asistente virtual tipo JARVIS.

Genera datos de entrenamiento para:
  - Descripción de imágenes y escenas
  - OCR (extracción de texto de imágenes/PDFs)
  - Detección de objetos en fotos
  - Análisis de UI por screenshot (ventanas, botones, errores)
  - Lectura de pantalla en tiempo real
  - Identificación de código en imágenes
  - Análisis de documentos (contratos, facturas, informes)
  - Detección de caras y expresiones (básico)

Dataset generado: training-data-vision.jsonl
Formato: {"text": "descripción/consulta visual", "output": "análisis estructurado", "metadata": {...}}

Uso:
  python scripts/vision_trainer.py --count 100 --category ocr
  python scripts/vision_trainer.py --count 100 --category ui_analysis
  python scripts/vision_trainer.py --count 100 --category documents
  python scripts/vision_trainer.py --all --count 200
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import textwrap
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("VisionTrainer")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "training-data-vision.jsonl"

CATEGORIES = ["ocr", "ui_analysis", "documents", "objects", "screens", "code_images", "faces"]


VISION_TEMPLATES: Dict[str, List[Dict]] = {
    "ocr": [
        {
            "template": "Extrae todo el texto visible de esta imagen de {context}. Devuelve el texto estructurado.",
            "variables": {
                "context": ["factura", "tarjeta de visita", "documento legal", "captura de chat", "email", "nota manuscrita"],
            },
            "difficulty": "easy",
            "answer": (
                "Análisis OCR:\n"
                "1. Detectar regiones de texto en la imagen.\n"
                "2. Aplicar reconocimiento de caracteres.\n"
                "3. Corregir errores comunes (confusión entre 0/O, 1/l/I).\n"
                "4. Estructurar por bloques lógicos.\n\n"
                "Texto extraído:\n"
                "[Aquí iría el texto reconocido de la imagen]"
            ),
        },
        {
            "template": "Lee el código que aparece en esta captura de pantalla de {ide}. ¿Qué hace?",
            "variables": {
                "ide": ["VS Code", "PyCharm", "Vim", "Sublime Text", "Notion"],
            },
            "difficulty": "medium",
            "answer": (
                "Análisis de código en imagen:\n"
                "1. Identificar lenguaje por sintaxis.\n"
                "2. Extraer código OCR + corrección.\n"
                "3. Analizar lógica: imports, funciones, estructuras.\n"
                "4. Detectar bugs o code smells.\n"
                "5. Sugerir mejoras.\n\n"
                "Código reconocido:\n"
                "[Código extraído]"
            ),
        },
        {
            "template": "Transcribe la tabla de esta imagen. Columnas: {cols}. Formato: JSON.",
            "variables": {
                "cols": ["nombre, precio, cantidad", "fecha, evento, ubicación", "producto, stock, precio, categoría"],
            },
            "difficulty": "medium",
            "answer": (
                "Tabla detectada:\n"
                "1. Detectar líneas de tabla.\n"
                "2. Mapear columnas por posición.\n"
                "3. Limpiar valores (símbolos $, espacios).\n"
                "4. Estructurar como lista de objetos.\n\n"
                "JSON:\n"
                "[{\"col1\": \"valor\", \"col2\": \"valor\", ...}]"
            ),
        },
    ],
    "ui_analysis": [
        {
            "template": "Analiza esta captura de pantalla de {app}. Describe la interfaz, identifica los elementos interactivos y sugiere mejoras de UX.",
            "variables": {
                "app": ["Chrome", "Discord", "Slack", "VS Code", "Windows Settings", "Spotify"],
            },
            "difficulty": "medium",
            "answer": (
                "Análisis UI:\n"
                "1. Layout general: grid/flex, jerarquía visual.\n"
                "2. Elementos interactivos: botones, inputs, menús.\n"
                "3. Contraste, tipografía, spacing.\n"
                "4. Accesibilidad: contraste WCAG, tamaño de touch target.\n"
                "5. Mejoras sugeridas:\n"
                "   - [Mejora 1]\n"
                "   - [Mejora 2]\n"
                "   - [Mejora 3]"
            ),
        },
        {
            "template": "En esta captura de {app}, identifica el error o advertencia visible. Explica qué significa y cómo solucionarlo.",
            "variables": {
                "app": ["Chrome DevTools", "VS Code terminal", "Windows Event Viewer", "Docker Desktop", "Postman"],
            },
            "difficulty": "hard",
            "answer": (
                "Diagnóstico:\n"
                "1. Localizar mensaje de error en la imagen.\n"
                "2. Clasificar tipo: sintaxis, runtime, configuración, permisos.\n"
                "3. Explicar causa raíz.\n"
                "4. Proponer solución paso a paso.\n"
                "5. Prevenir recurrencia.\n\n"
                "Error detectado: [mensaje OCR]\n"
                "Solución: [pasos concretos]"
            ),
        },
        {
            "template": "Compara esta captura de {app} con una interfaz ideal. ¿Qué elementos sobran, faltan o están mal posicionados?",
            "variables": {
                "app": ["formulario web", "dashboard de analytics", "app de tareas", "configuración de sistema"],
            },
            "difficulty": "hard",
            "answer": (
                "Comparativa UI:\n"
                "1. Elementos sobrantes: [lista]\n"
                "2. Elementos faltantes: [lista]\n"
                "3. Problemas de posición: [lista]\n"
                "4. Recomendaciones:\n"
                "   - Reorganizar secciones según frecuencia de uso.\n"
                "   - Aplicar principio de proximidad.\n"
                "   - Reducir carga cognitiva."
            ),
        },
    ],
    "documents": [
        {
            "template": "Analiza este documento de tipo {doc_type}. Extrae: título, fecha, entidades clave, montos y acciones requeridas.",
            "variables": {
                "doc_type": ["factura", "contrato", "informe médico", "certificado", "carta notarial"],
            },
            "difficulty": "medium",
            "answer": (
                "Análisis de documento:\n"
                "Tipo: {doc_type}\n"
                "Título: [extraído]\n"
                "Fecha: [extraída]\n"
                "Entidades: [personas/empresas involucradas]\n"
                "Montos: [valores económicos]\n"
                "Acciones requeridas: [plazos, firmas, pagos]\n"
                "Riesgos detectados: [cláusulas ambiguas, fechas críticas]"
            ),
        },
        {
            "template": "Resume esta página de {doc_type} en 3 bullet points. Destaca cifras, nombres y fechas.",
            "variables": {
                "doc_type": ["informe financiero", "artículo de investigación", "manual técnico", "reporte de ventas"],
            },
            "difficulty": "easy",
            "answer": (
                "Resumen visual:\n"
                "• [Punto 1: cifra/nombre/fecha clave]\n"
                "• [Punto 2: cifra/nombre/fecha clave]\n"
                "• [Punto 3: cifra/nombre/fecha clave]\n\n"
                "Detalles adicionales: [contexto relevante]"
            ),
        },
    ],
    "objects": [
        {
            "template": "Identifica los objetos principales en esta foto de {scene}. Describe su posición y estado.",
            "variables": {
                "scene": ["escritorio", "sala de reuniones", "cocina", "estación de trabajo", "parque"],
            },
            "difficulty": "easy",
            "answer": (
                "Detección de objetos:\n"
                "1. [Objeto 1] - posición: centro-izquierda, estado: encendido\n"
                "2. [Objeto 2] - posición: fondo-derecha, estado: apagado\n"
                "3. [Objeto 3] - posición: primer plano, estado: en uso\n\n"
                "Interpretación: [qué indica la escena]"
            ),
        },
        {
            "template": "¿Qué productos de {category} se detectan en esta imagen de tienda? Enuméralos con posición aproximada.",
            "variables": {
                "category": ["supermercado", "farmacia", "librería", "ferretería"],
            },
            "difficulty": "medium",
            "answer": (
                "Inventario visual:\n"
                "1. [Producto] - estante superior-izquierda\n"
                "2. [Producto] - estante medio-centro\n"
                "3. [Producto] - exhibidor frontal\n"
                "4. [Producto] - estante inferior-derecha\n\n"
                "Observaciones: [stock, rotación, precios visibles]"
            ),
        },
    ],
    "screens": [
        {
            "template": "En esta captura de pantalla, el usuario está en {app}. ¿Está realizando alguna acción peligrosa o tiene configuraciones inseguras?",
            "variables": {
                "app": ["navegador bancario", "configuración de router", "panel de admin", "terminal con sudo"],
            },
            "difficulty": "hard",
            "answer": (
                "Análisis de seguridad visual:\n"
                "1. Contexto: {app}\n"
                "2. Acciones visibles: [click en enlace sospechoso, descarga de archivo, comando peligroso]\n"
                "3. Configuraciones inseguras: [contraseña visible, puertos abiertos, permisos excesivos]\n"
                "4. Nivel de riesgo: [bajo/medio/alto/crítico]\n"
                "5. Recomendación: [acción inmediata]"
            ),
        },
        {
            "template": "Esta captura muestra un dashboard de {dashboard_type}. Extrae métricas visibles, alertas y tendencias.",
            "variables": {
                "dashboard_type": ["finanzas", "servidor", "red social", "e-commerce", "fitness"],
            },
            "difficulty": "medium",
            "answer": (
                "Extracción de dashboard:\n"
                "Métricas principales:\n"
                "• [Métrica 1]: [valor] - [tendencia: ↑/↓/→]\n"
                "• [Métrica 2]: [valor] - [tendencia]\n"
                "• [Métrica 3]: [valor] - [tendencia]\n\n"
                "Alertas: [lista de alertas visibles]\n"
                "Acciones sugeridas: [qué hacer con estos datos]"
            ),
        },
    ],
    "code_images": [
        {
            "template": "Este es un screenshot de código en {language}. Identifica el patrón de diseño, bugs potenciales y nivel de madurez.",
            "variables": {
                "language": ["Python", "JavaScript", "Java", "C++", "Rust", "Go"],
            },
            "difficulty": "hard",
            "answer": (
                "Análisis de código:\n"
                "Lenguaje: {language}\n"
                "Patrón detectado: [MVC/Singleton/Factory/Observer/otro]\n"
                "Bugs potenciales:\n"
                "• [Bug 1: tipo, línea aproximada, severidad]\n"
                "• [Bug 2: tipo, línea aproximada, severidad]\n\n"
                "Madurez: [prototipo/producción/legacy]\n"
                "Mejoras: [lista de refactorings]"
            ),
        },
    ],
    "faces": [
        {
            "template": "Analiza esta imagen con personas. Describe expresiones, posturas y contexto emocional aproximado.",
            "variables": {},
            "difficulty": "medium",
            "answer": (
                "Análisis de escena humana:\n"
                "Persona 1: [expresión: feliz/neutra/estresada], [postura: relajada/tensa], [contexto: trabajo/reunión]\n"
                "Persona 2: [expresión], [postura], [contexto]\n\n"
                "Interpretación:\n"
                "• Estado emocional general del grupo\n"
                "• Nivel de comodidad\n"
                "• Posibles conflictos o colaboraciones"
            ),
        },
    ],
}


class VisionTrainer:
    """Genera datos de entrenamiento para visión."""

    def __init__(self, seed: int = 42):
        random.seed(seed)
        self.generated_keys: set = set()
        self.counters: Dict[str, int] = {}

    def _key(self, category: str) -> str:
        self.counters[category] = self.counters.get(category, 0) + 1
        return f"vision:{category}:{self.counters[category]}"

    def _fill(self, template: str, variables: Dict) -> str:
        result = template
        for var, values in variables.items():
            if isinstance(values, list) and values:
                val = random.choice(values)
                if isinstance(val, int):
                    val = str(val)
                result = result.replace("{" + var + "}", val)
        return result

    def generate(self, category: str, difficulty: Optional[str] = None) -> Dict:
        templates = VISION_TEMPLATES.get(category, [])
        if not templates:
            raise ValueError(f"Unknown category: {category}")

        if difficulty:
            eligible = [t for t in templates if t.get("difficulty", "medium") == difficulty]
            if eligible:
                templates = eligible

        template = random.choice(templates)
        text = self._fill(template["template"], template.get("variables", {}))
        answer = self._fill(template.get("answer", "Análisis de imagen completado."), template.get("variables", {}))

        item = {
            "text": text,
            "output": answer,
            "metadata": {
                "source": "vision_trainer",
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
                    logger.debug(f"Skip vision {cat}: {exc}")
        return results[:count]

    def save_to_jsonl(self, items: List[Dict], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if output_path.exists() else "w"
        with open(output_path, mode, encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        logger.info(f"Saved {len(items)} vision samples -> {output_path}")


def cmd_generate(args: argparse.Namespace) -> None:
    trainer = VisionTrainer()
    categories = args.categories.split(",") if args.categories else None
    items = trainer.generate_batch(
        count=args.count,
        category=args.category,
        difficulty=args.difficulty,
    )
    output = Path(args.output)
    trainer.save_to_jsonl(items, output)


def main() -> None:
    p = argparse.ArgumentParser(description="AURA Vision Trainer")
    p.add_argument("--count", type=int, default=50)
    p.add_argument("--category", type=str, default=None, choices=CATEGORIES)
    p.add_argument("--categories", type=str, default=None, help="Categorías separadas por coma")
    p.add_argument("--difficulty", type=str, default=None, choices=["easy", "medium", "hard", "expert"])
    p.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT))
    args = p.parse_args()
    cmd_generate(args)


if __name__ == "__main__":
    main()