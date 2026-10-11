# Motor híbrido: núcleo unificado + módulos
from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass
class ModelConfig:
    unified_id: str = "qwen2.5-vl:3b-q4_k_m"
    vision_enabled: bool = True
    modules: Dict[str, str] = None

    def __post_init__(self):
        if self.modules is None:
            self.modules = {"stt": "whisper", "ocr": "rapidocr", "video": "framesampler"}
