from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class ImportanceScore:
    score: float = 0.0
    level: str = "low"
    reasons: List[str] = field(default_factory=list)
    category: str = "general"
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContentProfile:
    url: str = ""
    platform: str = ""
    title: str = ""
    transcription_summary: str = ""
    topics: List[str] = field(default_factory=list)
    visual_description: str = ""
    importance: ImportanceScore = field(default_factory=ImportanceScore)
    tags: List[str] = field(default_factory=list)
    save_reason: str = ""
    analysis_timestamp: float = 0.0


class ContentClassifier:

    def __init__(self) -> None:
        self._vectorizer = TfidfVectorizer(max_features=1000, stop_words="spanish")
        self._fit_default()

    def _fit_default(self) -> None:
        corpus = [
            "tutorial educativo aprender clase curso explicar guía cómo",
            "entretenimiento música baile comedia viral trend meme fun",
            "noticia política evento información actual mundo",
            "cocina receta comida preparar ingredientes",
            "fitness ejercicio entrenamiento deporte gym",
            "negocio marketing emprendimiento ventas dinero",
            "vlog vida cotidiana rutina día",
            "arte pintura dibujo creatividad craft",
            "tecnología software app programación celular",
            "gaming juego gamer stream entretenimiento",
        ]
        try:
            self._vectorizer.fit(corpus)
        except Exception:
            pass

    def classify_importance(
        self,
        transcription_text: str = "",
        visual_desc: str = "",
        topics: List[str] = None,
        engagement: Optional[Dict[str, float]] = None,
        custom_criteria: Optional[Dict[str, Any]] = None,
    ) -> ImportanceScore:
        score = 0.0
        reasons: List[str] = []

        text_len = len(transcription_text or "")
        if text_len > 100:
            score += 0.1
            reasons.append("Contenido textual sustancial")
        if text_len > 500:
            score += 0.1
            reasons.append("Contenido detallado")

        topic_keywords = [
            "educativo",
            "tutorial",
            "cómo",
            "aprender",
            "importante",
            "clave",
            "guía",
        ]
        lower_text = (transcription_text + " " + visual_desc).lower()
        for kw in topic_keywords:
            if kw in lower_text:
                score += 0.15
                reasons.append(f"Contenido educativo/valioso: '{kw}'")
                break

        if topics:
            high_value = ["educativo", "tutorial", "noticia", "negocio", "tecnología"]
            for t in topics:
                if t.lower() in high_value:
                    score += 0.15
                    reasons.append(f"Tema de alto valor: {t}")

        if engagement:
            if engagement.get("view_count", 0) > 100000:
                score += 0.1
                reasons.append("Alto engagement (100k+ vistas)")
            if engagement.get("like_count", 0) > 10000:
                score += 0.05
                reasons.append("Alto engagement (10k+ likes)")

        if custom_criteria:
            focus_keywords = custom_criteria.get("focus_keywords", [])
            for kw in focus_keywords:
                if kw.lower() in lower_text:
                    score += 0.2
                    reasons.append(f"Concuerda con criterio personalizado: {kw}")

            required_topics = custom_criteria.get("required_topics", [])
            if required_topics:
                match = any(rt.lower() in lower_text for rt in required_topics)
                if match:
                    score += 0.15
                    reasons.append("Concuerda con temas requeridos")

        urgency_words = [
            "urgente",
            "ahora",
            "último",
            "reciente",
            "breaking",
            "secreto",
            "exclusivo",
        ]
        for uw in urgency_words:
            if uw in lower_text:
                score += 0.1
                reasons.append(f"Contenido urgente/temporal: {uw}")
                break

        score = min(score, 1.0)

        if score >= 0.6:
            level = "high"
        elif score >= 0.3:
            level = "medium"
        else:
            level = "low"

        return ImportanceScore(score=round(score, 3), level=level, reasons=reasons)

    def find_similar(
        self,
        target_text: str,
        corpus: List[str],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        if not corpus or not target_text:
            return []
        try:
            all_texts = [target_text] + corpus
            vectors = self._vectorizer.transform(all_texts)
            sims = cosine_similarity(vectors[0:1], vectors[1:]).flatten()
            indices = np.argsort(sims)[::-1][:top_k]
            return [
                {"index": int(i), "similarity": float(sims[i]), "text": corpus[i][:300]}
                for i in indices
                if sims[i] > 0.01
            ]
        except Exception:
            return []

    def auto_save_decision(self, profile: ContentProfile) -> bool:
        return profile.importance.score >= 0.4

    def tag_content(self, transcription: str, topics: List[str]) -> List[str]:
        tags = []
        lower = transcription.lower()
        tag_map = {
            "español": "idioma:español",
            "english": "idioma:inglés",
            "tutorial": "tipo:tutorial",
            "musica": "tipo:música",
            "deporte": "tipo:deporte",
            "cocina": "tipo:cocina",
            "comedia": "tipo:comedia",
            "viaje": "tipo:viaje",
            "tecnología": "tipo:tech",
            "noticias": "tipo:noticias",
            "fitness": "tipo:fitness",
        }
        for keyword, tag in tag_map.items():
            if keyword.lower() in lower:
                tags.append(tag)
        for topic in topics:
            tags.append(f"tema:{topic.lower()}")
        return list(set(tags))
