# -*- coding: utf-8 -*-
"""ARIA OS - AI Model Manager.

Registro y gestión de modelos de IA por tipo de entrada:
texto, visión (imagen/video), audio, multimodal.
Soporta Ollama local y modelos rule-based como fallback.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ARIA.AI.Models")


class ModelType(Enum):
    TEXT = "text"
    VISION = "vision"
    AUDIO = "audio"
    MULTIMODAL = "multimodal"
    EMBEDDING = "embedding"


@dataclass
class ModelCapability:
    """Capacidades de un modelo de IA."""
    model_id: str
    model_type: ModelType
    supports_video: bool = False
    supports_image: bool = False
    supports_audio: bool = False
    supports_text: bool = True
    max_tokens: int = 4096
    context_window: int = 4096
    languages: List[str] = field(default_factory=lambda: ["es", "en"])
    local_only: bool = True
    ollama_model: Optional[str] = None
    cost_per_1k_tokens: float = 0.0


class AIModelManager:
    """Gestor de modelos de IA.

    Registra modelos disponibles, detecta capacidades y provee
    una interfaz unificada para inferencia por tipo de contenido.
    """

    def __init__(self, ollama_url: str = "http://localhost:11434") -> None:
        self.ollama_url = ollama_url
        self.models: Dict[str, ModelCapability] = {}
        self._ollama_available = False
        self._ollama_models: List[str] = []
        self._discover_ollama()
        self._register_builtin()

    # ------------------------------------------------------------------ #
    # Descubrimiento y registro
    # ------------------------------------------------------------------ #
    def _discover_ollama(self) -> None:
        """Detecta modelos disponibles en Ollama local."""
        try:
            import urllib.request
            req = urllib.request.Request(f"{self.ollama_url}/api/tags")
            with urllib.request.urlopen(req, timeout=3) as r:
                data = __import__("json").loads(r.read())
            models = data.get("models", [])
            for m in models:
                name = m.get("name", "")
                self._ollama_models.append(name)
                cap = self._infer_capabilities(name)
                self.models[name] = cap
            self._ollama_available = True
            logger.info(f"Ollama disponible: {len(models)} modelo(s)")
        except Exception as exc:
            logger.warning(f"Ollama no disponible: {exc}")
            self._ollama_available = False

    def _infer_capabilities(self, model_name: str) -> ModelCapability:
        """Infere capacidades a partir del nombre del modelo."""
        lower = model_name.lower()
        model_type = ModelType.TEXT
        supports_video = False
        supports_image = False
        supports_audio = False

        if any(k in lower for k in ["vision", "vllm", "llava", "bakllava", "granite3.2-vision"]):
            model_type = ModelType.MULTIMODAL
            supports_image = True
            supports_video = True
        elif any(k in lower for k in ["whisper", "audio"]):
            model_type = ModelType.AUDIO
            supports_audio = True
        elif any(k in lower for k in ["embed", "bge", "e5"]):
            model_type = ModelType.EMBEDDING
        else:
            model_type = ModelType.TEXT

        return ModelCapability(
            model_id=model_name,
            model_type=model_type,
            supports_video=supports_video,
            supports_image=supports_image,
            supports_audio=supports_audio,
            supports_text=True,
            ollama_model=model_name,
            local_only=True,
        )

    def _register_builtin(self) -> None:
        """Registra modelos built-in si no hay Ollama."""
        if not self._ollama_available:
            self.models["local-text"] = ModelCapability(
                model_id="local-text",
                model_type=ModelType.TEXT,
                supports_text=True,
                local_only=True,
            )
            self.models["local-vision"] = ModelCapability(
                model_id="local-vision",
                model_type=ModelType.VISION,
                supports_image=True,
                supports_video=True,
                local_only=True,
            )

    # ------------------------------------------------------------------ #
    # Consulta de modelos
    # ------------------------------------------------------------------ #
    def is_available(self) -> bool:
        return self._ollama_available or len(self.models) > 0

    def list_models(self) -> List[Dict[str, Any]]:
        return [
            {
                "model_id": c.model_id,
                "type": c.model_type.value,
                "supports_video": c.supports_video,
                "supports_image": c.supports_image,
                "supports_audio": c.supports_audio,
                "supports_text": c.supports_text,
                "ollama_model": c.ollama_model,
                "local_only": c.local_only,
            }
            for c in self.models.values()
        ]

    def get_best_for(self, model_type: ModelType) -> Optional[ModelCapability]:
        """Retorna el mejor modelo disponible para un tipo dado."""
        candidates = [
            c for c in self.models.values()
            if c.model_type == model_type or (
                model_type == ModelType.VISION and c.supports_image
            ) or (
                model_type == ModelType.MULTIMODAL and c.supports_video
            )
        ]
        if not candidates:
            return None
        # Preferir modelos con más capacidades
        candidates.sort(key=lambda c: (
            c.supports_video, c.supports_image, c.supports_audio,
        ), reverse=True)
        return candidates[0]

    def get_best_vision(self) -> Optional[ModelCapability]:
        return self.get_best_for(ModelType.VISION)

    def get_best_multimodal(self) -> Optional[ModelCapability]:
        return self.get_best_for(ModelType.MULTIMODAL)

    def get_best_text(self) -> Optional[ModelCapability]:
        return self.get_best_for(ModelType.TEXT)

    def get_best_embedding(self) -> Optional[ModelCapability]:
        return self.get_best_for(ModelType.EMBEDDING)

    # ------------------------------------------------------------------ #
    # Inferencia
    # ------------------------------------------------------------------ #
    def chat(
        self,
        message: str,
        model_id: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        system_prompt: Optional[str] = None,
        history: Optional[List[List[str]]] = None,
        images: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Chat con un modelo. Soporta imágenes (multimodal) vía Ollama."""
        model = self._resolve_model(model_id)
        if not model:
            return {"response": "No hay modelo de IA disponible.", "provider": "local", "model": None}

        if model.ollama_model and self._ollama_available:
            return self._chat_ollama(
                model.ollama_model, message, temperature, max_tokens,
                system_prompt, history, images,
            )
        return self._chat_local(message, model_id or model.model_id)

    def _resolve_model(self, model_id: Optional[str]) -> Optional[ModelCapability]:
        if model_id and model_id in self.models:
            return self.models[model_id]
        return self.get_best_text()

    def _chat_ollama(
        self,
        model_name: str,
        message: str,
        temperature: float,
        max_tokens: int,
        system_prompt: Optional[str],
        history: Optional[List[List[str]]],
        images: Optional[List[str]],
    ) -> Dict[str, Any]:
        import json as _json
        import urllib.request

        msgs: List[Dict[str, Any]] = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        if history:
            for u, a in history[-10:]:
                msgs.append({"role": "user", "content": u})
                msgs.append({"role": "assistant", "content": a})

        # Construir mensaje con imágenes si las hay
        user_content: Dict[str, Any] = {"role": "user", "content": message}
        if images:
            user_content["images"] = images
        msgs.append(user_content)

        body = _json.dumps({
            "model": model_name,
            "messages": msgs,
            "stream": False,
            "temperature": temperature,
            "num_predict": max_tokens,
        }).encode()

        try:
            req = urllib.request.Request(
                f"{self.ollama_url}/api/chat",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as r:
                data = _json.loads(r.read())
            text = ((data.get("message") or {}).get("content") or "").strip()
            return {
                "response": text,
                "provider": "ollama",
                "model": model_name,
                "latency": 0.0,
            }
        except Exception as exc:
            logger.error(f"Ollama chat error: {exc}")
            return self._chat_local(message, model_name)

    def _chat_local(self, message: str, model_id: str) -> Dict[str, Any]:
        lower = message.lower()
        if any(g in lower for g in ["hola", "buenas", "hello", "hi"]):
            return {"response": "Hola, soy ARIA. Tu asistente nativo.", "provider": "local", "model": model_id}
        if "estado" in lower or "status" in lower:
            return {"response": "Sistema IA local activo.", "provider": "local", "model": model_id}
        return {
            "response": f"Recibido: '{message}'. Configura Ollama para respuestas con IA.",
            "provider": "local",
            "model": model_id,
        }

    # ------------------------------------------------------------------ #
    # Estadísticas
    # ------------------------------------------------------------------ #
    def stats(self) -> Dict[str, Any]:
        return {
            "ollama_available": self._ollama_available,
            "ollama_models": self._ollama_models,
            "registered_models": len(self.models),
            "vision_models": [m.model_id for m in self.models.values() if m.supports_image],
            "multimodal_models": [m.model_id for m in self.models.values() if m.supports_video],
        }
