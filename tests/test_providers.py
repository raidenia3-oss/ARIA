#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Validador de proveedores IA para AURA (Fase 1).
Lee .env, prueba cada provider con credenciales y muestra reporte.
"""

import json
import os
import sys
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - fallback
    load_dotenv = None

try:
    import requests
except ImportError:  # pragma: no cover
    print("Falta dependencia: requests")
    sys.exit(1)


# ---------- helpers ----------
def _load_env() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if load_dotenv:
        load_dotenv(env_path)
        return
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())


def _timed(fn, *args, **kwargs):
    t0 = time.time()
    try:
        ok, detail = fn(*args, **kwargs)
    except Exception as e:
        ok = False
        detail = f"{type(e).__name__}: {e}"
    return ok, detail, (time.time() - t0) * 1000


# ---------- pruebas por provider ----------
def _test_nvidia(api_key: str):
    url = "https://api.nvcf.nvidia.com/v2/nvcf/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code == 200:
        return True, "Acceso a catálogo NVIDIA"
    return False, f"{r.status_code} {r.text[:120]}"


def _test_groq(api_key: str):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "llama3-8b-8192",
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
    }
    r = requests.post(url, headers=headers, json=payload, timeout=15)
    if r.status_code == 200:
        return True, "Modelo: llama3-8b-8192"
    return False, f"{r.status_code} {r.text[:120]}"


def _test_openrouter(api_key: str):
    url = "https://openrouter.ai/api/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code == 200:
        return True, "Acceso a OpenRouter"
    return False, f"{r.status_code} {r.text[:120]}"


def _test_hf(api_key: str):
    url = "https://api.huggingface.co/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code == 200:
        return True, "Acceso a HuggingFace"
    return False, f"{r.status_code} {r.text[:120]}"


def _test_gemini(api_key: str):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent"
    params = {"key": api_key}
    payload = {"contents": [{"role": "user", "parts": [{"text": "ping"}]}]}
    r = requests.post(url, params=params, json=payload, timeout=15)
    if r.status_code == 200:
        return True, "Modelo: gemini-2.0-flash-exp"
    return False, f"{r.status_code} {r.text[:120]}"


def _test_lm_studio(base_url: str):
    url = f"{base_url.rstrip('/')}/models"
    r = requests.get(url, timeout=15)
    if r.status_code == 200:
        return True, "LM Studio reachable"
    return False, f"{r.status_code} {r.text[:120]}"


# ---------- orquestación ----------
def main() -> None:
    _load_env()

    providers = {
        "NVIDIA": (os.getenv("NVIDIA_NIM_API_KEY"), _test_nvidia),
        "GROQ": (os.getenv("GROQ_API_KEY"), _test_groq),
        "OPENROUTER": (os.getenv("OPENROUTER_API_KEY"), _test_openrouter),
        "HUGGINGFACE": (os.getenv("HF_TOKEN"), _test_hf),
        "GEMINI": (os.getenv("GEMINI_API_KEY"), _test_gemini),
        "LM_STUDIO": (os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1"), _test_lm_studio),
    }

    lines = []
    lines.append("=== AURA Provider Diagnostic ===")
    for name, (cred, tester) in providers.items():
        if not cred:
            lines.append(f"[{name}] SKIP - Credencial no configurada")
            continue
        ok, detail, ms = _timed(tester, cred)
        if ok:
            lines.append(f"[{name}] OK ({ms:.0f}ms) - {detail}")
        else:
            lines.append(f"[{name}] ERROR ({ms:.0f}ms) - {detail}")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
