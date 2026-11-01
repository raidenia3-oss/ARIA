# -*- coding: utf-8 -*-
"""ARIA OS - Model Improver.

Mejora el reconocimiento de modelos de IA para video, foto y cualquier
tipo de información. Incluye:
- Mejora de prompts de visión
- Extracción de features de múltiples formatos
- Análisis de frames de video sin descarga completa
- Clasificación de contenido por tipo de medio
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ARIA.AI.ModelImprover")


@dataclass
class RecognitionResult:
    """Resultado de reconocimiento de contenido."""
    content_type: str  # image, video, audio, document, text, unknown
    format: str  # mp4, jpg, png, mp3, pdf, etc.
    description: str
    confidence: float
    features: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    processed_at: float = field(default_factory=time.time)


class ModelImprover:
    """Mejora el reconocimiento de IA para cualquier formato de información.

    Capacidades:
    - Reconocimiento de imágenes y frames de video
    - Extracción de texto de documentos (OCR-like)
    - Análisis de audio
    - Clasificación de contenido
    - Mejora de prompts de visión para mejor precisión
    """

    def __init__(self) -> None:
        self.supported_image_extensions = {
            ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".svg"
        }
        self.supported_video_extensions = {
            ".mp4", ".avi", ".mkv", ".mov", ".webm", ".flv", ".wmv", ".m4v"
        }
        self.supported_audio_extensions = {
            ".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a", ".wma"
        }
        self.supported_document_extensions = {
            ".pdf", ".doc", ".docx", ".txt", ".md", ".rtf", ".html", ".csv", ".json"
        }

    # ------------------------------------------------------------------ #
    # Content type detection
    # ------------------------------------------------------------------ #
    def detect_content_type(self, file_path: str) -> str:
        """Detecta el tipo de contenido por extensión."""
        ext = Path(file_path).suffix.lower()
        if ext in self.supported_image_extensions:
            return "image"
        if ext in self.supported_video_extensions:
            return "video"
        if ext in self.supported_audio_extensions:
            return "audio"
        if ext in self.supported_document_extensions:
            return "document"
        return "unknown"

    def detect_from_url(self, url: str) -> str:
        """Detecta tipo de contenido desde una URL."""
        lower = url.lower()
        if any(k in lower for k in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"]):
            return "image"
        if any(k in lower for k in [".mp4", ".avi", ".mkv", ".mov", ".webm", "/reel/", "/watch/", "/shorts/"]):
            return "video"
        if any(k in lower for k in [".mp3", ".wav", ".ogg", ".flac", ".aac"]):
            return "audio"
        if any(k in lower for k in [".pdf", ".doc", ".txt", ".md", ".html"]):
            return "document"
        return "unknown"

    # ------------------------------------------------------------------ #
    # Vision recognition improvement
    # ------------------------------------------------------------------ #
    def build_vision_prompt(
        self,
        content_type: str = "image",
        language: str = "es",
        detail_level: str = "detailed",
    ) -> str:
        """Construye un prompt optimizado para reconocimiento visual."""
        base = (
            "Eres un experto en análisis visual. Describe detalladamente lo que ves en la imagen. "
            "Incluye: personas, objetos, texto visible, acciones, entorno, colores, estilo, "
            "emociones, y cualquier detalle relevante. Sé preciso y conciso."
        )
        if content_type == "video":
            base += " Esta es una representación de un video (frame clave). Describe la acción y el contexto temporal."
        if language == "es":
            base += " Responde en español."
        else:
            base += " Respond in English."
        if detail_level == "detailed":
            base += " Da una descripción exhaustiva."
        elif detail_level == "concise":
            base += " Sé breve pero completo."
        return base

    def enhance_visual_description(
        self,
        raw_description: str,
        content_type: str = "image",
    ) -> RecognitionResult:
        """Mejora una descripción visual cruda con estructura."""
        features: List[str] = []
        text_lower = raw_description.lower()

        # Detectar elementos clave
        if any(k in text_lower for k in ["persona", "person", "gente", "hombre", "mujer", "niño"]):
            features.append("personas")
        if any(k in text_lower for k in ["texto", "letrero", "cartel", "escribe", "escribir"]):
            features.append("texto_visible")
        if any(k in text_lower for k in ["naturaleza", "árbol", "monte", "playa", "cielo", "nube"]):
            features.append("entorno_natural")
        if any(k in text_lower for k in ["ciudad", "edificio", "calle", "coche", "tráfico"]):
            features.append("entorno_urbano")
        if any(k in text_lower for k in ["comida", "plato", "bebida", "restaurante", "cocina"]):
            features.append("alimentación")
        if any(k in text_lower for k in ["tecnología", "computadora", "móvil", "pantalla", "código"]):
            features.append("tecnología")

        confidence = min(0.95, 0.5 + len(features) * 0.1)

        return RecognitionResult(
            content_type=content_type,
            format="unknown",
            description=raw_description,
            confidence=confidence,
            features=features,
        )

    # ------------------------------------------------------------------ #
    # Video frame analysis (no full download)
    # ------------------------------------------------------------------ #
    def analyze_video_info(
        self,
        video_meta: Dict[str, Any],
        visual_description: Optional[str] = None,
    ) -> RecognitionResult:
        """Analiza información de video desde metadatos de yt-dlp."""
        features: List[str] = []
        desc_parts: List[str] = []

        duration = video_meta.get("duration", 0)
        if duration:
            desc_parts.append(f"Duración: {duration}s")
            if duration < 60:
                features.append("video_corto")
            elif duration < 300:
                features.append("video_medio")
            else:
                features.append("video_largo")

        width = video_meta.get("video_width", 0)
        height = video_meta.get("video_height", 0)
        if width and height:
            desc_parts.append(f"Resolución: {width}x{height}")
            if width >= 1920:
                features.append("alta_resolución")

        codec = video_meta.get("video_codec", "")
        if codec:
            desc_parts.append(f"Codec: {codec}")
            features.append(f"codec_{codec}")

        fps = video_meta.get("video_fps", 0)
        if fps:
            desc_parts.append(f"FPS: {fps}")

        bitrate = video_meta.get("video_bitrate", 0)
        if bitrate:
            desc_parts.append(f"Bitrate: {bitrate} kbps")

        if visual_description:
            desc_parts.append(f"Visual: {visual_description}")
            enhanced = self.enhance_visual_description(visual_description, "video")
            features.extend(enhanced.features)

        return RecognitionResult(
            content_type="video",
            format=video_meta.get("video_ext", "mp4"),
            description=" | ".join(desc_parts),
            confidence=0.8,
            features=features,
            metadata=video_meta,
        )

    # ------------------------------------------------------------------ #
    # Content classification
    # ------------------------------------------------------------------ #
    def classify_content(
        self,
        title: str,
        description: str,
        visual_desc: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Clasifica el contenido por categoría temática."""
        text = f"{title} {description} {visual_desc or ''} {' '.join(tags or [])}".lower()

        categories = {
            "educativo": ["curso", "tutorial", "aprende", "educación", "estudio", "clase", "lección"],
            "tecnología": ["código", "programación", "software", "ia", "inteligencia artificial", "tech"],
            "entretenimiento": ["diversión", "humor", "comedia", "música", "película", "serie"],
            "noticias": ["noticia", "actualidad", "política", "mundo", "reporte"],
            "deportes": ["fútbol", "baloncesto", "deporte", "entrenamiento", "gimnasio"],
            "ciencia": ["ciencia", "investigación", "experimento", "física", "química", "biología"],
            "salud": ["salud", "medicina", "ejercicio", "nutrición", "bienestar"],
            "viajes": ["viaje", "turismo", "vacaciones", "hotel", "destino"],
        }

        scores: Dict[str, int] = {}
        for cat, keywords in categories.items():
            score = sum(1 for k in keywords if k in text)
            if score > 0:
                scores[cat] = score

        best_cat = max(scores, key=scores.get) if scores else "otro"
        confidence = min(0.95, scores.get(best_cat, 0) * 0.2 + 0.3)

        return {
            "category": best_cat,
            "confidence": confidence,
            "all_scores": scores,
            "tags_detected": tags or [],
        }

    # ------------------------------------------------------------------ #
    # Stats
    # ------------------------------------------------------------------ #
    def stats(self) -> Dict[str, Any]:
        return {
            "supported_image_extensions": list(self.supported_image_extensions),
            "supported_video_extensions": list(self.supported_video_extensions),
            "supported_audio_extensions": list(self.supported_audio_extensions),
            "supported_document_extensions": list(self.supported_document_extensions),
        }
