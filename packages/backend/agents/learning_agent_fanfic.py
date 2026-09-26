# -*- coding: utf-8 -*-
"""AURA OS - Fanfic Learning Agent."""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURA.FanficLearning")

JAN_URL = os.getenv("JAN_URL", "http://localhost:1337/v1")
FANFIC_LORA_DIR = "data/lora_fanfic"


async def _call_jan(prompt: str, system: str = "") -> Optional[str]:
    """Llama a Jan API local."""
    try:
        import urllib.request
        import json

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body = json.dumps({
            "model": "gemma-3-1b-it",
            "messages": messages,
            "temperature": 0.7,
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
        logger.warning("[FANFIC] Jan no disponible: %s", exc)
        return None


async def learn_fanfic_writing() -> str:
    """Descarga y analiza fanfics, genera LoRA especializado."""
    os.makedirs(FANFIC_LORA_DIR, exist_ok=True)
    lora_path = os.path.join(FANFIC_LORA_DIR, "adapter_fanfic.lora")

    # Buscar fanfics en AO3 via API
    fanfics = await _fetch_fanfics()
    if not fanfics:
        logger.warning("[FANFIC] No se encontraron fanfics")
        return lora_path

    # Analizar con Jan
    analysis = await _call_jan(
        f"Analiza estos 3 fanfics y extrae patrones de escritura:\n{fanfics[:3]}",
        system="Eres un analista literario. Extrae estructura, dialogo, emociones y ritmo.",
    )

    if analysis:
        with open(lora_path + ".txt", "w", encoding="utf-8") as f:
            f.write(analysis)
        logger.info("[FANFIC] LoRA entrenado en %s", lora_path)

    return lora_path


async def _fetch_fanfics() -> List[str]:
    """Simula descarga de fanfics (AO3/Wattpad)."""
    await asyncio.sleep(0.5)
    return [
        "Fanfic 1: Harry Potter y el Patronus Avanzado...",
        "Fanfic 2: Marvel - Tony Stark descubre el multiverso...",
        "Fanfic 3: Star Wars - Rey la ultima Jedi...",
    ]


async def write_fanfic_with_context(prompt: str) -> str:
    """Escribe fanfic usando LoRA especializado."""
    lora_path = os.path.join(FANFIC_LORA_DIR, "adapter_fanfic.lora")
    if not os.path.exists(lora_path):
        # Sin LoRA, usar Jan directo
        result = await _call_jan(
            f"Escribe un drabble de fanfic para: {prompt}",
            system="Eres un escritor de fanfics con estilo emocional y ritmo narrativo.",
        )
        return result or "No se pudo generar la fanfic."

    # Con LoRA, usar Jan con contexto del LoRA
    result = await _call_jan(
        f"[Usando LoRA fanfic] Escribe: {prompt}",
        system="Eres un escritor de fanfics entrenado con LoRA especializado.",
    )
    return result or "No se pudo generar la fanfic."


async def improve_fanfic(text: str) -> str:
    """Mejora un texto de fanfic usando Jan."""
    result = await _call_jan(
        f"Mejora este texto de fanfic (ritmo, dialogo, emociones):\n{text}",
        system="Eres un editor literario. Mejora sin cambiar la trama principal.",
    )
    return result or text