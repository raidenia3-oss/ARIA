import os
import time
import logging
import base64
import io
from typing import Optional, Dict, Tuple

import numpy as np
from PIL import ImageGrab, Image

logger = logging.getLogger("AURA_Vision")


class ScreenAnalyzer:
    def __init__(self, default_region: Optional[Tuple[int, int, int, int]] = None):
        self.default_region = default_region

    def capturar_region(self, region: Optional[Tuple[int, int, int, int]] = None) -> Image.Image:
        """Captura una región rectangular (left, top, right, bottom)."""
        bbox = region or self.default_region or (0, 0, 1920, 1080)
        try:
            image = ImageGrab.grab(bbox=bbox, all_screens=True)
            logger.info("Captura obtenida: %s", image.size)
            return image
        except Exception as e:
            logger.error("Fallo en captura: %s", e)
            raise

    def _encode_base64(self, image: Image.Image, fmt: str = "PNG") -> str:
        buffer = io.BytesIO()
        image.save(buffer, format=fmt)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def _encode_base64_safe(self, image: Image.Image, fmt: str = "PNG") -> str:
        try:
            return self._encode_base64(image, fmt=fmt)
        except Exception as e:
            logger.error("Fallo codificando base64: %s", e)
            raise

    def analizar_interfaz(
        self, image_path: Optional[str] = None, contextual_query: str = ""
    ) -> Dict:
        start = time.time()
        if image_path:
            try:
                pil_image = Image.open(image_path)
            except Exception as e:
                logger.error("No se pudo abrir la imagen: %s", e)
                return {"error": f"No se pudo abrir la imagen: {e}", "text": "", "base64": ""}
        else:
            pil_image = self.capturar_region()
        try:
            b64 = self._encode_base64_safe(pil_image, fmt="PNG")
            result = {
                "text": contextual_query or "Análisis de pantalla",
                "base64": b64,
                "format": "image/png",
                "size": pil_image.size,
                "elapsed_ms": int((time.time() - start) * 1000),
            }
            logger.info("Análisis preparado en %d ms", result["elapsed_ms"])
            return result
        except Exception as e:
            logger.error("Error en analizar_interfaz: %s", e)
            return {"error": str(e), "text": "", "base64": ""}
