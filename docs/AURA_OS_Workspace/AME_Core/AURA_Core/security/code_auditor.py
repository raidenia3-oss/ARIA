#!/usr/bin/env python3
"""
code_auditor.py - AURA Security Shield Automated Auditor Module.
Inspecciona archivos de automatización y código fuente usando DeepSeek (vía LLMRouter)
para detectar vulnerabilidades como desbordamientos, selectores frágiles o fugas de tokens.
"""

import os
import sys
import logging
import json
from typing import List, Dict, Optional
from pathlib import Path

# Asegurar que podemos importar desde AURA_Core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai_router import AuraCognitiveRouter

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("CodeAuditor")


class CodeAuditor:
    def __init__(self):
        self.router = AuraCognitiveRouter()
        self.system_prompt = """
        Eres un Experto en Ciberseguridad y Analista de Código Estático de nivel Senior en un entorno de Red Teaming ético.
        Tu misión es auditar fragmentos de código de automatización (Playwright/Python) y lógica de negocio para encontrar:
        1. Fugas de tokens, credenciales o información sensible.
        2. Selectores vulnerables o frágiles que podrían ser manipulados.
        3. Riesgos de confusión de tipos o inyecciones de datos.
        4. Lógica de reintento infinita o desbordamientos de buffer/memoria.
        5. Malas prácticas de manejo de excepciones que oculten fallos de seguridad.

        Responde de forma estructurada con un REPORTE DE AUDITORÍA que incluya:
        - LÍNEA: [Número o Fragmento]
        - RIESGO: [Bajo/Medio/Alto/Crítico]
        - DESCRIPCIÓN: [Explicación detallada]
        - RECOMENDACIÓN: [Código corregido o acción a tomar]

        Si el código parece seguro, indica: "ESTADO: SEGURO".
        """

    def audit_file(self, filepath: str) -> List[Dict]:
        """Lee un archivo y envía fragmentos al LLM para su auditoría."""
        if not os.path.exists(filepath):
            logger.error(f"Archivo no encontrado: {filepath}")
            return []

        logger.info(f"Iniciando auditoría de: {filepath}")
        with open(filepath, "r", encoding="utf-8") as f:
            code_content = f.read()

        # Enviar el código completo o fragmentado si es muy largo
        # Por simplicidad enviamos el bloque completo si no excede límites razonables
        prompt = f"AUDITA EL SIGUIENTE CÓDIGO:\n\n```python\n{code_content}\n```"

        # Usamos el router con preferencia por el modelo de razonamiento (DeepSeek-R1)
        # Forzamos task 'code' para que el router elija el mejor modelo de codificación/auditoría
        response = self.router.route(
            prompt, context={"task": "code", "system_prompt": self.system_prompt}
        )

        audit_report = response.get("response", "No se pudo obtener reporte.")
        logger.info("Auditoría completada.")

        # Procesar el reporte para extraer alertas críticas para el HUD
        alerts = self._parse_report_for_alerts(audit_report, filepath)
        return alerts

    def _parse_report_for_alerts(self, report: str, filepath: str) -> List[Dict]:
        """Analiza el reporte textual buscando patrones de riesgo alto o crítico."""
        alerts = []
        lines = report.split("\n")
        current_alert = None

        for line in lines:
            if (
                "RIESGO: [Alto]" in line
                or "RIESGO: [Crítico]" in line
                or "RIESGO: Alto" in line
                or "RIESGO: Crítico" in line
            ):
                current_alert = {
                    "file": filepath,
                    "level": "CRITICAL" if "Crítico" in line else "WARNING",
                    "message": "Vulnerabilidad detectada en auditoría de código.",
                }
            elif current_alert and "DESCRIPCIÓN:" in line:
                current_alert["description"] = line.split("DESCRIPCIÓN:")[1].strip()
                alerts.append(current_alert)
                current_alert = None

        # Si no se encontró estructura pero hay palabras clave
        if not alerts and ("VULNERABILIDAD" in report.upper() or "ERROR" in report.upper()):
            if (
                "ALTO" in report.upper()
                or "CRÍTICO" in report.upper()
                or "CRITICO" in report.upper()
            ):
                alerts.append(
                    {
                        "file": filepath,
                        "level": "CRITICAL",
                        "message": "Se detectaron posibles fallos críticos en el reporte de IA.",
                    }
                )

        return alerts

    def send_to_hud(self, alerts: List[Dict]):
        """Envía las alertas al HUD de JARVIS vía EventManager (si está disponible)."""
        if not alerts:
            return

        try:
            # Importar EventManager para broadcast
            from event_manager import EventManager

            config = {"rules_file": "rules.json", "telemetry_file": "telemetry_history.json"}
            em = EventManager(config)

            for alert in alerts:
                logger.warning(f"ENVIANDO ALERTA DE SEGURIDAD AL HUD: {alert['message']}")
                em._broadcast_ws("security_alert", {"event": "security_alert", "payload": alert})
        except Exception as e:
            logger.error(f"Error al enviar alertas al HUD: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python code_auditor.py <archivo_a_auditar>")
        sys.exit(1)

    auditor = CodeAuditor()
    alerts = auditor.audit_file(sys.argv[1])
    if alerts:
        print(f"ALERTA: Se detectaron {len(alerts)} posibles vulnerabilidades.")
        auditor.send_to_hud(alerts)
    else:
        print("OK: No se detectaron vulnerabilidades criticas.")
