#!/usr/bin/env python3
"""
AURA Emotional Memory — Memoria y perfil emocional del usuario.

Capacidades:
  - Detección de emociones en texto (feliz, frustrado, curioso, ansioso, triste, enojado)
  - Historial emocional con timestamps y tendencias
  - Ajuste automático de tono según estado emocional
  - Registro de triggers emocionales (palabras/frases que disparan emociones)
  - Perfil emocional del usuario (estado base, variabilidad, momentos clave)
  - Predicción de estado emocional futuro basado en historial
  - Recomendaciones de comunicación según estado emocional

Dataset: training-data-emotional.jsonl

Uso:
  python scripts/emotional_memory.py --user-id user1 --text "Estoy muy feliz hoy" --record
  python scripts/emotional_memory.py --user-id user1 --text "No entiendo nada" --record
  python scripts/emotional_memory.py --user-id user1 --profile
  python scripts/emotional_memory.py --generate --count 50
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import random
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EmotionalMemory")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "training-data-emotional.jsonl"
MEMORY_DIR = REPO_ROOT / "emotional_memory"

EMOTION_KEYWORDS: Dict[str, List[str]] = {
    "joy": ["feliz", "contento", "alegre", "genial", "increíble", "maravilloso", "perfecto", "genial", "bien", "excelente", "gracias", "amo", "encanta", "divertido", "sonrisa"],
    "frustration": ["frustrado", "no entiendo", "no funciona", "error", "difícil", "complicado", "no puedo", "imposible", "harto", "cansado", "molesto"],
    "anxiety": ["preocupado", "miedo", "urgente", "rápido", "pronto", "emergencia", "pánico", "desesperado", "estrés", "nervioso", "ansiedad"],
    "curiosity": ["interesante", "cómo", "por qué", "explica", "dime", "qué es", "cómo funciona", "curioso", "aprender", "saber"],
    "sadness": ["triste", "mal", "desanimado", "perdí", "fallé", "no sirve", "solo", "vacío", "deprimido", "llanto"],
    "anger": ["enojado", "molesto", "inaceptable", "terrible", "basura", "odio", "furioso", "rabia", "injusto"],
    "neutral": ["hola", "ayuda", "info", "dato", "consulta", "pregunta", "quiero", "necesito", "busco"],
}

EMOTION_RESPONSES: Dict[str, str] = {
    "joy": "Celebra el momento, refuerza la confianza y sugiere nuevos logros.",
    "frustration": "Valida el sentimiento, ofrece apoyo paso a paso y normaliza el error.",
    "anxiety": "Calma, prioriza acciones y ofrece un plan concreto.",
    "curiosity": "Alimenta la curiosidad con datos fascinantes, ejemplos y retos.",
    "sadness": "Acompaña sin juicios, ofrece consuelo y pequeñas acciones reconfortantes.",
    "anger": "Escucha sin confrontar, valida la emoción y redirige a soluciones.",
    "neutral": "Mantiene claridad, estructura y proactividad.",
}

PERSONALITY_TRAITS = {
    "empático": ["entiendo", "siento", "juntos", "acompaño", "respeto"],
    "técnico": ["exacto", "preciso", "paso", "configuración", "protocolo"],
    " motivador": ["vamos", "puedes", "logro", "meta", "avanza"],
    "analítico": ["según", "datos", "estadística", "patrón", "tendencia"],
    "creativo": ["imagina", "posibilidad", "alternativa", "visualiza", "sorprendente"],
}


class EmotionalMemory:
    """Gestión de memoria emocional del usuario."""

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self.memory_dir = MEMORY_DIR / user_id
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.memory_dir / "emotional_history.jsonl"
        self.profile_file = self.memory_dir / "emotional_profile.json"
        self.history: deque = deque(maxlen=1000)
        self.profile: Dict[str, Any] = self._load_profile()
        self._load_history()

    def _load_profile(self) -> Dict[str, Any]:
        if self.profile_file.exists():
            try:
                with open(self.profile_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "user_id": self.user_id,
            "base_emotion": "neutral",
            "emotional_variability": 0.0,
            "triggers": {},
            "last_updated": datetime.now().isoformat(),
            "total_records": 0,
        }

    def _save_profile(self) -> None:
        self.profile["last_updated"] = datetime.now().isoformat()
        with open(self.profile_file, "w", encoding="utf-8") as f:
            json.dump(self.profile, f, indent=2, ensure_ascii=False)

    def _load_history(self) -> None:
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                self.history.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
            except Exception:
                pass

    def _save_history_entry(self, entry: Dict) -> None:
        mode = "a" if self.history_file.exists() else "w"
        with open(self.history_file, mode, encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def detect_emotion(self, text: str) -> Tuple[str, float]:
        text_lower = text.lower()
        scores = {}
        for emotion, keywords in EMOTION_KEYWORDS.items():
            scores[emotion] = sum(1 for kw in keywords if kw in text_lower)
        if not scores or max(scores.values()) == 0:
            return "neutral", 0.5
        best = max(scores, key=scores.get)
        confidence = min(1.0, scores[best] / max(3, len(text.split()) * 0.1))
        return best, round(confidence, 2)

    def record(self, text: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        emotion, confidence = self.detect_emotion(text)
        entry = {
            "user_id": self.user_id,
            "text": text,
            "emotion": emotion,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
        }
        self.history.append(entry)
        self._save_history_entry(entry)
        self.profile["total_records"] += 1
        self._update_triggers(text, emotion)
        self._update_base_emotion(emotion)
        self._save_profile()
        logger.info(f"Recorded emotion: {emotion} ({confidence}) for user {self.user_id}")
        return entry

    def _update_triggers(self, text: str, emotion: str) -> None:
        words = text.lower().split()
        for word in words:
            if len(word) > 3:
                triggers = self.profile.setdefault("triggers", {})
                if word not in triggers:
                    triggers[word] = {"count": 0, "emotions": defaultdict(int)}
                triggers[word]["count"] += 1
                triggers[word]["emotions"][emotion] += 1

    def _update_base_emotion(self, new_emotion: str) -> None:
        recent = list(self.history)[-20:]
        if not recent:
            return
        counts = defaultdict(int)
        for entry in recent:
            counts[entry["emotion"]] += 1
        self.profile["base_emotion"] = max(counts, key=counts.get)
        total = sum(counts.values())
        max_c = max(counts.values())
        self.profile["emotional_variability"] = round(1.0 - (max_c / total), 2) if total else 0.0

    def get_profile(self) -> Dict[str, Any]:
        return self.profile

    def get_recent(self, limit: int = 20) -> List[Dict]:
        return list(self.history)[-limit:]

    def get_trend(self, hours: int = 24) -> Dict[str, Any]:
        cutoff = datetime.now().timestamp() - (hours * 3600)
        recent = [e for e in self.history if datetime.fromisoformat(e["timestamp"]).timestamp() > cutoff]
        counts = defaultdict(int)
        for entry in recent:
            counts[entry["emotion"]] += 1
        return {
            "window_hours": hours,
            "entries": len(recent),
            "distribution": dict(counts),
            "dominant": max(counts, key=counts.get) if counts else "neutral",
        }

    def recommend_communication(self) -> Dict[str, Any]:
        base = self.profile.get("base_emotion", "neutral")
        trend = self.get_trend(hours=1)
        dominant = trend.get("dominant", "neutral")
        if dominant != "neutral":
            emotion = dominant
        else:
            emotion = base
        return {
            "recommended_tone": emotion,
            "strategy": EMOTION_RESPONSES.get(emotion, "Mantener claridad y estructura."),
            "avoid": self._avoid_for_emotion(emotion),
            "use": self._use_for_emotion(emotion),
        }

    def _avoid_for_emotion(self, emotion: str) -> List[str]:
        return {
            "frustration": ["jerga innecesaria", "pasos complejos", "respuestas frías"],
            "anxiety": ["demasiada información", "lenguaje alarmista", "incertidumbre"],
            "joy": ["respuestas monótonas", "falta de entusiasmo"],
            "sadness": ["frases como 'ya se te pasará'", "minimizar sentimientos"],
            "anger": ["tono defensivo", "contradecir", "respuestas cortantes"],
        }.get(emotion, ["tono ambiguo", "respuestas evasivas"])

    def _use_for_emotion(self, emotion: str) -> List[str]:
        return {
            "frustration": ["validación", "pasos cortos", "ejemplos prácticos"],
            "anxiety": ["claridad", "priorización", "tiempos concretos"],
            "curiosity": ["metáforas", "datos fascinantes", "preguntas retóricas"],
            "joy": ["celebración", "siguientes logros", "lenguaje positivo"],
            "sadness": ["empatía", "presencia", "opciones sin presión"],
            "anger": ["escucha", "reconocimiento", "soluciones concretas"],
        }.get(emotion, ["claridad", "estructura", "proactividad"])

    def generate_batch(self, count: int = 50) -> List[Dict]:
        results = []
        emotions = list(EMOTION_KEYWORDS.keys())
        for _ in range(count):
            emotion = random.choice(emotions)
            keywords = EMOTION_KEYWORDS[emotion]
            user_text = f"Usuario {emotion}: {random.choice(keywords)}. {random.choice(['ayuda', 'explica', 'soluciona', 'dime'])} {random.choice(['esto', 'cómo', 'por qué', 'qué'])}."
            result = self.record(user_text)
            comm = self.recommend_communication()
            results.append({
                "text": user_text,
                "output": f"Emoción detectada: {result['emotion']} (confianza: {result['confidence']})\nEstrategia: {comm['strategy']}\nTono recomendado: {comm['recommended_tone']}\nUsar: {', '.join(comm['use'])}\nEvitar: {', '.join(comm['avoid'])}",
                "metadata": {
                    "source": "emotional_memory",
                    "emotion": result["emotion"],
                    "confidence": result["confidence"],
                    "recommended_tone": comm["recommended_tone"],
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
        logger.info(f"Saved {len(items)} emotional samples -> {output_path}")


def cmd_record(args: argparse.Namespace) -> None:
    memory = EmotionalMemory(user_id=args.user_id)
    entry = memory.record(args.text)
    print(json.dumps(entry, indent=2, ensure_ascii=False))


def cmd_profile(args: argparse.Namespace) -> None:
    memory = EmotionalMemory(user_id=args.user_id)
    profile = memory.get_profile()
    trend = memory.get_trend(hours=args.hours)
    comm = memory.recommend_communication()
    result = {
        "profile": profile,
        "trend": trend,
        "communication_recommendation": comm,
        "recent": memory.get_recent(limit=args.limit),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_generate(args: argparse.Namespace) -> None:
    memory = EmotionalMemory()
    items = memory.generate_batch(count=args.count)
    output = Path(args.output)
    memory.save_to_jsonl(items, output)


def main() -> None:
    p = argparse.ArgumentParser(description="AURA Emotional Memory")
    sub = p.add_subparsers(dest="command")

    s_rec = sub.add_parser("record", help="Registrar emoción del usuario")
    s_rec.add_argument("--user-id", type=str, default="default")
    s_rec.add_argument("text", type=str, help="Texto del usuario")
    s_rec.set_defaults(func=cmd_record)

    s_prof = sub.add_parser("profile", help="Ver perfil emocional")
    s_prof.add_argument("--user-id", type=str, default="default")
    s_prof.add_argument("--hours", type=int, default=24)
    s_prof.add_argument("--limit", type=int, default=20)
    s_prof.set_defaults(func=cmd_profile)

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
