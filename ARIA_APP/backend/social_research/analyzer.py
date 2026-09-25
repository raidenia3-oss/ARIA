from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image


@dataclass
class VisualAnalysis:
    description: str = ""
    tags: List[str] = field(default_factory=list)
    scene_type: str = ""
    mood: str = ""
    objects_detected: List[str] = field(default_factory=list)
    text_overlays: List[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class ContentTopic:
    topic: str = ""
    category: str = ""
    subcategory: str = ""
    confidence: float = 0.0
    keywords: List[str] = field(default_factory=list)


@dataclass
class FullAnalysis:
    video_path: str = ""
    transcription: Optional[Any] = None
    visual_analysis: Optional[VisualAnalysis] = None
    topics: List[ContentTopic] = field(default_factory=list)
    summary: str = ""
    key_moments: List[Dict[str, Any]] = field(default_factory=list)
    age_rating: str = "unknown"
    is_educational: bool = False
    is_entertainment: bool = False
    is_educational_score: float = 0.0
    is_entertainment_score: float = 0.0
    raw_response: str = ""


class VideoAnalyzer:

    def __init__(self, openai_client: Optional[Any] = None) -> None:
        self._openai_client = openai_client
        self._vision_model = "gpt-4o"

    def set_client(self, client: Any) -> None:
        self._openai_client = client

    def analyze_visual(self, image_path: str) -> VisualAnalysis:
        if not self._openai_client:
            return self._analyze_visual_local(image_path)
        try:
            img = Image.open(image_path)
            response = self._openai_client.chat.completions.create(
                model=self._vision_model,
                messages=[
                    {
                        "role": "system",
                        "content": "Analiza esta imagen de un video corto. Describe: qué se ve, el ambiente/mood, tipo de contenido (educativo, entretenimiento, vlog, tutorial, etc.), objetos principales, texto visible, y el estado de ánimo general. Responde en español en formato JSON: {description, tags, scene_type, mood, objects_detected, text_overlays, confidence}.",
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"file://{image_path}"}},
                        ],
                    },
                ],
                response_format={"type": "json_object"},
                max_tokens=800,
            )
            data = response.choices[0].message.content
            import json

            parsed = json.loads(data) if data else {}
            return VisualAnalysis(
                description=parsed.get("description", ""),
                tags=parsed.get("tags", []),
                scene_type=parsed.get("scene_type", ""),
                mood=parsed.get("mood", ""),
                objects_detected=parsed.get("objects_detected", []),
                text_overlays=parsed.get("text_overlays", []),
                confidence=parsed.get("confidence", 0.5),
            )
        except Exception as e:
            return self._analyze_visual_local(image_path)

    def _analyze_visual_local(self, image_path: str) -> VisualAnalysis:
        try:
            img = Image.open(image_path)
            w, h = img.size
            desc = f"Imagen {w}x{h}"
        except Exception:
            desc = "No se pudo cargar imagen"
        return VisualAnalysis(description=desc, confidence=0.3)

    def analyze_video(
        self,
        video_path: str,
        transcription_text: str = "",
        visual_samples: Optional[List[str]] = None,
    ) -> FullAnalysis:
        visual_results: List[VisualAnalysis] = []
        if visual_samples:
            for sp in visual_samples:
                va = self.analyze_visual(sp)
                visual_results.append(va)
        elif Path(video_path).exists():
            from backend.social_research.collector import SocialCollector

            collector = SocialCollector()
            frames = collector.extract_frames(video_path, fps=0.15, max_frames=10)
            for f in frames:
                va = self.analyze_visual(f["path"])
                visual_results.append(va)

        combined_desc = "; ".join(v.description for v in visual_results if v.description)
        combined_tags = []
        for v in visual_results:
            combined_tags.extend(v.tags)

        topics = self._classify_topics(transcription_text, combined_desc)

        summary = self._generate_summary(transcription_text, visual_results, topics)

        key_moments = self._detect_key_moments(transcription_text)

        is_edu = any(
            t.topic.lower() in ["educativo", "tutorial", "cómo", "aprender", "enseñar"]
            for t in topics
        )
        is_ent = any(
            t.topic.lower()
            in ["entretenimiento", "música", "comedia", "entretenimiento", "dance", "danza"]
            for t in topics
        )

        return FullAnalysis(
            video_path=video_path,
            transcription=None,
            visual_analysis=visual_results[0] if visual_results else VisualAnalysis(),
            topics=topics,
            summary=summary,
            key_moments=key_moments,
            is_educational=is_edu,
            is_entertainment=is_ent,
            is_educational_score=sum(
                t.confidence
                for t in topics
                if t.topic.lower() in ["educativo", "tutorial", "cómo", "aprender", "enseñar"]
            )
            / max(len(topics), 1),
            is_entertainment_score=sum(
                t.confidence
                for t in topics
                if t.topic.lower()
                in ["entretenimiento", "música", "comedia", "entretenimiento", "dance", "danza"]
            )
            / max(len(topics), 1),
            raw_response=summary,
        )

    def _classify_topics(self, text: str, visual_desc: str = "") -> List[ContentTopic]:
        combined = (text + " " + visual_desc).lower()
        topic_map: Dict[str, Dict[str, Any]] = {
            "Educativo": {
                "category": "educativo",
                "keywords": [
                    "enseñar",
                    "aprender",
                    "tutorial",
                    "cómo",
                    "guía",
                    "explicar",
                    "curso",
                    "clase",
                    "historia",
                    "ciencia",
                    "matemáticas",
                ],
            },
            "Entretenimiento": {
                "category": "entretenimiento",
                "keywords": [
                    "música",
                    "baile",
                    "comedia",
                    "chiste",
                    "entretenimiento",
                    "funny",
                    "viral",
                    "trend",
                    "meme",
                ],
            },
            "Cocina": {
                "category": "lifestyle",
                "keywords": [
                    "cocina",
                    "receta",
                    "comer",
                    "food",
                    "kitchen",
                    "ingrediente",
                    "preparar",
                ],
            },
            "Fitness": {
                "category": "lifestyle",
                "keywords": [
                    "ejercicio",
                    "gym",
                    "fitness",
                    "entrenamiento",
                    "deporte",
                    "running",
                    "workout",
                ],
            },
            "Tecnología": {
                "category": "tecnología",
                "keywords": [
                    "tech",
                    "technology",
                    "programa",
                    "código",
                    "software",
                    "app",
                    "celular",
                    "phone",
                ],
            },
            "Vlog": {
                "category": "contenido personal",
                "keywords": ["vlog", "día", "day", "mi vida", "daily", "routine", "rutina"],
            },
            "Noticias": {
                "category": "información",
                "keywords": [
                    "noticia",
                    "news",
                    "política",
                    "politics",
                    "evento",
                    "event",
                    "información",
                ],
            },
            "Arte": {
                "category": "creativo",
                "keywords": [
                    "arte",
                    "art",
                    "pintura",
                    "dibujo",
                    "draw",
                    "craft",
                    "manualidad",
                    "design",
                ],
            },
            "Negocios": {
                "category": "negocios",
                "keywords": [
                    "negocio",
                    "business",
                    "emprendimiento",
                    "marketing",
                    "ventas",
                    "dinero",
                ],
            },
            "Gaming": {
                "category": "entretenimiento",
                "keywords": ["juego", "game", "gaming", "play", "gamer", "stream"],
            },
        }

        topics: List[ContentTopic] = []
        for name, info in topic_map.items():
            score = sum(1 for kw in info["keywords"] if kw in combined)
            if score > 0:
                topics.append(
                    ContentTopic(
                        topic=name,
                        category=info["category"],
                        subcategory="",
                        confidence=min(score / len(info["keywords"]) * 2, 1.0),
                        keywords=[kw for kw in info["keywords"] if kw in combined],
                    )
                )

        if not topics:
            topics.append(ContentTopic(topic="General", category="general", confidence=0.3))

        topics.sort(key=lambda t: t.confidence, reverse=True)
        return topics[:5]

    def _generate_summary(
        self,
        transcription_text: str,
        visual_results: List[VisualAnalysis],
        topics: List[ContentTopic],
    ) -> str:
        parts = []
        if topics:
            topic_names = ", ".join(t.topic for t in topics[:3])
            parts.append(f"Temas principales: {topic_names}.")
        if transcription_text:
            clean_text = " ".join(transcription_text.split())
            if len(clean_text) > 200:
                clean_text = clean_text[:200] + "..."
            parts.append(f"Contenido hablado: {clean_text}")
        if visual_results and visual_results[0].description:
            parts.append(f"Visual: {visual_results[0].description}")
        return " ".join(parts) if parts else "Sin análisis disponible."

    def _detect_key_moments(self, transcription_text: str) -> List[Dict[str, Any]]:
        if not transcription_text:
            return []
        moments = []
        import re

        hooks = [
            "pero",
            "sin embargo",
            "importante",
            "clave",
            "lo que",
            "esto es",
            "mir",
            "watch",
            "note",
            "tip",
        ]
        segments = transcription_text.split(". ")
        for i, seg in enumerate(segments):
            for hook in hooks:
                if hook.lower() in seg.lower():
                    moments.append(
                        {
                            "type": "hook",
                            "text": seg.strip()[:200],
                            "index": i,
                        }
                    )
                    break
        return moments[:10]
