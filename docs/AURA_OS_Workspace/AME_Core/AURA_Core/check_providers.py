#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnóstico de proveedores de IA configurados en .env.

Uso:
    python AURA_Core/check_providers.py

Muestra un reporte en terminal con el estado de cada proveedor activo.
"""

import os
import time
import requests
import json
from typing import Tuple


def _timed_request(func):
    """Decorator: devuelve (ok, detalle, ms) y captura excepciones."""

    def wrapper(*args, **kwargs) -> Tuple[bool, str, float]:
        start = time.time()
        try:
            ok, detail = func(*args, **kwargs)
        except Exception as exc:  # pragma: no cover
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        elapsed = (time.time() - start) * 1000
        return ok, detail, elapsed

    return wrapper


@_timed_request
def test_gemini(api_key: str) -> Tuple[bool, str]:
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent"
    payload = {"contents": [{"role": "user", "parts": [{"text": "ping"}]}]}
    params = {"key": api_key}
    r = requests.post(url, params=params, json=payload, timeout=15)
    if r.status_code == 200:
        return True, "Modelo: gemini-2.0-flash-exp"
    return False, f"{r.status_code} {r.text[:120]}"  # pragma: no cover


@_timed_request
def test_nvidia(api_key: str) -> Tuple[bool, str]:
    url = "https://api.nvcf.nvidia.com/v2/nvcf/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code == 200:
        return True, "Acceso a catálogo de modelos"
    return False, f"{r.status_code} {r.text[:120]}"  # pragma: no cover


@_timed_request
def test_groq(api_key: str) -> Tuple[bool, str]:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "mixtral-8x7b-32768",
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
    }
    r = requests.post(url, headers=headers, json=payload, timeout=15)
    if r.status_code == 200:
        return True, "Modelo: mixtral-8x7b-32768"
    return False, f"{r.status_code} {r.text[:120]}"  # pragma: no cover


@_timed_request
def test_hf(api_key: str) -> Tuple[bool, str]:
    url = "https://api.huggingface.co/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code == 200:
        return True, "Acceso a HuggingFace API"
    return False, f"{r.status_code} {r.text[:120]}"  # pragma: no cover


@_timed_request
def test_openrouter(api_key: str) -> Tuple[bool, str]:
    url = "https://openrouter.ai/api/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code == 200:
        return True, "Acceso a OpenRouter API"
    return False, f"{r.status_code} {r.text[:120]}"  # pragma: no cover


@_timed_request
def test_lm_studio(base_url: str) -> Tuple[bool, str]:
    url = f"{base_url.rstrip('/')}/models"
    r = requests.get(url, timeout=15)
    if r.status_code == 200:
        return True, "LM Studio reachable"
    return False, f"{r.status_code} {r.text[:120]}"  # pragma: no cover


def main() -> None:
    # Cargar variables de entorno desde .env
    from dotenv import load_dotenv

    load_dotenv()

    providers = {
        "GEMINI": (os.getenv("GEMINI_API_KEY"), test_gemini),
        "NVIDIA": (os.getenv("NVIDIA_NIM_API_KEY"), test_nvidia),
        "GROQ": (os.getenv("GROQ_API_KEY"), test_groq),
        "HF": (os.getenv("HF_TOKEN"), test_hf),
        "OPENROUTER": (os.getenv("OPENROUTER_API_KEY"), test_openrouter),
        "LM_STUDIO": (os.getenv("LM_STUDIO_BASE_URL"), test_lm_studio),
    }

    report = []
    report.append("=== AURA Provider Diagnostic ===")
    for name, (cred, tester) in providers.items():
        if not cred:
            line = f"[{name}] SKIP - Credencial no configurada"
        else:
            ok, detail, ms = tester(cred)
            icon = "OK" if ok else "ERROR"
            line = f"[{name}] {icon} ({ms:.0f}ms) - {detail}"
        report.append(line)

    print("\n".join(report))
    print("\nDiagnóstico completado.")


if __name__ == "__main__":
    main()
