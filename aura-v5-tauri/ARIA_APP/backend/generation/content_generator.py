"""Content Generator — Creative content generation based on ARIA context."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# ============================================================
# Story Generator
# ============================================================


@dataclass
class StoryMetadata:
    title: str
    genre: str
    length: str
    themes: List[str] = field(default_factory=list)
    chapters_count: int = 0


@dataclass
class StoryChapter:
    number: int
    title: str
    content: str


class StoryGenerator:
    """Creates stories in Tensura/anime style."""

    def __init__(self, ai_provider=None) -> None:
        self.ai = ai_provider

    async def generate_story(
        self, prompt: str, length: str = "medium", context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Genera historia tipo Tensura."""
        chapters = {"short": 3, "medium": 5, "long": 10}.get(length, 5)
        title = self._generate_title(prompt)
        chapters_list = []
        for i in range(chapters):
            c_title = f"Capítulo {i+1}: {self._chapter_title(i+1, prompt)}"
            c_content = self._generate_chapter(prompt, i + 1, length, context)
            chapters_list.append(StoryChapter(number=i + 1, title=c_title, content=c_content))
        return {
            "title": title,
            "story": "\n\n".join(f"{c.title}\n{c.content}" for c in chapters_list),
            "metadata": {
                "title": title,
                "genre": "fantasy/anime",
                "length": length,
                "themes": self._extract_themes(prompt),
                "chapters_count": chapters,
            },
        }

    def _generate_title(self, prompt: str) -> str:
        return f"La Leyenda de {self._extract_theme(prompt).title()}"

    def _extract_theme(self, prompt: str) -> str:
        words = prompt.split()
        if len(words) > 3:
            return " ".join(words[:3])
        return prompt if prompt else "Aventura"

    def _extract_themes(self, prompt: str) -> List[str]:
        themes = []
        lower = prompt.lower()
        for t in [
            "magia",
            "aventura",
            "guerra",
            "amistad",
            "traición",
            "poder",
            "misterio",
            "venganza",
        ]:
            if t in lower:
                themes.append(t)
        return themes if themes else ["fantasy"]

    def _chapter_title(self, num: int, prompt: str) -> str:
        titles = [
            "El Despertar",
            "La Primera Prueba",
            "El Encuentro",
            "Sombras Emergen",
            "La Decisión",
            "El Conflicto",
            "El Poder Desatado",
            "El Momento Verdadero",
            "La Batalla Final",
            "El Legado",
        ]
        return titles[(num - 1) % len(titles)]

    def _generate_chapter(
        self, prompt: str, chapter: int, length: str, context: Optional[Dict]
    ) -> str:
        length_words = {"short": 80, "medium": 150, "long": 300}.get(length, 150)
        context_note = ""
        if context:
            app = context.get("current_app", "")
            if app and app != "unknown":
                context_note = f" El protagonista se encuentra en un entorno relacionado con {app}."
        return (
            f"El protagonista avanza hacia su destino.{context_note} "
            f"En el capítulo {chapter}, surge un desafío que pone a prueba su determinación. "
            f"Las fuerzas del mundo parecen conspirar, pero dentro de su corazón arde una llama "
            f"que ninguna oscuridad puede apagar. {self._dramatic_cliffhanger(chapter)}"
        )[:length_words]

    def _dramatic_cliffhanger(self, chapter: int) -> str:
        endings = [
            "Pero algo más grande se acerca.",
            "Una revelación cambia todo lo que creía saber.",
            "El enemigo revela su verdadera forma.",
            "El aliado oculta un secreto oscuro.",
            "El destino le exige una elección imposible.",
        ]
        return endings[(chapter - 1) % len(endings)]

    async def generate_with_character(self, chars: List[str], prompt: str = "") -> Dict[str, Any]:
        """Genera historia con personajes específicos."""
        char_list = ", ".join(chars)
        story = await self.generate_story(
            f"Historia con personajes: {char_list}. {prompt}",
            length="medium",
        )
        story["characters"] = chars
        return story

    async def generate_arc(self, outline: str) -> Dict[str, Any]:
        """Genera historia completa desde outline de 5-7 puntos."""
        points = [p.strip() for p in re.split(r"[.\n]", outline) if p.strip()]
        points = points[:7]
        title = self._generate_title(outline)
        chapters = []
        for i, point in enumerate(points):
            chapters.append(
                StoryChapter(
                    number=i + 1,
                    title=f"Parte {i+1}: {point[:50]}",
                    content=f"El arco se desarrolla: {point}. Los eventos se intensifican mientras el protagonista enfrenta desafíos que pondrán a prueba todo lo que ha aprendido hasta ahora.",
                )
            )
        return {
            "title": title,
            "chapters": [
                {"number": c.number, "title": c.title, "content": c.content} for c in chapters
            ],
            "outline_points": len(points),
        }


