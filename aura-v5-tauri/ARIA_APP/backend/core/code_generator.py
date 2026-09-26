# -*- coding: utf-8 -*-
"""ARIA OS - Code Generator.

AURA genera codigo para si misma: consulta a Jan, parsea la respuesta JSON
y retorna modulo completo + tests + puntos de integracion.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

import httpx

from backend.core.event_bus import CoreEvent, EventType, get_event_bus

logger = logging.getLogger("ARIA.CodeGenerator")

JAN_BASE_URL = "http://localhost:1337/v1"
JAN_TIMEOUT = 30.0


class CodeGenerator:
    """Genera modulo de code completo vía Jan (o fallback local)."""

    def __init__(self, jan_url: str = JAN_BASE_URL, timeout: float = JAN_TIMEOUT) -> None:
        self.jan_url = jan_url.rstrip("/")
        self.timeout = timeout
        self._bus = get_event_bus()

    async def generate_feature_code(
        self,
        feature: str,
        existing_modules: Optional[List[str]] = None,
        requirements: str = "",
        language: str = "python",
    ) -> Dict[str, Any]:
        """Genera un modulo completo para la feature dada.

        Retorna: module_name, code, integration_points, tests, dependencies.
        """
        t0 = time.time()
        existing_modules = existing_modules or []

        prompt = self._build_prompt(feature, existing_modules, requirements, language)
        self._bus.emit_simple(
            EventType.THOUGHT.value,
            {
                "stage": "code_generator_start",
                "feature": feature[:100],
                "language": language,
            },
            agent="code_generator",
            status="running",
        )

        raw = await self._call_jan(prompt)
        parsed = self._parse_response(raw, feature, language)

        duration_ms = round((time.time() - t0) * 1000, 2)
        result = {
            "module_name": parsed.get("module_name", self._slug(feature) + ".py"),
            "code": parsed.get("code", ""),
            "integration_points": parsed.get("integration_points", []),
            "tests": parsed.get("tests", ""),
            "dependencies": parsed.get("dependencies", []),
            "language": language,
            "feature": feature,
            "requirements": requirements,
            "duration_ms": duration_ms,
            "status": "success",
        }

        self._bus.emit_simple(
            EventType.COMPLETE.value,
            {
                "stage": "code_generator_complete",
                "module_name": result["module_name"],
                "duration_ms": duration_ms,
            },
            agent="code_generator",
            status="completed",
        )

        logger.info(
            "code_generator: feature=%s module=%s latency=%sms",
            feature[:60],
            result["module_name"],
            duration_ms,
        )
        return result

    def _build_prompt(
        self,
        feature: str,
        existing_modules: List[str],
        requirements: str,
        language: str,
    ) -> str:
        """construye el prompt para Jan."""
        mod_list = "\n".join(f"  - {m}" for m in existing_modules) or "  (ninguno)"
        return (
            f"Eres un ingeniero de software senior. Genera un modulo COMPLETO y FUNCIONAL"
            f" para la siguiente feature:\n\n"
            f"FEATURE: {feature}\n"
            f"REQUISITOS: {requirements}\n"
            f"LENGUAJE: {language}\n\n"
            f"MODULOS EXISTENTES (para integrar):\n{mod_list}\n\n"
            f"RESPONDE EN JSON VALIDO con esta estructura exacta:\n"
            f'{{"module_name": "nombre_modulo.py",\n'
            f'  "code": "codigo completo del modulo",\n'
            f'  "integration_points": ["punto 1", "punto 2"],\n'
            f'  "tests": "codigo de prueba",\n'
            f'  "dependencies": ["dep1", "dep2"]}}\n\n'
            f"El modulo debe ser auto contenido, con type hints, manejo de errores"
            f" y documentacion."
        )

    async def _call_jan(self, prompt: str) -> str:
        """llama a Jan (OpenAI-compat) y retorna el texto crudo."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                r = await c.post(
                    f"{self.jan_url}/chat/completions",
                    json={
                        "model": "gemma-3-1b-it",
                        "messages": [
                            {
                                "role": "system",
                                "content": "Eres un ingeniero de software experto. Responde solo con JSON valido.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.3,
                        "max_tokens": 4096,
                    },
                )
                if r.status_code == 200:
                    data = r.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    return content
                logger.warning("Jan devolvio status %s", r.status_code)
        except Exception as exc:
            logger.debug("Jan no disponible para code gen: %s", exc)
        return self._fallback_code(prompt)

    def _fallback_code(self, prompt: str) -> str:
        """Genera un modulo basico cuando Jan no esta disponible."""
        return json.dumps(
            {
                "module_name": "feature_module.py",
                "code": '"""Modulo auto-generado (fallback)."""\n\nfrom __future__ import annotations\n\ndef execute(config=None):\n    return {"status": "ok", "message": "implementar"}\n',
                "integration_points": ["importar execute() en main.py"],
                "tests": 'def test_execute():\n    assert execute({})["status"] == "ok"\n',
                "dependencies": [],
            },
            ensure_ascii=False,
        )

    def _parse_response(self, raw: str, feature: str, language: str) -> Dict[str, Any]:
        """Parsea la respuesta de Jan (JSON o texto libre)."""
        if not raw:
            return self._fallback_default(feature, language)

        # Intentar extraer JSON de la respuesta
        json_match = re.search(r"\{[\s\S]*\}", raw)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                if isinstance(parsed, dict) and "code" in parsed:
                    return parsed
            except json.JSONDecodeError:
                pass

        # Fallback: tratar todo el texto como code
        return {
            "module_name": self._slug(feature) + ".py",
            "code": raw,
            "integration_points": [],
            "tests": "",
            "dependencies": [],
        }

    def _fallback_default(self, feature: str, language: str) -> Dict[str, Any]:
        return {
            "module_name": self._slug(feature) + ".py",
            "code": f"# Feature: {feature}\n# Auto-generado (fallback)\n",
            "integration_points": [],
            "tests": "",
            "dependencies": [],
        }

    def _slug(self, name: str) -> str:
        """Convierte un nombre de feature en un slug de modulo."""
        words = re.findall(r"[0-9a-zA-Z_]+", (name or "").lower())
        slug = "_".join(words[:4]) if words else "feature"
        return slug


_generator: Optional[CodeGenerator] = None


def get_code_generator() -> CodeGenerator:
    global _generator
    if _generator is None:
        _generator = CodeGenerator()
    return _generator


def reset_code_generator() -> None:
    global _generator
    _generator = None
