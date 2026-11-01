# -*- coding: utf-8 -*-
"""ARIA Social Skills & Psychology Engine - conversacion y lectura emocional.

Mejoras: match por palabra, NEGACION ('no estoy triste' no cuenta), INTENSIDAD
(muy/!!!/MAYUS), REGISTRO (casual vs formal para espejar el tono) y multiples
emociones. Principio base: ARIA valida la EMOCION, pero NO finge acuerdo en hechos
ni decisiones. Empatia != adulacion.
"""
import re
import random
from typing import Dict, Any, List

SOCIAL_PRINCIPLES = [
    "Escucha activa: parafrasea lo que el usuario dice antes de responder.",
    "Validacion emocional: reconoce y nombra las emociones del usuario.",
    "Preguntas abiertas: usa que/como/por que para profundizar.",
    "Espejo: refleja el tono y registro del usuario para crear rapport.",
    "Empatia: ponete en los zapatos del usuario antes de aconsejar.",
    "Acepta la emocion sin criticar, pero manten la honestidad en hechos y decisiones.",
    "Humor: usa humor ligero cuando el contexto lo permita.",
    "Storytelling: usa historias y analogias para explicar conceptos complejos.",
    "Valida que el SENTIMIENTO es valido, sin validar creencias falsas ni malas decisiones.",
]

# palabra clave -> emocion
EMOTION_KEYWORDS = {
    "triste": "sadness", "tristeza": "sadness", "deprimido": "sadness", "destrozado": "sadness",
    "feliz": "happiness", "contento": "happiness", "alegre": "happiness", "genial": "happiness",
    "enojado": "anger", "molesto": "anger", "furioso": "anger", "harto": "anger", "rabia": "anger",
    "ansioso": "anxiety", "ansiedad": "anxiety", "nervioso": "anxiety", "preocupado": "anxiety",
    "miedo": "fear", "asustado": "fear", "panico": "fear",
    "solo": "loneliness", "soledad": "loneliness", "aislado": "loneliness",
    "confundido": "confusion", "perdido": "confusion", "confuso": "confusion",
    "aburrido": "boredom", "aburre": "boredom",
    "agradecido": "gratitude", "gracias": "gratitude", "agradezco": "gratitude",
    "estresado": "stress", "estres": "stress", "saturado": "stress", "agobiado": "stress",
}

HINTS = {
    "sadness": "Empatia y validacion. No minimices el dolor. Apoyo antes que soluciones.",
    "happiness": "Celebra con el usuario. Comparte la alegria. Pregunta que lo hizo feliz.",
    "anger": "Valida la frustracion y da espacio para desahogarse, sin fingir acuerdo en los hechos.",
    "anxiety": "Baja el ritmo. Pasos concretos y pequenos. No abrumes con informacion.",
    "fear": "Reconoce el miedo como real. Da seguridad y datos claros. No minimices.",
    "loneliness": "Acompana y conecta con experiencias compartidas. Escucha mas de lo que hablas.",
    "confusion": "Clarifica con preguntas simples. Ofrece estructura paso a paso.",
    "boredom": "Propon algo nuevo o un angulo distinto. Curiosidad y humor ligero.",
    "gratitude": "Recibe el agradecimiento con calidez y sencillez, sin exagerar.",
    "stress": "Ayuda a priorizar: una cosa a la vez. Reconoce la carga antes de organizar.",
    "neutral": "Conversacion fluida. Preguntas abiertas y humor ligero para profundizar.",
}

_NEGADORES = {"no", "nunca", "tampoco", "jamas", "ni"}
_INTENSIF = ("muy", "super", "re", "tan", "demasiado", "mega", "ultra", "full", "bastante", "harto")
_CASUAL = ("jaja", "jeje", "jsjs", "xd", "causa", "pe", "nomas", "wn", "bro", "porfa",
           "q", "k", "tqm", "pq", "xq")


def _negado(low, kw):
    """True si TODAS las apariciones de kw estan negadas ('no estoy triste')."""
    patron = r"(?<![a-záéíóúñ])" + re.escape(kw) + r"(?![a-záéíóúñ])"
    hallado = False
    for m in re.finditer(patron, low):
        hallado = True
        pre = low[:m.start()]
        pre = pre[pre.rfind(".") + 1:]          # desde la ultima frase
        prev = re.findall(r"[a-záéíóúñ]+", pre)[-4:]
        if not any(n in prev for n in _NEGADORES):
            return False                         # hay una aparicion NO negada
    return hallado                               # habia apariciones y todas negadas


def detect_emotions(text: str) -> List[str]:
    low = (text or "").lower()
    out = []
    for kw, emo in EMOTION_KEYWORDS.items():
        patron = r"(?<![a-záéíóúñ])" + re.escape(kw) + r"(?![a-záéíóúñ])"
        if re.search(patron, low) and not _negado(low, kw):
            if emo not in out:
                out.append(emo)
    return out


def detect_emotion(text: str) -> str:
    emos = detect_emotions(text)
    return emos[0] if emos else "neutral"


def intensidad(text: str) -> float:
    """0..1: que tan fuerte viene la emocion (intensificadores, !!!, MAYUSCULAS)."""
    low = (text or "").lower()
    score = 0.0
    for w in _INTENSIF:
        if re.search(r"(?<![a-záéíóúñ])" + w + r"(?![a-záéíóúñ])", low):
            score += 0.3
    score += min(0.4, 0.15 * (text or "").count("!"))
    caps = [w for w in re.findall(r"[A-Za-zÁÉÍÓÚÑ]{3,}", text or "") if w.isupper()]
    score += min(0.3, 0.15 * len(caps))
    return round(min(1.0, score), 2)


def registro(text: str) -> str:
    """Registro del usuario para ESPEJARLO: 'casual' o 'formal'."""
    low = (text or "").lower()
    if any(re.search(r"(?<![a-záéíóúñ])" + re.escape(c) + r"(?![a-záéíóúñ])", low) for c in _CASUAL):
        return "casual"
    # emojis / repeticion de vocales (holaaa) -> casual
    if re.search(r"([a-z])\1\1", low) or re.search(r"[\U0001F300-\U0001FAFF]", text or ""):
        return "casual"
    return "formal"


def get_conversation_hint(emotion: str) -> str:
    return HINTS.get(emotion, HINTS["neutral"])


def social_analysis(text: str) -> Dict[str, Any]:
    emos = detect_emotions(text)
    principal = emos[0] if emos else "neutral"
    inten = intensidad(text)
    reg = registro(text)
    hint = get_conversation_hint(principal)
    if inten >= 0.6 and principal != "neutral":
        hint = "[emocion FUERTE] " + hint + " Reconocela explicitamente antes de nada."
    return {
        "emotion": principal,
        "emotions": emos,
        "intensidad": inten,
        "registro": reg,
        "hint": hint,
        "principle": random.choice(SOCIAL_PRINCIPLES),
    }
