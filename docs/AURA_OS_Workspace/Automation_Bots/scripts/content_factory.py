"""
Content Factory - Pipeline automatizado de creacion de contenidos.
Toma texto, genera narracion audio, anima avatar ASCII y prepara payload para redes.
"""

import os
import json
import time
import random
from datetime import datetime

try:
    from gtts import gTTS
except ImportError:
    gTTS = None

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

VOICE_ENGINE = pyttsx3 or gTTS

AUDIO_OUTPUT = "dist/content_to_upload/audio/"
FRAMES_OUTPUT = "dist/content_to_upload/frames/"
PAYLOAD_OUTPUT = "dist/content_to_upload/payload.json"
SOURCE_GUIDE = "docs/ame_modification_guide.md"


def extract_sections(path: str):
    if not os.path.exists(path):
        return ["Bienvenidos a AURA/AME. En este video les ensenare a modificar su app sin root."]
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")][:20]


def generate_audio(text: str, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if pyttsx3:
        engine = pyttsx3.init()
        engine.save_to_file(text, path)
        engine.runAndWait()
    elif gTTS:
        tts = gTTS(text=text, lang="es")
        tts.save(path)
    else:
        raise RuntimeError("No hay motor TTS instalado. Instala pyttsx3 o gtts.")


def avatar_sequence(text: str) -> list:
    frames = [
        "     ╭──────────────╮\n     │  (◕‿◕✿)     │\n     │  HABLANDO     │\n     │  ▓▓▓▓▓▓░░░░ │\n     ╰──────────────╯",
        "     ╭──────────────╮\n     │  (｡◕‿◕｡)   │\n     │  PROCESANDO  │\n     │  ▓▓▓▓▓▓▓▓░░ │\n     ╰──────────────╯",
        "     ╭──────────────╮\n     │  (ﾉ◕ヮ◕)ﾉ   │\n     │  ENFASIS     │\n     │  ▓▓▓▓▓▓░░░░ │\n     ╰──────────────╯",
    ]
    words = text.split()
    result = []
    for i in range(0, len(words), 5):
        frame = random.choice(frames)
        result.append(frame + "\n     ► " + " ".join(words[i : i + 5]))
    return result


def optimize_seo(title: str, body: str) -> dict:
    keywords = ["AURA", "AME", "Android", "sin root", "IA", "automatizacion", "RollerCoin"]
    tags = ["#AURA", "#AME", "#Android", "#SinRoot", "#IA", "#Tech", "#OpenSource"]
    desc = f"{title} - {body[:120]}..."
    return {
        "title": title,
        "description": desc,
        "keywords": keywords,
        "hashtags": " ".join(tags[:6]),
        "monetization_links": [
            "https://huggingface.co/spaces/raiden456-slut",
            "https://openrouter.ai",
        ],
    }


def build_payload(section: str, index: int):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    audio_name = f"content_{ts}_{index}.mp3"
    audio_path = os.path.join(AUDIO_OUTPUT, audio_name)
    generate_audio(section, audio_path)
    frames = avatar_sequence(section)
    seo = optimize_seo(f"AME Mod {index}", section)
    payload = {
        "id": f"content_{ts}_{index}",
        "section": section[:200],
        "audio_file": audio_path,
        "frames": frames,
        "seo": seo,
        "ready_to_upload": True,
    }
    return payload


def run_factory():
    sections = extract_sections(SOURCE_GUIDE)
    os.makedirs(AUDIO_OUTPUT, exist_ok=True)
    os.makedirs(FRAMES_OUTPUT, exist_ok=True)
    payloads = []
    for i, sec in enumerate(sections[:3]):
        payloads.append(build_payload(sec, i))
    with open(PAYLOAD_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(payloads, f, indent=2, ensure_ascii=False)
    print(f"Factory completada: {len(payloads)} contenidos listos en dist/content_to_upload/")


if __name__ == "__main__":
    run_factory()
