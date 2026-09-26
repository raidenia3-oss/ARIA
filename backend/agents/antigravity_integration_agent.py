# -*- coding: utf-8 -*-
"""AURA OS - Antigravity Integration Agent."""
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from typing import Any, Dict, Optional

logger = logging.getLogger("AURA.AntigravityIntegration")

ANTIGRAVITY_PATH = os.getenv(
    "ANTIGRAVITY_PATH",
    r"C:\Users\User\AppData\Local\Programs\Antigravity IDE\antigravity.exe",
)
JAN_URL = os.getenv("JAN_URL", "http://localhost:1337/v1")


async def _call_jan(task: str, context: str = "") -> Optional[str]:
    """Pide a Jan que escriba/corrija codigo."""
    try:
        import urllib.request
        import json

        system = "Eres un desarrollador senior. Escribe codigo Python limpio, eficiente y con manejo de errores."
        if context:
            system += f"\nContexto: {context}"

        body = json.dumps({
            "model": "gemma-3-1b-it",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": task},
            ],
            "temperature": 0.3,
            "max_tokens": 2048,
            "stream": False,
        }).encode()

        req = urllib.request.Request(
            f"{JAN_URL}/chat/completions",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            result = json.loads(r.read())
        return ((result.get("choices") or [{}])[0].get("message") or {}).get("content", "")
    except Exception as exc:
        logger.warning("[ANTIGRAVITY] Jan error: %s", exc)
        return None


async def open_antigravity_IDE(project_name: str = "aura_project") -> str:
    """Abre Antigravity IDE y crea un proyecto nuevo."""
    project_path = os.path.join(os.getcwd(), project_name)
    os.makedirs(project_path, exist_ok=True)

    try:
        if os.path.exists(ANTIGRAVITY_PATH):
            subprocess.Popen([ANTIGRAVITY_PATH, project_path])
            logger.info("[ANTIGRAVITY] IDE abierto en %s", project_path)
        else:
            logger.warning("[ANTIGRAVITY] No instalado en %s", ANTIGRAVITY_PATH)
    except Exception as exc:
        logger.error("[ANTIGRAVITY] Error abriendo IDE: %s", exc)

    return project_path


async def write_and_test_code(task: str) -> Dict[str, Any]:
    """Escribe codigo con Jan, lo prueba en Antigravity."""
    code = await _call_jan(
        f"Escribe codigo Python para: {task}. Incluye manejo de errores y print de resultado.",
    )

    if not code:
        return {"success": False, "error": "Jan no pudo generar codigo", "code": ""}

    code = _extract_code(code)

    test_file = os.path.join(os.getcwd(), "test_generated.py")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write(code)

    output = ""
    try:
        result = subprocess.run(
            ["python", test_file],
            capture_output=True, text=True, timeout=30,
        )
        output = result.stdout + result.stderr
        success = result.returncode == 0
    except Exception as exc:
        output = str(exc)
        success = False

    if not success:
        fixed = await _call_jan(
            f"Corrige este codigo Python que fallo:\n{code}\n\nError:\n{output}",
        )
        if fixed:
            code = _extract_code(fixed)
            with open(test_file, "w", encoding="utf-8") as f:
                f.write(code)
            result = subprocess.run(
                ["python", test_file],
                capture_output=True, text=True, timeout=30,
            )
            output = result.stdout + result.stderr
            success = result.returncode == 0

    logger.info("[ANTIGRAVITY] Code test: success=%s, output=%s", success, output[:200])
    return {
        "success": success,
        "code": code,
        "output": output,
        "test_file": test_file,
    }


def _extract_code(text: str) -> str:
    """Extrae el bloque de codigo de la respuesta de Jan."""
    if "```python" in text:
        start = text.find("```python") + 9
        end = text.find("```", start)
        if end > start:
            return text[start:end].strip()
    if "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        if end > start:
            return text[start:end].strip()
    return text


async def improve_existing_code(file_path: str) -> Dict[str, Any]:
    """Mejora un archivo de codigo existiente usando Jan + Antigravity."""
    if not os.path.exists(file_path):
        return {"success": False, "error": "Archivo no encontrado", "file": file_path}

    with open(file_path, "r", encoding="utf-8") as f:
        original = f.read()

    improved = await _call_jan(
        f"Mejora este codigo Python (performance, legabilidad, manejo de errores, type hints):\n{original[:3000]}",
        system="Eres un senior developer. Mantienes la funcionalidad pero mejoras el codigo.",
    )

    if not improved:
        return {"success": False, "error": "Jan no pudo mejorar", "file": file_path}

    improved = _extract_code(improved)

    test_result = await write_and_test_code(f"Valida que este sintaxis Python es correcta:\n{improved[:500]}")

    if test_result["success"]:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(improved)
        logger.info("[ANTIGRAVITY] Code improved in %s", file_path)
        return {
            "success": True,
            "file": file_path,
            "original_lines": len(original.splitlines()),
            "improved_lines": len(improved.splitlines()),
        }

    return {"success": False, "error": "El mejorado codigo falla al testear", "file": file_path}


class AntigravityIntegrationAgent:
    """Agente de integracion con Antigravity IDE."""

    async def improve_codebase(self) -> Dict[str, Any]:
        """Mejora automaticamente los archivos principales del proyecto."""
        files_to_improve = [
            "backend/main.py",
            "backend/daemon/aura_daemon.py",
            "backend/integrations/ame_sync_manager.py",
        ]

        results = {}
        for fp in files_to_improve:
            if os.path.exists(fp):
                result = await improve_existing_code(fp)
                results[fp] = result
                await asyncio.sleep(1)

        return {
            "files_processed": len(results),
            "results": results,
        }
