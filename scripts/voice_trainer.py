#!/usr/bin/env python3
"""
AURA Voice Trainer — Entrenamiento de voz para asistente virtual tipo JARVIS.

Genera datos de entrenamiento para:
  - Wake-word detection: "AURA", "JARVIS", "Hey AURA"
  - STT (Speech-to-Text): transcripciones con variaciones de acento y ruido
  - TTS (Text-to-Speech): frases con entonación, pausas, énfasis
  - Comandos por voz: intenciones, entidades, acciones
  - Audio event detection: sonidos del entorno (puerta, alarma, timbre)

Dataset generado: training-data-voice.jsonl
Formato: {"text": "transcripción", "output": "intención + acción", "metadata": {...}}

Uso:
  python scripts/voice_trainer.py --count 200 --wake-word AURA
  python scripts/voice_trainer.py --commands --count 100
  python scripts/voice_trainer.py --events --count 50
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
logger = logging.getLogger("VoiceTrainer")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "training-data-voice.jsonl"

WAKE_WORDS = ["AURA", "JARVIS", "Hey AURA", "Hey JARVIS", "OK AURA", "Computer"]

ACCENT_VARIATIONS = [
    "Español neutro", "Español latino", "Español España", "Inglés US", "Inglés UK",
    "Portugués BR", "Francés", "Alemán", "Italiano", "Japonés", "Chino mandarín"
]

NOISE_CONTEXTS = [
    "silencio", "ruido de fondo bajo", "ruido de tráfico", "música suave",
    "conversación de fondo", "teclado mecánico", "ventilador", "lluvia"
]

VOICE_COMMANDS: List[Dict] = [
    {
        "template": "AURA, {action} las luces de la {room} al {level}%",
        "intent": "smart_home.control",
        "action_template": "Ejecutar: smart_home.set_lights(room='{room}', brightness={level})",
        "variables": {
            "action": ["enciende", "apaga", "ajusta", "configura"],
            "room": ["sala", "habitación", "cocina", "baño", "oficina", "estudio"],
            "level": [0, 25, 50, 75, 100],
        },
    },
    {
        "template": "AURA, {action} la {device} de la {room}",
        "intent": "smart_home.control",
        "action_template": "Ejecutar: smart_home.toggle(device='{device}', room='{room}')",
        "variables": {
            "action": ["enciende", "apaga", "reinicia"],
            "device": ["luz", "ventilador", "aire acondicionado", "calefacción", "TV", "router"],
            "room": ["sala", "habitación", "cocina", "baño", "oficina"],
        },
    },
    {
        "template": "AURA, pon una alarma para las {hour}:{minute} {period}",
        "intent": "alarm.set",
        "action_template": "Ejecutar: alarm.set(hour={hour}, minute={minute}, period='{period}')",
        "variables": {
            "hour": [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23],
            "minute": [0, 15, 30, 45],
            "period": ["AM", "PM"],
        },
    },
    {
        "template": "AURA, recuérdame {task} en {time}",
        "intent": "reminder.create",
        "action_template": "Ejecutar: reminder.create(task='{task}', time='{time}')",
        "variables": {
            "task": ["llamar al médico", "revisar el correo", "enviar el informe", "tomar la medicina", "asistir a la reunión"],
            "time": ["30 minutos", "1 hora", "2 horas", "mañana", "el viernes"],
        },
    },
    {
        "template": "AURA, busca en internet sobre {query}",
        "intent": "web.search",
        "action_template": "Ejecutar: web.search(query='{query}')",
        "variables": {
            "query": ["cómo funciona el motor Tesla", "clima hoy", "últimas noticias de tecnología", "precio del dólar", "recetas de pasta"],
        },
    },
    {
        "template": "AURA, envía un mensaje a {contact} diciendo {message}",
        "intent": "messaging.send",
        "action_template": "Ejecutar: messaging.send(contact='{contact}', message='{message}')",
        "variables": {
            "contact": ["Mamá", "Jefe", "Equipo", "María", "Carlos"],
            "message": ["llego tarde", "revisa el documento", "feliz cumpleaños", "nos vemos en 10"],
        },
    },
    {
        "template": "AURA, reproduce {song} de {artist}",
        "intent": "media.play",
        "action_template": "Ejecutar: media.play(song='{song}', artist='{artist}')",
        "variables": {
            "song": ["Bohemian Rhapsody", "Imagine", "Hotel California", "Shape of You", "Despacito"],
            "artist": ["Queen", "John Lennon", "Eagles", "Ed Sheeran", "Luis Fonsi"],
        },
    },
    {
        "template": "AURA, cuéntame un chiste",
        "intent": "conversation.joke",
        "action_template": "Respuesta: Contar un chiste corto y apropiado",
        "variables": {},
    },
    {
        "template": "AURA, {action} el volumen al {level}%",
        "intent": "system.volume",
        "action_template": "Ejecutar: system.set_volume(level={level})",
        "variables": {
            "action": ["sube", "baja", "ajusta", "silencia", "quita silencio"],
            "level": [0, 25, 50, 75, 100],
        },
    },
    {
        "template": "AURA, {action} el {mode}",
        "intent": "system.mode",
        "action_template": "Ejecutar: system.set_mode(mode='{mode}')",
        "variables": {
            "action": ["activa", "desactiva", "cambia a"],
            "mode": ["modo avión", "modo no molestar", "modo trabajo", "modo cine", "modo noche"],
        },
    },
]

AUDIO_EVENTS: List[Dict] = [
    {"event": "timbre", "action": "Responder: Timbre detectado. ¿Abrir puerta?"},
    {"event": "alarma de humo", "action": "Responder: Alarma de humo detectada. Verificar seguridad inmediatamente."},
    {"event": "vidrio roto", "action": "Responder: Sonido de vidrio roto. Verificar cámaras de seguridad."},
    {"event": "puerta abriéndose", "action": "Responder: Puerta abierta. ¿Quién llegó?"},
    {"event": "llanto de bebé", "action": "Responder: Llanto de bebé detectado. Verificar cámara de la habitación."},
    {"event": "golpe fuerte", "action": "Responder: Golpe fuerte detectado. Verificar estado de personas."},
    {"event": "sirena de ambulancia", "action": "Responder: Sirena cercana. ¿Necesitas ayuda?"},
    {"event": "notificación de mensaje", "action": "Responder: Notificación recibida. ¿Leer en voz alta?"},
]


class VoiceTrainer:
    """Genera datos de entrenamiento para voz y audio."""

    def __init__(self, seed: int = 42):
        random.seed(seed)
        self.generated_keys: set = set()

    def _key(self, category: str, idx: int) -> str:
        return f"{category}:{idx}"

    def _fill(self, template: str, variables: Dict) -> str:
        result = template
        for var, values in variables.items():
            if isinstance(values, list) and values:
                val = random.choice(values)
                if isinstance(val, int):
                    val = str(val)
                result = result.replace("{" + var + "}", val)
        return result

    def generate_wake_word(self, word: str = "AURA") -> Dict:
        noise = random.choice(NOISE_CONTEXTS)
        accent = random.choice(ACCENT_VARIATIONS)
        templates = [
            f"[{noise}] [{accent}] {word}",
            f"{word}...",
            f"oye {word}",
            f"hey {word}",
            f"{word}, por favor",
            f"disculpa {word}",
            f"{word}!!!",
        ]
        text = random.choice(templates)
        key = self._key("wake", hash(text) % 100000)
        if key in self.generated_keys:
            return self.generate_wake_word(word)
        self.generated_keys.add(key)

        return {
            "text": text,
            "output": f"Intent: wake_word_detected\nAction: activate_aura\nConfidence: high\nWake word: {word}",
            "metadata": {
                "source": "voice_trainer",
                "category": "wake_word",
                "noise": noise,
                "accent": accent,
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            },
        }

    def generate_command(self) -> Dict:
        cmd = random.choice(VOICE_COMMANDS)
        text = self._fill(cmd["template"], cmd.get("variables", {}))
        intent = cmd["intent"]
        action = self._fill(cmd["action_template"], cmd.get("variables", {}))
        key = self._key("command", hash(text) % 100000)
        if key in self.generated_keys:
            return self.generate_command()
        self.generated_keys.add(key)

        return {
            "text": text,
            "output": f"Intent: {intent}\nAction: {action}",
            "metadata": {
                "source": "voice_trainer",
                "category": "command",
                "intent": intent,
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            },
        }

    def generate_event(self) -> Dict:
        evt = random.choice(AUDIO_EVENTS)
        key = self._key("event", hash(evt["event"]) % 100000)
        if key in self.generated_keys:
            return self.generate_event()
        self.generated_keys.add(key)

        return {
            "text": f"[Audio event: {evt['event']}]",
            "output": evt["action"],
            "metadata": {
                "source": "voice_trainer",
                "category": "audio_event",
                "event": evt["event"],
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            },
        }

    def generate_batch(self, count: int = 50, category: str = "commands") -> List[Dict]:
        results = []
        for _ in range(count):
            try:
                if category == "wake_words":
                    results.append(self.generate_wake_word())
                elif category == "events":
                    results.append(self.generate_event())
                else:
                    results.append(self.generate_command())
            except Exception as exc:
                logger.debug(f"Skip voice sample: {exc}")
        return results

    def save_to_jsonl(self, items: List[Dict], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        logger.info(f"Saved {len(items)} voice samples -> {output_path}")


def cmd_generate(args: argparse.Namespace) -> None:
    trainer = VoiceTrainer()
    items = trainer.generate_batch(count=args.count, category=args.category)
    output = Path(args.output)
    trainer.save_to_jsonl(items, output)


def main() -> None:
    p = argparse.ArgumentParser(description="AURA Voice Trainer")
    p.add_argument("--count", type=int, default=50)
    p.add_argument("--category", type=str, default="commands", choices=["commands", "wake_words", "events"])
    p.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT))
    args = p.parse_args()
    cmd_generate(args)


if __name__ == "__main__":
    main()