# ============================================================
# Character Designer
# ============================================================


class CharacterDesigner:
    """Creates original characters."""

    async def design_character(
        self, role: str = "hero", traits: List[str] = None
    ) -> Dict[str, Any]:
        """Diseña un personaje."""
        traits = traits or ["determined", "strong"]
        name = self._generate_name(role, traits)
        description = self._generate_description(role, traits)
        abilities = self._generate_abilities(role, traits)
        personality = self._generate_personality(traits)
        backstory = self._generate_backstory(name, role, traits)
        return {
            "name": name,
            "description": description,
            "abilities": abilities,
            "personality": personality,
            "backstory": backstory,
            "role": role,
            "traits": traits,
        }

    def _generate_name(self, role: str, traits: List[str]) -> str:
        prefixes = {
            "hero": "Kael",
            "villain": "Seraphine",
            "companion": "Pip",
            "mentor": "Vellius",
            "antihero": "Vex",
        }
        suffixes = ["von Darkmore", "Nightshade", "Stormcaller", "Shadowforge", "Dawnbringer"]
        return f"{prefixes.get(role, 'Aria')} {suffixes[hash(''.join(traits)) % len(suffixes)]}"

    def _generate_description(self, role: str, traits: List[str]) -> str:
        desc_map = {
            "hero": "Guerrero con propósito inquebrantable y ojos que reflejan experiencia más allá de su edad.",
            "villain": "Belleza inquietante con sonrisa que revela peligros ocultos.",
            "companion": "Pequeño y aparentemente inocente, guarda secretos profundos.",
            "mentor": "Sabio cuya vejez oculta una juventud olvidada.",
            "antihero": "Figura ambigua donde el bien y el mal se confunden.",
        }
        return f"{desc_map.get(role, 'Personaje misterioso')} Rasgos: {', '.join(traits)}."

    def _generate_abilities(self, role: str, traits: List[str]) -> List[str]:
        ability_map = {
            "hero": ["mana shield", "power surge", "healing aura"],
            "villain": ["mind control", "shadow manipulation", "summoning"],
            "companion": ["minor healing", "trap detection", "emotional support"],
            "mentor": ["arcane knowledge", "prophecy", "ancient magic"],
            "antihero": ["dark pact", "dual wielding", "shadow walk"],
        }
        base = ability_map.get(role, ["basic combat"])
        extra = [f"{t}_infused" for t in traits[:3]]
        return base + extra

    def _generate_personality(self, traits: List[str]) -> Dict[str, Any]:
        return {
            "primary": "complex",
            "traits_description": " ".join(traits) + " con profundidad emocional.",
            "flaws": ["overprotective", "trust issues", "self-sacrificing"],
            "strengths": ["determined", "adaptable", "perceptive"],
        }

    def _generate_backstory(self, name: str, role: str, traits: List[str]) -> str:
        return f"{name} nació en tiempos de conflicto. {'Exiliado' if role == 'villain' else 'Marcado'} por circunstancias que forjaron su {'oscuridad' if role == 'villain' else 'determinación'}. Cada rasgo de {', '.join(traits)} cuenta una historia de supervivencia y transformación."

    async def generate_squad(self, theme: str = "fantasy", size: int = 4) -> List[Dict[str, Any]]:
        """Crea equipo coherente."""
        roles = ["hero", "villain", "companion", "mentor", "antihero"]
        squad = []
        for i in range(min(size, len(roles))):
            char = await self.design_character(
                role=roles[i],
                traits=[theme, "unique", f"specialty_{i}"],
            )
            squad.append(char)
        return squad

    async def generate_backstory(self, character_name: str, depth: int = 3) -> Dict[str, Any]:
        """Genera backstory con profundidad variable."""
        depths = {
            1: f"{character_name} es un guerrero solitario con un pasado misterioso.",
            2: f"{character_name} fue entrenado desde niño en artes marciales ancestrales. Su primer maestro desapareció misteriosamente.",
            3: f"{character_name} creció en las ruinas de un reino caído. Cada cicatriz cuenta una batalla perdida. Su búsqueda de redención lo llevó a los confines del mundo.",
            4: f"La historia de {character_name} abarca eras. Nació durante una guerra divina, criado por entidades antiguas que le enseñaron los secretos del universo. Su transformación de niño prodigio a guerrero legendario incluye traiciones, pérdidas y redescubrimientos que redefinieron su comprensión de la magia y la humanidad.",
            5: f"{character_name} es la encarnación de un ciclo eterno. Nacido, muerto y renacido múltiples veces, cada vida añade una capa a su ser. Sus memorias fragmentadas incluyen: un reino flotante, una era de hielo eterno, una guerra entre dimensiones, y un momento de paz absoluta que solo duró un suspiro. Todo converge hacia el presente donde debe elegir entre romper el ciclo o perpetuarlo.",
        }
        text = depths.get(depth, depths[3])
        return {
            "backstory_text": text,
            "key_events": [f"Evento {i+1}: {text[:60]}..." for i in range(min(depth, 5))],
        }


