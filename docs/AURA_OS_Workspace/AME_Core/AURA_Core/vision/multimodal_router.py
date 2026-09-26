import base64
import logging
from typing import Dict, Optional

from AURA_Core.vision.screen_analyzer import ScreenAnalyzer
from AURA_Core.automation.llm_router import llm_router

logger = logging.getLogger("AURA_VisionRouter")


class MultimodalRouter:
    def __init__(self) -> None:
        self.analyzer = ScreenAnalyzer()

    def enviar_imagen_a_llm(self, image_base64: str, prompt: str) -> str:
        payload = {
            "model": llm_router.primary.model,
            "messages": [
                {
                    "role": "system",
                    "content": "Eres un asistente de vision que analiza capturas de pantalla.",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                        },
                    ],
                },
            ],
            "max_tokens": 256,
            "temperature": 0.0,
        }
        return llm_router.chat_multimodal(
            system_prompt="Eres un asistente de vision que analiza capturas de pantalla.",
            user_text=prompt,
            image_base64=image_base64,
            temperature=0.0,
            max_tokens=256,
        )

    def analizar_pantalla(self, consulta: str) -> str:
        resultado = self.analyzer.analizar_interfaz(contextual_query=consulta)
        if "error" in resultado and resultado["error"]:
            return f"Error en captura: {resultado['error']}"
        image_b64 = resultado.get("base64", "")
        if not image_b64:
            return "Captura vacia."
        prompt = (
            consulta
            or "Examina la imagen de la pantalla y dime las coordenadas relativas X/Y o el nuevo texto del boton que ha cambiado."
        )
        respuesta = self.enviar_imagen_a_llm(image_b64, prompt)
        logger.info("Vision analisis: %s", respuesta[:200])
        return respuesta


multimodal_router = MultimodalRouter()
