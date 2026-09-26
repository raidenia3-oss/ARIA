"""
AURA Narrative Engine - Coherent Storytelling
Motor de narrativa con memoria de personajes, tramas y coherencia emocional.
"""

from __future__ import annotations

import os
import time
import json
import hashlib
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional
from pathlib import Path


AURA_BACKEND_URL = os.getenv("AURA_BACKEND_URL", "http://localhost:8000")
AURA_API_KEY = os.getenv("AURA_API_KEY", "")
NARRATIVE_DIR = Path(__file__).resolve().parent.parent / "narrative_data"
NARRATIVE_DIR.mkdir(exist_ok=True)


class CharacterMemory:
    def __init__(self, name: str, personality: str = "", background: str = "", voice_pattern: str = "") -> None:
        self.name = name
        self.personality = personality
        self.background = background
        self.relationships: Dict[str, str] = {}
        self.emotional_state: Dict[str, float] = {"joy": 0.5, "anger": 0.0, "fear": 0.0, "sadness": 0.0, "surprise": 0.0}
        self.memories: List[Dict[str, Any]] = []
        self.voice_pattern: str = ""
        self.created_at = time.time()

    def add_memory(self, event: str, emotional_impact: Dict[str, float] = None) -> None:
        memory = {
            "event": event,
            "timestamp": time.time(),
            "emotional_impact": emotional_impact or {},
        }
        self.memories.append(memory)
        if emotional_impact:
            for emotion, value in emotional_impact.items():
                self.emotional_state[emotion] = min(1.0, max(0.0, self.emotional_state.get(emotion, 0.0) + value))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "personality": self.personality,
            "background": self.background,
            "relationships": self.relationships,
            "emotional_state": self.emotional_state,
            "memories": self.memories[-10:],
            "voice_pattern": self.voice_pattern,
        }


class StoryPlot:
    def __init__(self, title: str, genre: str = "") -> None:
        self.title = title
        self.genre = genre
        self.chapters: List[Dict[str, Any]] = []
        self.main_conflict: str = ""
        self.resolution: str = ""
        self.themes: List[str] = []
        self.pacing: str = "moderate"
        self.created_at = time.time()

    def add_chapter(self, title: str, content: str, characters: List[str]) -> None:
        self.chapters.append({
            "title": title,
            "content": content,
            "characters": characters,
            "timestamp": time.time(),
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "genre": self.genre,
            "main_conflict": self.main_conflict,
            "resolution": self.resolution,
            "themes": self.themes,
            "pacing": self.pacing,
            "chapters": self.chapters,
        }


class NarrativeEngine:
    def __init__(self, backend_url: str = AURA_BACKEND_URL, api_key: str = AURA_API_KEY) -> None:
        self.backend_url = backend_url.rstrip("/")
        self.api_key = api_key
        self.headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            self.headers["X-API-Key"] = self.api_key
        self.characters: Dict[str, CharacterMemory] = {}
        self.plots: Dict[str, StoryPlot] = {}
        self.load_state()

    def load_state(self) -> None:
        state_file = NARRATIVE_DIR / "narrative_state.json"
        if state_file.exists():
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for name, char_data in data.get("characters", {}).items():
                    char = CharacterMemory(name=char_data["name"], personality=char_data.get("personality", ""), background=char_data.get("background", ""))
                    char.relationships = char_data.get("relationships", {})
                    char.emotional_state = char_data.get("emotional_state", {})
                    char.memories = char_data.get("memories", [])
                    char.voice_pattern = char_data.get("voice_pattern", "")
                    self.characters[name] = char
                for title, plot_data in data.get("plots", {}).items():
                    plot = StoryPlot(title=plot_data["title"], genre=plot_data.get("genre", ""))
                    plot.main_conflict = plot_data.get("main_conflict", "")
                    plot.resolution = plot_data.get("resolution", "")
                    plot.themes = plot_data.get("themes", [])
                    plot.pacing = plot_data.get("pacing", "moderate")
                    plot.chapters = plot_data.get("chapters", [])
                    self.plots[title] = plot
            except Exception:
                pass

    def save_state(self) -> None:
        state_file = NARRATIVE_DIR / "narrative_state.json"
        try:
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump({
                    "characters": {name: char.to_dict() for name, char in self.characters.items()},
                    "plots": {title: plot.to_dict() for title, plot in self.plots.items()},
                }, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def create_character(self, name: str, personality: str, background: str, voice_pattern: str = "") -> CharacterMemory:
        char = CharacterMemory(name=name, personality=personality, background=background, voice_pattern=voice_pattern)
        self.characters[name] = char
        self.save_state()
        return char

    def create_plot(self, title: str, genre: str, main_conflict: str, themes: List[str] = None) -> StoryPlot:
        plot = StoryPlot(title=title, genre=genre)
        plot.main_conflict = main_conflict
        plot.themes = themes or []
        self.plots[title] = plot
        self.save_state()
        return plot

    def generate_story_prompt(self, plot_title: str, chapter_title: str, pov_character: str, target_length: int = 1000) -> str:
        plot = self.plots.get(plot_title)
        if not plot:
            return ""
        char = self.characters.get(pov_character)
        if not char:
            return ""

        recent_memories = char.memories[-5:]
        memory_context = "; ".join([m["event"] for m in recent_memories])
        emotional_tone = ", ".join([f"{k}: {v:.2f}" for k, v in char.emotional_state.items() if v > 0.1])

        prompt = f"""
Eres un escritor profesional. Escribe el capítulo "{chapter_title}" de la historia "{plot_title}" (género: {plot.genre}).

PERSONAJE (POV): {pov_character}
Personalidad: {char.personality}
Trasfondo: {char.background}
Patrón de voz: {char.voice_pattern}

CONTEXTO EMOCIONAL: {emotional_tone}
MEMORIAS RECIENTES: {memory_context}

CONFLICTO PRINCIPAL: {plot.main_conflict}
TEMAS: {", ".join(plot.themes)}

REQUISITOS:
1. Mantén la voz del personaje consistente con su personalidad y patrón de voz
2. Las reacciones emocionales deben reflejar su estado emocional actual
3. Las acciones deben ser coherentes con su trasfondo y motivaciones
4. Evita clichés y respuestas genéricas
5. Usa lenguaje natural y específico del personaje
6. Longitud: aproximadamente {target_length} palabras
"""
        return prompt

    def call_aura_for_story(self, prompt: str) -> Optional[str]:
        payload = {"prompt": prompt, "session_id": "narrative-engine", "user_id": "system"}
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"{self.backend_url}/api/chat",
            data=data,
            headers=self.headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                result = json.loads(r.read())
                return result.get("text", "")
        except Exception as exc:
            print(f"[Narrative] Error: {exc}")
            return None

    def generate_chapter(self, plot_title: str, chapter_title: str, pov_character: str, target_length: int = 1000) -> Optional[str]:
        prompt = self.generate_story_prompt(plot_title, chapter_title, pov_character, target_length)
        if not prompt:
            return None
        story_text = self.call_aura_for_story(prompt)
        if story_text:
            plot = self.plots.get(plot_title)
            if plot:
                plot.add_chapter(chapter_title, story_text, [pov_character])
            char = self.characters.get(pov_character)
            if char:
                char.add_memory(f"Escribió capítulo '{chapter_title}' de '{plot_title}'", {"joy": 0.2, "surprise": 0.1})
            self.save_state()
        return story_text

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_characters": len(self.characters),
            "total_plots": len(self.plots),
            "total_chapters": sum(len(p.chapters) for p in self.plots.values()),
            "characters": list(self.characters.keys()),
            "plots": list(self.plots.keys()),
        }