# ============================================================
# World Builder
# ============================================================


class WorldBuilder:
    """Creates magic systems and worlds."""

    async def create_magic_system(self, name: str, rules: List[str] = None) -> Dict[str, Any]:
        """Crea sistema mágico completo."""
        rules = rules or ["mana from environment", "runes as medium", "cost in lifeforce"]
        return {
            "system_name": name,
            "rules": rules,
            "limitations": [
                f"No puede crear materia del vacío",
                f"Cada hechizo consume algo: mana, memoria o vida",
            ],
            "costs": {
                "low": "mana ambiental",
                "medium": "energía vital moderada",
                "high": "memoria o años de vida",
                "extreme": "parte del alma",
            },
            "source": "mana del entorno",
            "medium": "runas y gestos",
        }

    async def build_world(self, theme: str, size: str = "medium") -> Dict[str, Any]:
        """Crea worldbuilding coherente."""
        geographies = {
            "small": "Un valle rodeado de montañas con un solo bosque encantado.",
            "medium": "Un continente con tres reinos, cada uno con cultura y magia distintas.",
            "large": "Múltiples continentes conectados por portales dimensionales, cada uno con ecosistemas mágicos únicos.",
        }
        cultures = [
            {"name": "Norte Helado", "traits": "Guerreros rudos, magia de hielo", "gov": "Clanes"},
            {"name": "Sur Arcadia", "traits": "Académicos, magia de runas", "gov": "Senado mágico"},
            {
                "name": "Este Sombrio",
                "traits": "Nómades, magia de sombras",
                "gov": "Consejo de ancianos",
            },
        ]
        return {
            "world_name": f"Mundo de {theme.title()}",
            "geography": geographies.get(size, geographies["medium"]),
            "cultures": cultures[: {"small": 1, "medium": 3, "large": 6}.get(size, 3)],
            "history": f"Este mundo fue forjado por los primeros magos que canalizaron el {theme}. {size.capitalize()} mundos han surgido desde entonces, cada uno añadiendo capas a la historia compartida.",
            "theme": theme,
            "size": size,
        }

    async def generate_pantheon(self, world_name: str, num_gods: int = 6) -> List[Dict[str, Any]]:
        """Crea dioses/panteón."""
        domains = [
            ("Aether", "Magic and knowledge", "curious, distant"),
            ("Terra", "Earth and endurance", "stoic, nurturing"),
            ("Flux", "Change and chaos", "mischievous, unpredictable"),
            ("Solace", "Peace and healing", "compassionate, gentle"),
            ("Tempest", "War and storm", "fierce, territorial"),
            ("Void", "Death and rebirth", "mysterious, patient"),
            ("Radiance", "Light and truth", "righteous, demanding"),
            ("Whisper", "Secrets and fate", "sly, omniscient"),
        ]
        gods = []
        for i in range(min(num_gods, len(domains))):
            name, domain, personality = domains[i]
            gods.append(
                {
                    "god_name": f"{name} el/la {domain.split()[0].title()}",
                    "domain": domain,
                    "personality": personality,
                    "world": world_name,
                }
            )
        return gods


