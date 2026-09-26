import logging
from typing import Dict, Any

from AURA_Core.vision.screen_analyzer import ScreenAnalyzer
from AURA_Core.vision.multimodal_router import MultimodalRouter

logger = logging.getLogger("AURA_VisionIntegration")


class VisionEventIntegration:
    """Orquesta captura, análisis visual y feedback al HUD / Knowledge Graph."""

    def __init__(self) -> None:
        self.analyzer = ScreenAnalyzer()
        self.router = MultimodalRouter()

    def run_analysis(self, consulta: str) -> Dict[str, Any]:
        resultado = self.router.analizar_pantalla(consulta)
        telemetry = {
            "event": "screen_analysis",
            "payload": {
                "query": consulta,
                "result": resultado,
            },
        }
        logger.info("Análisis de pantalla listo para enviar al HUD: %s", telemetry)
        return telemetry

    def on_healer_failure(self, error_context: str) -> str:
        """Disparado por healer.py cuando falla la reparación por código."""
        consulta = (
            "Examina la imagen de la pantalla y dime las coordenadas relativas X/Y "
            "o el nuevo texto del botón que ha cambiado. Contexto: " + error_context
        )
        telemetry = self.run_analysis(consulta)
        return telemetry["payload"]["result"]


vision_integration = VisionEventIntegration()
