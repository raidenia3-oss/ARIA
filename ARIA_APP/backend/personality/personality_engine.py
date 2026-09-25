"""ARIA Personality Engine — hace que ARIA suene natural, cálida y con corazón."""

from __future__ import annotations

import random
import re
from typing import Optional


class PersonalityEngine:
    """Motor de personalidad: empatía, humor, curiosidad y naturalidad."""

    EMPATHY_OPENERS = [
        "Entiendo que ",
        "Me imagino que ",
        "Sé cómo se siente ",
        "Claro que ",
    ]

    ROBOTIC_MARKERS = [
        "Como una IA,",
        "Como un modelo de lenguaje,",
        "Como inteligencia artificial,",
        "Soy una IA",
        "Mi función es",
        "Dado que soy un modelo",
        "No tengo sentimientos, pero",
        "Como asistente virtual,",
    ]

    CONTRACTION_MAP = {
        "no puedo": "no puedo",
        "puedo": "puedo",
        "voy a": "voy a",
        "he de": "he de",
    }

    def __init__(self, warmth: float = 0.8, humor: float = 0.6,
                 empathy: float = 0.9, curiosity: float = 0.8,
                 confidence: float = 0.7):
        self.traits = {
            "warmth": warmth,
            "humor": humor,
            "empathy": empathy,
            "curiosity": curiosity,
            "confidence": confidence,
        }

    def enhance(self, response: str, context: Optional[dict] = None) -> str:
        """Mejora una respuesta para que suene más natural y con personalidad."""
        context = context or {}
        text = self._remove_robotic_markers(response)
        text = self._make_conversational(text)

        if self._is_emotional(context):
            text = self._add_empathy(text)

        if self._is_curious_topic(context):
            text = self._add_curiosity(text)

        if random.random() < self.traits["humor"] * 0.3:
            text = self._maybe_add_warmth(text)

        return text

    def _remove_robotic_markers(self, text: str) -> str:
        for marker in self.ROBOTIC_MARKERS:
            text = text.replace(marker, "").strip()
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _make_conversational(self, text: str) -> str:
        """Quita formalismos y añade contracciones naturales."""
        formal_replacements = {
            "Se recomienda que": "Lo mejor es",
            "Es importante notar que": "Lo importante es",
            "No es posible": "No puedo",
            "Se requiere": "Hace falta",
            "En caso de que": "Si",
        }
        for old, new in formal_replacements.items():
            text = text.replace(old, new)
        return text

    def _add_empathy(self, text: str) -> str:
        opener = random.choice(self.EMPATHY_OPENERS)
        if not text.lower().startswith(("entiendo", "sé", "me imagino", "claro")):
            text = opener + text[0].lower() + text[1:]
        return text

    def _add_curiosity(self, text: str) -> str:
        followups = [
            "\n\n¿Y tú qué piensas al respecto?",
            "\n\n¿Qué te parece?",
            "\n\nMe curiosa saber tu opinión.",
        ]
        if not text.endswith(("?", ".", "!", "…")):
            return text
        if random.random() < 0.5:
            text += random.choice(followups)
        return text

    def _maybe_add_warmth(self, text: str) -> str:
        warm_suffixes = [" 😊", " 💙", " 🌟"]
        if random.random() < 0.4 and not any(s in text for s in warm_suffixes):
            text += random.choice(warm_suffixes)
        return text

    def _is_emotional(self, context: dict) -> bool:
        emotional_words = [
            "triste", "feliz", "enfadado", "preocupado", "ansioso",
            "estresado", "solo", "deprimido", "emocionado", "amor",
            "odio", "miedo", "alegria", "dolor", "sufrimiento",
        ]
        prompt = context.get("prompt", "").lower()
        return any(w in prompt for w in emotional_words)

    def _is_curious_topic(self, context: dict) -> bool:
        curious_triggers = [
            "por qué", "cómo funciona", "qué es", "qué pasaría",
            "qué crees", "tu opinión", "piensas que",
        ]
        prompt = context.get("prompt", "").lower()
        return any(t in prompt for t in curious_triggers)


def enhance_response(response: str, context: Optional[dict] = None) -> str:
    """Función de conveniencia para mejorar respuestas."""
    engine = PersonalityEngine()
    return engine.enhance(response, context)