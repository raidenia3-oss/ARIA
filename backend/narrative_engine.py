"""Narrative Engine - Sistema de generación de historias coherentes."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional

from backend.models import Story, StoryScene

logger = logging.getLogger("AURA.Narrative")


class StoryTone(Enum):
    DARK = "dark"
    WHIMSICAL = "whimsical"
    DRAMATIC = "dramatic"
    NOIR = "noir"
    ROMANTIC = "romantic"


class NarrativeMemory:
    """Memoria narrativa que persiste en DB."""

    def __init__(self, db_session_factory):
        self.db_session_factory = db_session_factory
        self.story_id: Optional[int] = None
        self.characters: Dict[str, Dict[str, Any]] = {}
        self.plot_points: List[str] = []
        self.tone: Optional[StoryTone] = None
        self.setting: str = ""
        self.world_rules: List[str] = []
        self.previous_scenes: List[Dict[str, Any]] = []

    def load_story(self, story_id: int) -> NarrativeMemory:
        db = self.db_session_factory()
        try:
            story = db.query(Story).filter_by(id=story_id).first()
            if not story:
                return self
            self.story_id = story.id
            self.characters = json.loads(story.characters or "{}")
            self.plot_points = []
            self.tone = StoryTone(story.tone) if story.tone else None
            self.setting = story.premise or ""
            self.world_rules = json.loads(story.world_rules or "[]")
            scenes = db.query(StoryScene).filter_by(story_id=story_id).order_by(StoryScene.timestamp.asc()).all()
            self.previous_scenes = [
                {
                    "text": s.text,
                    "characters": json.loads(s.characters_present or "[]"),
                    "timestamp": datetime.utcfromtimestamp(s.timestamp).isoformat() + "Z",
                }
                for s in scenes
            ]
        finally:
            db.close()
        return self

    def add_scene(self, scene_text: str, characters_present: List[str]) -> None:
        self.previous_scenes.append(
            {
                "text": scene_text,
                "characters": characters_present,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
        )
        db = self.db_session_factory()
        try:
            db.add(
                StoryScene(
                    story_id=self.story_id,
                    text=scene_text,
                    characters_present=json.dumps(characters_present, ensure_ascii=False),
                    timestamp=datetime.utcnow().timestamp(),
                )
            )
            db.commit()
        except Exception as exc:
            logger.error("No se pudo guardar escena: %s", exc)
            db.rollback()
        finally:
            db.close()

    def get_narrative_context(self) -> str:
        context = f"Tono: {self.tone.value if self.tone else 'dramatic'}\n"
        context += f"Escenario: {self.setting}\n\n"
        context += "Personajes:\n" + json.dumps(self.characters, indent=2, ensure_ascii=False) + "\n\n"
        context += "Puntos de trama:\n" + json.dumps(self.plot_points, indent=2, ensure_ascii=False) + "\n\n"
        context += "Reglas del mundo:\n" + json.dumps(self.world_rules, indent=2, ensure_ascii=False) + "\n\n"
        context += "Últimas escenas:\n"
        for scene in self.previous_scenes[-3:]:
            context += f"- {scene['text'][:500]}\n"
        return context


class ClichéDetector:
    CLICHES = {
        r"coraz[oó]n.*lat[ií]a.*r[aá]pido": "ritmo cardíaco acelerado",
        r"tiempo.*se.*detuvo": "tiempo detenido",
        r"aliento.*entrecortado": "respiración entrecortada",
        r"piel.*eriz[oó]": "piel erizada",
        r"mirada.*ardiente": "mirada ardiente",
        r"sinti[oó].*dolor.*atraves[oó]": "dolor atravesando",
        r"l[aá]grimas.*rodaron": "lágrimas rodando",
        r"coraz[oó]n.*roto": "corazón roto",
        r"amor.*a primera vista": "amor a primera vista",
        r"corri[oó].*brazos abiertos": "carrera con brazos abiertos",
        r"beso.*apasionado": "beso apasionado",
    }

    @staticmethod
    def score_cliche(text: str) -> tuple[float, List[str]]:
        found = []
        for pattern, label in ClichéDetector.CLICHES.items():
            if re.search(pattern, text, re.IGNORECASE):
                found.append(label)
        score = min(1.0, len(found) / 4.0)
        return score, found

    @staticmethod
    def suggest_alternatives(cliche: str) -> List[str]:
        return {
            "ritmo cardíaco acelerado": ["Notó cómo subía la adrenalina", "Su pulso se escapó"],
            "tiempo detenido": ["El mundo se redujo a ese instante", "Todo lo demás dejó de importar"],
            "beso apasionado": ["Se besaron sin filtro", "Un beso que no necesitaba explicación"],
        }.get(cliche, ["Busca una descripción más específica y menos gastada"])


class ConsistencyChecker:
    def __init__(self, memory: NarrativeMemory):
        self.memory = memory

    def check_character_consistency(self, character: str, action: str) -> tuple[bool, str]:
        if character not in self.memory.characters:
            return True, "personaje no registrado"
        traits = self.memory.characters[character].get("traits", [])
        contradictions = {
            "evil": ["salvó", "protegió", "ayudó"],
            "kind": ["mató", "lastimó", "abandonó"],
            "coward": ["enfrentó", "desafió", "atacó"],
        }
        for trait in traits:
            if trait in contradictions:
                if any(token in action.lower() for token in contradictions[trait]):
                    return False, f"{character} es {trait}, pero la acción suena contradictoria"
        return True, "consistente"

    def check_plot_consistency(self, new_event: str) -> tuple[bool, str]:
        recent = " ".join(self.memory.plot_points[-5:]).lower()
        contradictions = [
            ("murió", "sobrevivió"),
            ("sobrevivió", "murió"),
            ("regresó", "desapareció"),
        ]
        for a, b in contradictions:
            if a in new_event.lower() and b in recent:
                return False, f"Evento contradice: {b}"
        return True, "consistente"


class ToneAnalyzer:
    TONE_PROMPTS = {
        StoryTone.DARK: (
            "Tono oscuro. "
            "Sangre es sangre, el dolor es brutal, no romantices el sufrimiento. "
            "Usa detalles crudos y realistas."
        ),
        StoryTone.WHIMSICAL: (
            "Tono juguetón. "
            "Lo absurdo es normal. El humor fluye natural. "
            "No fuerces solemnidad."
        ),
        StoryTone.DRAMATIC: (
            "Tono dramático. "
            "Emoción peso completo, pero sin exageración barata. "
            "Deja espacio a silencios."
        ),
        StoryTone.NOIR: (
            "Tono noir. "
            "Ambigüedad, paranoia, nadie es completamente bueno. "
            "Las respuestas nunca son simples."
        ),
        StoryTone.ROMANTIC: (
            "Tono romántico. "
            "Intimidad en detalles pequeños, vulnerabilidad, sin lujuria explícita."
        ),
    }

    @classmethod
    def get_tone_system_prompt(cls, tone: Optional[StoryTone]) -> str:
        if not tone:
            return ""
        return cls.TONE_PROMPTS.get(tone, "")


class NarrativeEngine:
    def __init__(self, db_session_factory, llm_query, llm_stream):
        self.db_session_factory = db_session_factory
        self.llm_query = llm_query
        self.llm_stream = llm_stream
        self.memory: Optional[NarrativeMemory] = None

    async def start_story(
        self,
        title: str,
        premise: str,
        characters: Dict[str, Any],
        tone: StoryTone = StoryTone.DRAMATIC,
    ) -> int:
        db = self.db_session_factory()
        try:
            story = Story(
                title=title,
                premise=premise,
                tone=tone.value,
                characters=json.dumps(characters, ensure_ascii=False),
                world_rules=json.dumps([], ensure_ascii=False),
                created_at=datetime.utcnow().timestamp(),
                updated_at=datetime.utcnow().timestamp(),
            )
            db.add(story)
            db.commit()
            db.refresh(story)
            story_id = story.id
        finally:
            db.close()
        self.memory = NarrativeMemory(self.db_session_factory)
        self.memory.story_id = story_id
        self.memory.characters = characters
        self.memory.tone = tone
        self.memory.setting = premise
        return story_id

    async def continue_story(self, story_id: int, prompt: str) -> AsyncGenerator[str, None]:
        self.memory = NarrativeMemory(self.db_session_factory).load_story(story_id)
        checker = ConsistencyChecker(self.memory)
        tone_prompt = ToneAnalyzer.get_tone_system_prompt(self.memory.tone)
        cliche_score, cliches = ClichéDetector.score_cliche(prompt)
        system_prompt = (
            "Eres un narrador de historias coherente y auténtico.\n"
            f"{tone_prompt}\n\n"
            "MEMORIA NARRATIVA:\n"
            f"{self.memory.get_narrative_context()}\n\n"
            "REGLAS:\n"
            "- No repitas escenas previas.\n"
            "- Evita clichés literarios evidentes.\n"
            "- Mantén la voz de cada personaje.\n"
            "- Haz avanzar la trama.\n"
            "- Escribe como humano, no como IA genérica.\n"
        )
        buffer = ""
        async for chunk in self.llm_stream(prompt=prompt, system=system_prompt, max_tokens=1200):
            buffer += chunk
            yield chunk
            if len(buffer) > 120:
                score, found = ClichéDetector.score_cliche(buffer)
                if score > 0.6:
                    yield "\n[⚠️ Alerta: posible cliché detectado: %s]\n" % ", ".join(found)
                buffer = ""
        self.memory.add_scene(buffer, self._extract_characters(buffer))

    async def regenerate_section(self, story_id: int, section: str) -> str:
        self.memory = NarrativeMemory(self.db_session_factory).load_story(story_id)
        score, cliches = ClichéDetector.score_cliche(section)
        if score < 0.3:
            return "Esta sección no parece muy cliché. ¿Seguro que querés regenerarla?"
        alternatives = []
        for c in cliches:
            alternatives.extend(ClichéDetector.suggest_alternatives(c))
        prompt = (
            "Reescribe la siguiente sección siendo menos cliché.\n\n"
            f"SECCIÓN ORIGINAL:\n{section}\n\n"
            f"CLICHÉS DETECTADOS: {', '.join(cliches)}\n"
            f"ALTERNATIVAS: {', '.join(alternatives)}\n\n"
            "Mantén el significado, cambia solo el tratamiento."
        )
        return await self.llm_query(prompt=prompt)

    def get_story_stats(self, story_id: int) -> Dict[str, Any]:
        db = self.db_session_factory()
        try:
            story = db.query(Story).filter_by(id=story_id).first()
            if not story:
                return {}
            scenes = db.query(StoryScene).filter_by(story_id=story_id).all()
            total_words = sum(len(s.text.split()) for s in scenes)
            return {
                "title": story.title,
                "scenes": len(scenes),
                "total_words": total_words,
                "characters": list(json.loads(story.characters or "{}").keys()),
                "tone": story.tone,
                "created": story.created_at,
            }
        finally:
            db.close()

    def _extract_characters(self, text: str) -> List[str]:
        if not self.memory:
            return []
        return [name for name in self.memory.characters if name.lower() in text.lower()]