# ============================================================
# Anime Prompt Optimizer
# ============================================================


class AnimePromptOptimizer:
    """Optimizes prompts for Stable Diffusion."""

    async def optimize_for_art(self, description: str, style: str = "anime") -> Dict[str, Any]:
        """Convierte descripción → prompt de arte."""
        style_tags = {
            "anime": "anime style, cel shading, vibrant colors, detailed eyes",
            "realistic": "photorealistic, detailed skin texture, natural lighting",
            "3d": "3d render, cinematic lighting, depth of field, detailed",
        }
        quality_tags = "masterpiece, best quality, ultra detailed, 8k resolution"
        optimized_prompt = (
            f"{description}, {style_tags.get(style, style_tags['anime'])}, {quality_tags}"
        )
        return {
            "prompt": optimized_prompt,
            "style_tags": style_tags.get(style, "").split(", "),
            "quality_tags": quality_tags.split(", "),
            "negative_prompt": "low quality, blurry, deformed, ugly, bad anatomy",
            "style": style,
        }


# ============================================================
# Content Library (SQLite storage)
# ============================================================


class ContentLibrary:
    """SQLite library for generated content."""

    def __init__(self, db_path: str = None) -> None:
        self.db_path = db_path or str(Path.home() / ".aria" / "content_library.db")
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS content_library (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT,
                content_text TEXT,
                metadata TEXT,
                user_feedback TEXT,
                generated_from_context TEXT,
                created_at REAL,
                rating INTEGER DEFAULT 0,
                improvements TEXT
            )
        """)
        conn.commit()
        conn.close()

    def save(self, type_: str, content_text: str, metadata: dict, context: str = "") -> int:
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO content_library (type, content_text, metadata, user_feedback, generated_from_context, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (type_, content_text, json.dumps(metadata), "", context, time.time()),
        )
        conn.commit()
        cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return cid

    def get_library(
        self, type_: str = None, limit: int = 20, sort_by: str = "recent"
    ) -> List[Dict[str, Any]]:
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        query = "SELECT * FROM content_library"
        conditions = []
        params = []
        if type_:
            conditions.append("type = ?")
            params.append(type_)
        if sort_by == "recent":
            order = "created_at DESC"
        elif sort_by == "rating":
            order = "rating DESC"
        else:
            order = "created_at DESC"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY " + order + " LIMIT ?"
        params.append(limit)
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        results = []
        for row in rows:
            item = dict(zip(cols, row))
            try:
                item["metadata"] = json.loads(item["metadata"]) if item["metadata"] else {}
            except Exception:
                item["metadata"] = {}
            results.append(item)
        conn.close()
        return results

    def rate(self, item_id: int, rating: int) -> bool:
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        conn.execute("UPDATE content_library SET rating = ? WHERE id = ?", (rating, item_id))
        conn.commit()
        conn.close()
        return True
