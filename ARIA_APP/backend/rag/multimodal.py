# -*- coding: utf-8 -*-
"""ARIA OS - Multimodal RAG.

Procesamiento de consultas multi-modal: texto + imágenes + video.
Usa el modelo de visión disponible para describir contenido visual
y combinarlo con búsqueda textual.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.ai.models import AIModelManager, ModelType
from backend.ai.model_improver import ModelImprover, RecognitionResult

logger = logging.getLogger("ARIA.RAG.Multimodal")


class MultimodalRAG:
    """RAG multi-modal: combina búsqueda de texto con análisis de imagen/video."""

    def __init__(self, model_manager: AIModelManager) -> None:
        self.mm = model_manager
        self.improver = ModelImprover()

    def process(
        self,
        query: str,
        image_paths: Optional[List[str]] = None,
        video_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Procesa una consulta multi-modal."""
        results: Dict[str, Any] = {
            "query": query,
            "images": [],
            "video": None,
            "combined_description": "",
        }

        # Procesar imágenes
        if image_paths:
            for path in image_paths:
                result = self._process_image(path)
                results["images"].append(result)

        # Procesar video
        if video_info:
            results["video"] = self._process_video(video_info)

        # Construir descripción combinada
        parts = [f"Consulta: {query}"]
        for img in results["images"]:
            parts.append(f"Imagen ({img.get('format')}): {img.get('description', '')}")
        if results["video"]:
            parts.append(f"Video: {results['video'].get('description', '')}")

        results["combined_description"] = " | ".join(parts)
        return results

    def _process_image(self, path: str) -> Dict[str, Any]:
        """Procesa una sola imagen."""
        content_type = self.improver.detect_content_type(path)
        vision_model = self.mm.get_best_vision()

        description = ""
        confidence = 0.0

        if vision_model and vision_model.ollama_model and self.mm._ollama_available:
            # Usar Ollama para descripción real
            prompt = self.improver.build_vision_prompt(content_type)
            chat_result = self.mm.chat(
                message=prompt,
                model_id=vision_model.model_id,
                images=[path],
                temperature=0.3,
            )
            description = chat_result.get("response", "")
            confidence = 0.85
        else:
            # Fallback: descripción básica
            description = f"Archivo de imagen: {path}"
            confidence = 0.3

        enhanced = self.improver.enhance_visual_description(description, content_type)

        return {
            "path": path,
            "content_type": content_type,
            "description": description,
            "confidence": confidence,
            "features": enhanced.features,
        }

    def _process_video(self, video_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Procesa información de video."""
        result = self.improver.analyze_video_info(
            video_meta=video_info,
            visual_description=video_info.get("visual_description"),
        )
        return {
            "content_type": result.content_type,
            "format": result.format,
            "description": result.description,
            "confidence": result.confidence,
            "features": result.features,
            "metadata": result.metadata,
        }
