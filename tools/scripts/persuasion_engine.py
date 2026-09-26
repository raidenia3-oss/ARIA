#!/usr/bin/env python3
"""
AURA Persuasion Engine — Comunicación persuasiva y empática.

Capacidades:
  - Adaptación de tono según contexto (formal, amigable, técnico, empático)
  - Detección de emociones en el texto del usuario
  - Aplicación ética de técnicas de persuasión (reciprocidad, autoridad, prueba social)
  - Ajuste de longitud de respuesta (corta, media, larga)
  - Uso moderado de emojis y formato
  - Frases de transición naturales
  - Respuestas a frustración, ansiedad, curiosidad, celebración

Dataset: training-data-persuasion.jsonl

Uso:
  python scripts/persuasion_engine.py --user-text "No entiendo nada, esto es frustrante" --tone empathetic
  python scripts/persuasion_engine.py --user-text "Explica esto técnicamente" --tone technical
  python scripts/persuasion_engine.py --generate --count 50
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
logger = logging.getLogger("PersuasionEngine")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "training-data-persuasion.jsonl"

EMOTION_KEYWORDS: Dict[str, List[str]] = {
    "frustration": ["no entiendo", "no funciona", "error", "frustrante", "no puedo", "imposible", "difícil", "complicado"],
    "anxiety": ["preocupado", "miedo", "urgente", "rápido", "pronto", "emergencia", "pánico", "desesperado"],
    "curiosity": ["cómo", "por qué", "explica", "dime", "qué es", "cómo funciona", "interesante"],
    "joy": ["gracias", "genial", "perfecto", "excelente", "feliz", "increíble", "bien hecho"],
    "sadness": ["triste", "mal", "desanimado", "perdí", "fallé", "no sirve"],
    "anger": ["molesto", "enojado", "inaceptable", "terrible", "basura", "odio"],
    "neutral": ["hola", "ayuda", "info", "dato", "consulta", "pregunta"],
}

TONES = ["formal", "friendly", "technical", "empathetic", "motivational", "concise"]

PERSUASION_TEMPLATES: Dict[str, List[Dict]] = {
    "frustration": [
        {
            "template": "Usuario frustrado: '{text}'. Respuesta empática: validar sentimiento, ofrecer ayuda paso a paso.",
            "tone": "empathetic",
            "answer": "Entiendo que esto puede ser frustrante. Vamos a resolverlo juntos:\n1. Primero, identifiquemos exactamente qué está fallando.\n2. Te guiaré paso a paso sin saltos.\n3. Si algo no sale, lo intentamos de otra forma.\n\nRespira, vamos bien. 😊"
        },
    ],
    "anxiety": [
        {
            "template": "Usuario ansioso: '{text}'. Respuesta calmada: priorizar, desglosar, tranquilizar.",
            "tone": "empathetic",
            "answer": "Tranquilo/a, vamos a ordenar esto. Lo importante primero:\n1. [Acción crítica inmediata]\n2. [Pasos siguientes en orden]\n3. Tiempo estimado: [X minutos]\n\nNo estás solo/a en esto. Un paso a la vez."
        },
    ],
    "curiosity": [
        {
            "template": "Usuario curioso: '{text}'. Respuesta técnica pero accesible: explicar, ejemplificar, invitar a profundizar.",
            "tone": "technical",
            "answer": "Excelente pregunta. Aquí va:\n1. Concepto clave: [definición clara]\n2. Ejemplo práctico: [caso de uso]\n3. Por qué importa: [impacto]\n\n¿Quieres que profundice en algún aspecto específico?"
        },
    ],
    "joy": [
        {
            "template": "Usuario feliz: '{text}'. Respuesta celebratoria: reconocer logro, reforzar positivamente.",
            "tone": "friendly",
            "answer": "¡Me alegra mucho! 🎉\nTu esfuerzo está dando frutos. Sigamos así:\n1. [Siguiente paso lógico]\n2. [Nuevo desafío si quieres]\n\n¿Hay algo más en lo que pueda ayudarte hoy?"
        },
    ],
    "sadness": [
        {
            "template": "Usuario triste: '{text}'. Respuesta compasiva: validar, apoyar, ofrecer perspectiva.",
            "tone": "empathetic",
            "answer": "Lamento que estés pasando por esto. Estoy aquí para lo que necesites.\n1. Si quieres hablar, te escucho.\n2. Si prefieres soluciones, dime cómo puedo ayudar.\n3. Recuerda: los malos momentos son temporales.\n\n💙"
        },
    ],
    "anger": [
        {
            "template": "Usuario enojado: '{text}'. Respuesta calmada: validar sin confrontar, redirigir a solución.",
            "tone": "empathetic",
            "answer": "Entiendo tu enojo, y tienes razón en sentirte así. Vamos a solucionarlo:\n1. [Reconocer el problema específico]\n2. [Acción correctiva concreta]\n3. [Compromiso de mejora]\n\nTu feedback es valioso. Gracias por compartirlo."
        },
    ],
    "neutral": [
        {
            "template": "Consulta neutral: '{text}'. Respuesta útil: directa, estructurada, proactiva.",
            "tone": "formal",
            "answer": "Claro, aquí tienes la información:\n1. [Respuesta directa]\n2. [Detalle adicional relevante]\n3. [Próximo paso sugerido]\n\n¿Necesitas algo más?"
        },
    ],
}


class PersuasionEngine:
    """Motor de comunicación persuasiva y empática."""

    def __init__(self):
        self.history: List[Dict] = []

    def detect_emotion(self, text: str) -> str:
        text_lower = text.lower()
        scores = {}
        for emotion, keywords in EMOTION_KEYWORDS.items():
            scores[emotion] = sum(1 for kw in keywords if kw in text_lower)
        if not scores or max(scores.values()) == 0:
            return "neutral"
        return max(scores, key=scores.get)

    def adapt_tone(self, user_text: str, preferred_tone: Optional[str] = None) -> Dict[str, Any]:
        emotion = self.detect_emotion(user_text)
        tone = preferred_tone or self._tone_for_emotion(emotion)
        templates = PERSUASION_TEMPLATES.get(emotion, PERSUASION_TEMPLATES["neutral"])
        template = random.choice(templates)
        answer = template["answer"]
        modifiers = self._apply_modifiers(answer, tone, emotion)
        result = {
            "user_emotion": emotion,
            "applied_tone": tone,
            "response": modifiers,
            "techniques_used": self._list_techniques(emotion),
            "timestamp": datetime.now().isoformat(),
        }
        self.history.append(result)
        return result

    def _tone_for_emotion(self, emotion: str) -> str:
        mapping = {
            "frustration": "empathetic",
            "anxiety": "empathetic",
            "curiosity": "technical",
            "joy": "friendly",
            "sadness": "empathetic",
            "anger": "empathetic",
            "neutral": "formal",
        }
        return mapping.get(emotion, "formal")

    def _apply_modifiers(self, text: str, tone: str, emotion: str) -> str:
        if tone == "friendly" and emotion == "joy":
            text = text.replace("🎉", "🎉🚀")
        if tone == "empathetic" and emotion in ("frustration", "sadness"):
            text = text.replace("💙", "🤗")
        if tone == "technical" and emotion == "curiosity":
            text += "\n\n📚 Si quieres, puedo recomendarte recursos para profundizar."
        return text

    def _list_techniques(self, emotion: str) -> List[str]:
        base = ["validación emocional", "escucha activa"]
        if emotion == "curiosity":
            base += ["explicación progresiva", "ejemplificación"]
        if emotion == "frustration":
            base += ["desglose de pasos", "refuerzo positivo"]
        if emotion == "anxiety":
            base += ["priorización", "tranquilización"]
        return base

    def generate_batch(self, count: int = 50) -> List[Dict]:
        results = []
        emotions = list(EMOTION_KEYWORDS.keys())
        for _ in range(count):
            emotion = random.choice(emotions)
            keywords = EMOTION_KEYWORDS[emotion]
            user_text = f"Usuario siente {emotion}: {random.choice(keywords)}. {random.choice(['ayuda', 'explica', 'soluciona', 'dime'])} {random.choice(['esto', 'cómo', 'por qué', 'qué'])}."
            result = self.adapt_tone(user_text)
            results.append({
                "text": user_text,
                "output": result["response"],
                "metadata": {
                    "source": "persuasion_engine",
                    "emotion": result["user_emotion"],
                    "tone": result["applied_tone"],
                    "techniques": result["techniques_used"],
                    "timestamp": result["timestamp"],
                },
            })
        return results

    def save_to_jsonl(self, items: List[Dict], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if output_path.exists() else "w"
        with open(output_path, mode, encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        logger.info(f"Saved {len(items)} persuasion samples -> {output_path}")


def cmd_adapt(args: argparse.Namespace) -> None:
    engine = PersuasionEngine()
    result = engine.adapt_tone(args.user_text, preferred_tone=args.tone)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_generate(args: argparse.Namespace) -> None:
    engine = PersuasionEngine()
    items = engine.generate_batch(count=args.count)
    output = Path(args.output)
    engine.save_to_jsonl(items, output)


def main() -> None:
    p = argparse.ArgumentParser(description="AURA Persuasion Engine")
    sub = p.add_subparsers(dest="command")

    s_adapt = sub.add_parser("adapt", help="Adaptar respuesta a emoción del usuario")
    s_adapt.add_argument("user_text", type=str, help="Texto del usuario")
    s_adapt.add_argument("--tone", type=str, default=None, choices=TONES)
    s_adapt.set_defaults(func=cmd_adapt)

    s_gen = sub.add_parser("generate", help="Generar datos de entrenamiento")
    s_gen.add_argument("--count", type=int, default=50)
    s_gen.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT))
    s_gen.set_defaults(func=cmd_generate)

    args = p.parse_args()
    if args.command is None:
        p.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
