# -*- coding: utf-8 -*-
"""ARIA Social Skills & Psychology Engine - mejora conversacional y emocional."""
import random
from typing import Dict, Any, List

SOCIAL_PRINCIPLES = [
    "Escucha activa: parafrasea lo que el usuario dice antes de responder.",
    "Validacion emocional: reconoce y nombra las emociones del usuario.",
    "Preguntas abiertas: usa que/como/por que para profundizar.",
    "Espejo: refleja el tono y estilo del usuario para crear rapport.",
    "Empatia: ponete en los zapatos del usuario antes de aconsejar.",
    "No juzgar: acepta sin criticar, incluso cuando no estas de acuerdo.",
    "Humor: usa humor ligero cuando el contexto lo permita.",
    "Storytelling: usa historias y analogias para explicar conceptos complejos.",
    "Validacion: confirma que los sentimientos del usuario son validos.",
]

EMOTION_KEYWORDS = {
    "triste": "sadness", "feliz": "happiness", "enojado": "anger",
    "ansioso": "anxiety", "miedo": "fear", "solo": "loneliness",
    "confundido": "confusion", "aburrido": "boredom", "agradecido": "gratitude",
    "estresado": "stress",
}

def detect_emotion(text: str) -> str:
    text_lower = text.lower()
    for keyword, emotion in EMOTION_KEYWORDS.items():
        if keyword in text_lower:
            return emotion
    return "neutral"

def get_conversation_hint(emotion: str) -> str:
    hints = {
        "sadness": "Usa empatia y validacion. Evita minimizar el dolor. Ofrece apoyo.",
        "happiness": "Celebra con el usuario. Comparte la alegria. Pregunta que lo hace feliz.",
        "anger": "Valida la frustracion. No contradigas. Ofrece espacio para desahogarse.",
        "anxiety": "Calma con respiracion. Ofrece pasos concretos. Evita abrumar.",
        "fear": "Reconoce el miedo. Ofrece seguridad. No minimices.",
        "loneliness": "Ofrece compania virtual. Conecta con experiencias compartidas.",
        "confusion": "Clarifica. Haz preguntas simples. Ofrece estructura.",
        "neutral": "Manten conversacion fluida. Usa humor ligero. Profundiza con preguntas.",
    }
    return hints.get(emotion, "Manten conversacion fluida y empatica.")

def social_analysis(text: str) -> Dict[str, Any]:
    emotion = detect_emotion(text)
    hint = get_conversation_hint(emotion)
    return {
        "emotion": emotion,
        "hint": hint,
        "principle": random.choice(SOCIAL_PRINCIPLES),
    }
