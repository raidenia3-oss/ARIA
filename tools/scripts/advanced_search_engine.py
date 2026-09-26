#!/usr/bin/env python3
"""
AURA Advanced Search Engine — Motor de búsqueda avanzada estructurada.

Genera pares Q/A especializados en:
  - Formulación de queries booleanas y filtros
  - Evaluación de fuentes y autoridad
  - Análisis de resultados de búsqueda
  - Estrategias de investigación profunda
  - Búsqueda académica y técnica

Uso:
  python scripts/advanced_search_engine.py --count 50 --output training-data-search.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AdvancedSearchEngine")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "training-data-search.jsonl"

SEARCH_TEMPLATES: List[Dict] = [
    {
        "template": "Formula una consulta boolean avanzada para buscar {A} en {B}. Usa operadores AND, OR, NOT, comillas y filetype:.",
        "variables": {
            "A": [
                "vulnerabilidades críticas en servidores Linux",
                "artículos sobre transformers en visión por computadora",
                "tutoriales de Docker multi-stage",
                "datasets públicos de imágenes médicas",
                "especificaciones de protocolos IoT",
            ],
            "B": ["Google Scholar", "Google estándar", "Bing", "DuckDuckGo", "GitHub search"],
        },
        "difficulty": "easy",
        "answer": (
            "Query propuesta para buscar '{A}' en {B}:\n"
            "  \"vulnerabilidades críticas\" AND servidores Linux filetype:pdf site:cve.mitre.org OR site:nvd.nist.gov\n"
            "  -buy -cheap -amazon\n\n"
            "Desglose:\n"
            "- Comillas para frases exactas.\n"
            "- AND/OR para combinar conceptos.\n"
            "- filetype: para filtrar por formato.\n"
            "- site: para limitar a dominios confiables.\n"
            "- (-) para excluir ruido comercial."
        ),
    },
    {
        "template": "Diseña una estrategia de investigación para {A}. Define: 1) Keywords principales y sinónimos, 2) Fuentes primarias y secundarias, 3) Criterios de inclusión/exclusión, 4) Método de validación de fuentes.",
        "variables": {
            "A": [
                "la seguridad de contratos inteligentes en Ethereum",
                "técnicas de compresión de modelos LLM",
                "arquitecturas de microservicios para fintech",
                "métodos de detección de sesgo en IA",
                "optimización de bases de datos de series temporales",
            ],
        },
        "difficulty": "medium",
        "answer": (
            "Estrategia de investigación sobre '{A}':\n"
            "1. Keywords: términos principales + sinónimos + variantes en inglés.\n"
            "2. Fuentes primarias: papers (arXiv, ACL, IEEE), documentación oficial, blogs de ingeniería senior.\n"
            "3. Filtros de calidad: peer-review, citas, fecha de publicación, autoridad del autor.\n"
            "4. Validación: cruzar al menos 3 fuentes independientes; buscar réplicas o refutaciones."
        ),
    },
    {
        "template": "Evalúa la siguiente fuente para decidir si es confiable para un trabajo académico sobre {A}. Considera autoridad, precisión, objetividad, vigencia y cobertura.\n\nFuente: {fuente}",
        "variables": {
            "A": ["cambio climático", "inteligencia artificial", "medicina alternativa", "historia contemporánea", "economía"],
            "fuente": [
                "Artículo en revista Nature (2024) - Estudio revisado por pares con n=5000",
                "Post de blog anónimo (2019) - Sin referencias, tono sensacionalista",
                "Wiki community edit (hace 2 horas) - Contenido sobre medicina",
                "Paper preprint arXiv (2023) - No revisado, pero del MIT",
                "Nota de prensa corporativa - Sin metodología descrita",
            ],
        },
        "difficulty": "medium",
        "answer": (
            "Evaluación CRAAP para trabajo sobre '{A}':\n"
            "- Currency: priorizar fuentes de 2023-2024.\n"
            "- Relevance: {fuente} - {'alta' if 'Nature' in '{fuente}' or 'arXiv' in '{fuente}' else 'media/baja'}.\n"
            "- Authority: {'Alta' if 'Nature' in '{fuente}' or 'MIT' in '{fuente}' or 'preprint' in '{fuente}' else 'Baja'}.\n"
            "- Accuracy: {'Referencias y datos' if 'revisado' in '{fuente}' or 'preprint' in '{fuente}' else 'Sin metodología'}.\n"
            "- Purpose: {'Académico' if 'Nature' in '{fuente}' or 'preprint' in '{fuente}' else 'Marketing/Opinión'}.\n"
            "Conclusión: {'Apta para trabajo académico' if 'Nature' in '{fuente}' or 'MIT' in '{fuente}' else 'Descartar o usar solo como referencia secundaria'}."
        ),
    },
    {
        "template": "Un investigador necesita encontrar todos los papers de {A} publicados entre {y1} y {y2} que citen el paper seminal de {B}. Describe la estrategia paso a paso usando Google Scholar, Semantic Scholar y técnicas de citation chaining.",
        "variables": {
            "A": ["graph neural networks", "federated learning", "diffusion models", "prompt engineering", "constitutional AI"],
            "y1": [2018, 2019, 2020, 2021, 2022],
            "y2": [2023, 2024, 2025],
            "B": ["Kipf & Welling (2016)", "McMahan et al. (2017)", "Ho et al. (2020)", "Brown et al. (2020)", "Bai et al. (2022)"],
        },
        "difficulty": "hard",
    },
    {
        "template": "Analiza los siguientes resultados para la query '{query}' y clasifica cada uno por: autoridad (alta/media/baja), relevancia (directa/parcial/irrelevante) y vigencia (actual/semidesactualizado/obsoleto). Luego, selecciona los 3 mejores para un informe ejecutivo.\n\n{results}",
        "variables": {
            "query": ["Python asyncio", "cybersecurity tools 2024", "LLM quantization", "Rust vs Go performance"],
            "results": [
                "\n1. docs.python.org/3/library/asyncio.html (2024) - Documentación oficial\n2. Blog personal 'Asyncio intro' (2019) - Tutorial básico\n3. Stack Overflow Q&A (2023) - Pregunta sobre EventLoop\n4. Reddit r/Python thread (2024) - Discusión sobre aiohttp vs requests\n5. Curso Udemy (2022) - 'Python Async Mastery'\n6. Paper arXiv 'Scalable Async Patterns' (2024) - Revisado\n",
                "\n1. NIST Cybersecurity Framework 2.0 (2024) - Guía oficial\n2. Blog corporativo 'Top 10 Security Tools' (2023) - Marketing\n3. GitHub repo 'awesome-security' (2024) - Curado comunitario\n4. Wikipedia 'Cybersecurity' (2023) - General\n5. Foro no verificado 'Best Tools 2021' - Desactualizado\n6. CISA Alert AA24-123A (2024) - Alerta oficial\n",
            ],
        },
        "difficulty": "medium",
    },
    {
        "template": "Un equipo debe responder rápidamente a la pregunta: '{pregunta}'. Diseña un flujo de búsqueda que garantice respuesta en {t} minutos con 90% de confianza. Define fuentes, queries de respaldo y criterios de parada.",
        "variables": {
            "pregunta": [
                "¿Cuál es el último CVE crítico de Kubernetes?",
                "¿Cómo resolver el error de memory leak en Node.js 20?",
                "¿Qué opciones de deploy hay para modelos LLM en AWS?",
                "¿Cuál es el estado actual de la regulación de IA en la UE?",
            ],
            "t": [5, 10, 15, 30],
        },
        "difficulty": "hard",
    },
    {
        "template": "Diseña un sistema de búsqueda interna para una empresa con {n} documentos técnicos. Define: esquema de índice, estrategia de tokenización, ranking por relevancia, y manejo de sinónimos técnicos (ej: 'K8s' = 'Kubernetes').",
        "variables": {
            "n": [10000, 100000, 1000000],
        },
        "difficulty": "expert",
    },
    {
        "template": "Encuentra 10 artículos de investigación revisados por pares sobre {A} publicados desde {year}. Proporciona título, autores, revista, año y una frase clave de cada uno.",
        "variables": {
            "A": ["federated learning", "diffusion models", "graph neural networks", "prompt engineering", "constitutional AI"],
            "year": [2020, 2021, 2022, 2023],
        },
        "difficulty": "hard",
    },
    {
        "template": "Evalúa la calidad de los siguientes resultados para la query '{query}':\n\n{results}\n\nClasifica cada uno por: CRAAP (Currency, Relevance, Authority, Accuracy, Purpose).",
        "variables": {
            "query": ["Python asyncio", "cybersecurity tools", "LLM quantization", "cloud architecture"],
            "results": [
                "\n1. docs.python.org (2024) - Documentación oficial\n2. Medium article (2020) - 'Asyncio en 10 minutos'\n3. Stack Overflow (2023) - Pregunta popular\n4. Curso Udemy (2022) - 'Python Async'\n5. Paper arXiv (2024) - 'Scalable Async Patterns'\n",
                "\n1. NIST Guide (2023) - Framework oficial\n2. Blog corporativo (2023) - Top 10 tools\n3. GitHub repo (2024) - Awesome-security\n4. Wikipedia (2023) - Historia\n5. Foro anónimo (2021) - Best tools\n",
            ],
        },
        "difficulty": "medium",
    },
    {
        "template": "Diseña una estrategia de búsqueda sistemática (protocolo PRISMA) para una revisión sistemática sobre {A}. Define PICO, criterios de inclusión, bases de datos y estrategia de extracción de datos.",
        "variables": {
            "A": ["efectividad de terapias digitales para ansiedad", "impacto de microplásticos en salud humana", "rendimiento de transformers en edge devices", "seguridad de smart contracts en finanzas descentralizadas"],
        },
        "difficulty": "expert",
    },
    {
        "template": "Un periodista necesita verificar una afirmación viral: '{claim}'. Diseña un flujo de fact-checking en 3 niveles: 1) verificación rápida, 2) investigación profunda, 3) consulta a expertos.",
        "variables": {
            "claim": [
                "Beber agua de limón en ayunas cura el cáncer",
                "Los 5G propagan virus",
                "La IA ya supera a los humanos en creatividad",
                "Python es el lenguaje más rápido para procesamiento de datos",
                "Se puede clonar un WhatsApp con solo el número de teléfono",
            ],
        },
        "difficulty": "medium",
    },
    {
        "template": "Encuentra el dataset abierto más adecuado para entrenar un modelo de {A}. Define criterios de selección (tamaño, licencia, calidad de etiquetas, sesgo) y describe el proceso de descarga y validación.",
        "variables": {
            "A": ["detección de fraude en tarjetas de crédito", "clasificación de imágenes médicas", "predicción de demanda de transporte", "detección de spam en correos", "reconocimiento de voz en español"],
        },
        "difficulty": "medium",
    },
]


class AdvancedSearchEngine:
    """Genera contenido especializado en búsqueda avanzada."""

    def __init__(self, seed: int = 42):
        random.seed(seed)
        self.generated_keys: set = set()

    def _fill_template(self, template: str, variables: Dict) -> str:
        result = template
        for var, values in variables.items():
            if isinstance(values, list):
                val = random.choice(values)
                if isinstance(val, int):
                    val = str(val)
                result = result.replace("{" + var + "}", val)
        remaining = re.findall(r"\{([A-Z0-9_]+)\}", result)
        for var in remaining:
            result = result.replace("{" + var + "}", f"[{var}]")
        return result

    def _key(self, idx: int, difficulty: str) -> str:
        return f"{idx}:{difficulty}"

    def generate(self, difficulty: Optional[str] = None) -> Dict:
        if difficulty is None:
            difficulty = random.choice(["easy", "medium", "hard", "expert"])

        eligible = [t for t in SEARCH_TEMPLATES if t.get("difficulty", "medium") == difficulty]
        if not eligible:
            eligible = SEARCH_TEMPLATES

        template = random.choice(eligible)
        idx = SEARCH_TEMPLATES.index(template)
        key = self._key(idx, difficulty)

        if key in self.generated_keys:
            return self.generate(difficulty)
        self.generated_keys.add(key)

        question = self._fill_template(template["template"], template.get("variables", {}))
        raw_answer = template.get("answer", self._default_answer(difficulty))
        answer = self._fill_template(raw_answer, template.get("variables", {}))

        return {
            "text": question,
            "output": answer,
            "metadata": {
                "source": "advanced_search",
                "category": "search",
                "difficulty": difficulty,
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            },
        }

    def _default_answer(self, difficulty: str) -> str:
        return (
            "Respuesta estructurada de búsqueda avanzada:\n"
            "1. Interpretación de la necesidad de información.\n"
            "2. Formulación de estrategia de búsqueda.\n"
            "3. Ejecución y refinamiento.\n"
            "4. Evaluación de fuentes.\n"
            "5. Síntesis y presentación de conclusiones.\n"
            f"Se adapta al nivel de dificultad '{difficulty}'."
        )

    def generate_batch(
        self,
        count: int = 50,
        difficulty: Optional[str] = None,
    ) -> List[Dict]:
        results = []
        for _ in range(count):
            try:
                results.append(self.generate(difficulty))
            except Exception as exc:
                logger.debug(f"Skip search task: {exc}")
        return results

    def save_to_jsonl(self, tasks: List[Dict], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for task in tasks:
                f.write(json.dumps(task, ensure_ascii=False) + "\n")
        logger.info(f"Saved {len(tasks)} search tasks -> {output_path}")


def cmd_generate(args: argparse.Namespace) -> None:
    engine = AdvancedSearchEngine(seed=42)
    tasks = engine.generate_batch(count=args.count, difficulty=args.difficulty)
    output = Path(args.output)
    engine.save_to_jsonl(tasks, output)


def main() -> None:
    p = argparse.ArgumentParser(description="AURA Advanced Search Engine")
    p.add_argument("--count", type=int, default=50)
    p.add_argument("--difficulty", type=str, default=None, choices=["easy", "medium", "hard", "expert"])
    p.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT))
    args = p.parse_args()
    cmd_generate(args)


if __name__ == "__main__":
    main()
