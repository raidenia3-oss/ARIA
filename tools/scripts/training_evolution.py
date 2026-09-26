#!/usr/bin/env python3
"""
AURA Training Evolution — Evolución del espacio de entrenamiento.

Capacidades:
  - Mezcla inteligente de datasets por dificultad y categoría
  - Generación de variaciones de personalidad (científico, poeta, profesor, narrador, amigo, técnico)
  - Introducción de contexto conversacional (historial, preferencias, memoria)
  - Transformación de samples para mejorar lógica de texto (coherencia, relevancia, estructura)
  - Generación de pares "pregunta difícil -> razonamiento paso a paso"
  - Parafraseo y expansión de respuestas
  - Inyección de contexto en preguntas/respuestas

Dataset: training-data-evolved.jsonl

Uso:
  python scripts/training_evolution.py --base training-data.jsonl --personality scientist --count 100
  python scripts/training_evolution.py --base training-data.jsonl --personality storyteller --count 100
  python scripts/training_evolution.py --evolve-all --count 200
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TrainingEvolution")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "training-data-evolved.jsonl"

PERSONALITIES: Dict[str, Dict[str, Any]] = {
    "scientist": {
        "name": "Científico",
        "tone": "riguroso, objetivo, metódico",
        "style": "Usa terminología precisa, cita principios, estructura lógica, separa hechos de hipótesis.",
        "prefixes": ["Según el método científico:", "Hipótesis:", "Evidencia:", "Conclusión basada en datos:"],
    },
    "poet": {
        "name": "Poeta",
        "tone": "expresivo, metafórico, emotivo",
        "style": "Usa metáforas, ritmo, imágenes sensoriales, juega con las palabras.",
        "prefixes": ["Imagina que:", "Como un:", "En el lienzo de:", "Entre líneas:"],
    },
    "professor": {
        "name": "Profesor",
        "tone": "pedagógico, claro, estructurado",
        "style": "Explica desde lo básico, usa ejemplos, hace preguntas retóricas, verifica comprensión.",
        "prefixes": ["Vamos por partes:", "Primero, recordemos:", "En términos simples:", "Piénsalo así:"],
    },
    "storyteller": {
        "name": "Narrador",
        "tone": "narrativo, envolvente, dramático",
        "style": "Crea historias, personajes, conflicto y resolución. Usa tensión narrativa.",
        "prefixes": ["Había una vez:", "En un mundo donde:", "El destino de:", "Lo que nadie te contó:"],
    },
    "friend": {
        "name": "Amigo",
        "tone": "cercano, relajado, honesto",
        "style": "Lenguaje coloquial, humor suave, consejos directos, complicidad.",
        "prefixes": ["Oye,", "Mira,", "Te seré sincero:", "Entre nosotros:"],
    },
    "technician": {
        "name": "Técnico",
        "tone": "preciso, detallado, pragmático",
        "style": "Pasos numerados, comandos exactos, configuraciones, troubleshooting.",
        "prefixes": ["Procedimiento:", "Configuración:", "Diagnóstico:", "Solución paso a paso:"],
    },
}

CONTEXT_TEMPLATES = [
    "Recordando nuestra conversación anterior sobre {topic}, ahora...",
    "Basado en lo que me contaste antes: {topic}...",
    "Continuando con el tema de {topic}...",
    "Retomando tu consulta anterior sobre {topic}...",
    "En relación a {topic} que discutimos...",
]

REASONING_STEPS = [
    "Identificar el problema principal.",
    "Descomponer en subproblemas.",
    "Analizar cada componente.",
    "Buscar patrones o analogías.",
    "Evaluar soluciones posibles.",
    "Seleccionar la óptima.",
    "Implementar y verificar.",
]


class TrainingEvolution:
    """Evoluciona el espacio de entrenamiento para mejorar lógica, personalidad y contexto."""

    def __init__(self, seed: int = 42):
        random.seed(seed)
        self.generated_keys: set = set()

    def _key(self, text: str) -> str:
        return text[:80]

    def load_base(self, path: Path) -> List[Dict]:
        items = []
        if not path.exists():
            logger.warning(f"Base file not found: {path}")
            return items
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        items.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        logger.info(f"Loaded {len(items)} base samples from {path}")
        return items

    def apply_personality(self, item: Dict, personality: str) -> Dict:
        profile = PERSONALITIES.get(personality, PERSONALITIES["professor"])
        prefix = random.choice(profile["prefixes"])
        text = item.get("text", "")
        output = item.get("output", "")
        if text and not any(text.startswith(p) for p in ["[", "(", "•", "-", "1.", "2.", "3.", "4.", "5."]):
            text = f"{prefix} {text}"
        if output:
            output = f"[{profile['name']} - {profile['tone']}]\n\n{profile['style']}\n\n{output}"
        result = {
            "text": text,
            "output": output,
            "metadata": {
                "source": "training_evolution",
                "personality": personality,
                "original_source": item.get("metadata", {}).get("source", "unknown"),
                "timestamp": datetime.now().isoformat(),
            },
        }
        return result

    def add_context(self, item: Dict, context_topic: Optional[str] = None) -> Dict:
        text = item.get("text", "")
        topic = context_topic or random.choice(["IA", "programación", "ciencia", "historia", "filosofía", "arte", "matemáticas"])
        template = random.choice(CONTEXT_TEMPLATES).format(topic=topic)
        new_text = f"{template} {text}"
        result = {
            "text": new_text,
            "output": item.get("output", ""),
            "metadata": {
                "source": "training_evolution",
                "context_injected": True,
                "context_topic": topic,
                "timestamp": datetime.now().isoformat(),
            },
        }
        return result

    def improve_logic(self, item: Dict) -> Dict:
        text = item.get("text", "")
        output = item.get("output", "")
        if any(word in text.lower() for word in ["por qué", "cómo", "explica", "razón", "lógica"]):
            steps = "\n".join([f"{i+1}. {step}" for i, step in enumerate(random.sample(REASONING_STEPS, 4))])
            output = f"Razonamiento paso a paso:\n{steps}\n\nRespuesta final: {output}"
        result = {
            "text": text,
            "output": output,
            "metadata": {
                "source": "training_evolution",
                "logic_improved": True,
                "timestamp": datetime.now().isoformat(),
            },
        }
        return result

    def paraphrase(self, item: Dict, intensity: str = "medium") -> Dict:
        text = item.get("text", "")
        output = item.get("output", "")
        if intensity == "light":
            text = text.replace("?", ", ¿verdad?") if "?" in text else text
        elif intensity == "medium":
            text = re.sub(r"\b(y)\b", "además", text)
            text = re.sub(r"\b(pero)\b", "sin embargo", text)
            text = re.sub(r"\b(porque)\b", "debido a que", text)
            text = re.sub(r"\b(entonces)\b", "por lo tanto", text)
        elif intensity == "heavy":
            words = text.split()
            if len(words) > 5:
                words = words[:len(words)//2] + ["...", "en resumen:"] + words[len(words)//2:]
                text = " ".join(words)
        result = {
            "text": text,
            "output": output,
            "metadata": {
                "source": "training_evolution",
                "paraphrase_intensity": intensity,
                "timestamp": datetime.now().isoformat(),
            },
        }
        return result

    def expand_response(self, item: Dict) -> Dict:
        output = item.get("output", "")
        expansions = [
            "\n\nNota adicional: este punto es crucial porque establece la base para comprender el resto.",
            "\n\nEjemplo práctico: si aplicamos esto a un caso real, veríamos...",
            "\n\nDato curioso: muchos expertos coinciden en que este enfoque es fundamental.",
            "\n\nEn resumen: lo clave aquí es recordar que la consistencia es más importante que la perfección.",
        ]
        output = output + random.choice(expansions)
        result = {
            "text": item.get("text", ""),
            "output": output,
            "metadata": {
                "source": "training_evolution",
                "expanded": True,
                "timestamp": datetime.now().isoformat(),
            },
        }
        return result

    def generate_difficult_pairs(self, base_items: List[Dict], count: int = 50) -> List[Dict]:
        results = []
        difficult_templates = [
            ("Si {concept} es verdadero, ¿por qué {counter}?", "Razonamiento:\n1. Premisa: {concept}\n2. Contrapregunta: {counter}\n3. Análisis lógico: [pasos]\n4. Conclusión: [respuesta matizada]"),
            ("¿Qué pasa si cambiamos {param} en {scenario}?", "Análisis de sensibilidad:\n1. Estado base: {scenario}\n2. Cambio: {param}\n3. Efecto inmediato: [X]\n4. Efecto secundario: [Y]\n5. Conclusión: [Z]"),
            ("Explica la contradicción entre {a} y {b}.", "Resolución de contradicción:\n1. Contexto de {a}: [validez]\n2. Contexto de {b}: [validez]\n3. Punto de tensión: [dónde chocan]\n4. Síntesis: [cómo reconciliarlos]"),
        ]
        concepts = ["la entropía", "la gravedad cuántica", "el libre albedrío", "la ética en IA", "la conciencia", "el tiempo"]
        params = ["temperatura", "presupuesto", "tiempo", "personal", "tecnología"]
        scenarios = ["un proyecto de software", "una startup", "una investigación", "una campaña"]
        for _ in range(count):
            template = random.choice(difficult_templates)
            a, b = random.sample(concepts, 2)
            param = random.choice(params)
            scenario = random.choice(scenarios)
            text = template[0].format(concept=random.choice(concepts), counter=random.choice(concepts), param=param, scenario=scenario, a=a, b=b)
            output = template[1].format(concept=random.choice(concepts), counter=random.choice(concepts), param=param, scenario=scenario, a=a, b=b)
            results.append({
                "text": text,
                "output": output,
                "metadata": {
                    "source": "training_evolution",
                    "type": "difficult_pair",
                    "difficulty": "hard",
                    "timestamp": datetime.now().isoformat(),
                },
            })
        return results

    def evolve(self, base_items: List[Dict], personalities: List[str], count: int = 100, add_context: bool = True, improve_logic: bool = True, add_difficult: bool = True) -> List[Dict]:
        results = []
        per_personality = max(1, count // len(personalities))
        for personality in personalities:
            for _ in range(per_personality):
                if not base_items:
                    continue
                item = random.choice(base_items)
                key = self._key(item.get("text", "")) + personality
                if key in self.generated_keys:
                    continue
                self.generated_keys.add(key)
                result = self.apply_personality(item, personality)
                if add_context and random.random() > 0.5:
                    result = self.add_context(result)
                if improve_logic and random.random() > 0.6:
                    result = self.improve_logic(result)
                if random.random() > 0.7:
                    result = self.expand_response(result)
                results.append(result)
        if add_difficult:
            results.extend(self.generate_difficult_pairs(base_items, count=max(10, count // 10)))
        return results[:count]

    def save_to_jsonl(self, items: List[Dict], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if output_path.exists() else "w"
        with open(output_path, mode, encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        logger.info(f"Saved {len(items)} evolved samples -> {output_path}")


def cmd_evolve(args: argparse.Namespace) -> None:
    base_path = Path(args.base)
    evolver = TrainingEvolution()
    base_items = evolver.load_base(base_path)
    personalities = args.personalities.split(",") if args.personalities else list(PERSONALITIES.keys())
    items = evolver.evolve(
        base_items=base_items,
        personalities=personalities,
        count=args.count,
        add_context=not args.no_context,
        improve_logic=not args.no_logic,
        add_difficult=not args.no_difficult,
    )
    output = Path(args.output)
    evolver.save_to_jsonl(items, output)


def main() -> None:
    p = argparse.ArgumentParser(description="AURA Training Evolution")
    p.add_argument("--base", type=str, required=True, help="Dataset base")
    p.add_argument("--personalities", type=str, default=",".join(PERSONALITIES.keys()), help="Personalidades separadas por coma")
    p.add_argument("--count", type=int, default=100)
    p.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT))
    p.add_argument("--no-context", action="store_true", help="No inyectar contexto")
    p.add_argument("--no-logic", action="store_true", help="No mejorar lógica")
    p.add_argument("--no-difficult", action="store_true", help="No generar pares difíciles")
    args = p.parse_args()
    cmd_evolve(args)


if __name__ == "__main__":
    main()
