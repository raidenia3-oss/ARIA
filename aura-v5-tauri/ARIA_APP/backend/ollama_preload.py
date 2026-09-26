"""Ollama model preloader — keeps model in memory for fast inference."""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.request

MODEL = os.environ.get("LOCAL_LFM_MODEL", "dolphin-2_6-phi-2:latest")
BASE_URL = os.environ.get("LOCAL_LFM_BASE_URL", "http://localhost:11434")
KEEP_ALIVE_MINUTES = 30


def preload_model() -> dict:
    data = json.dumps({"model": MODEL, "prompt": "[PRELOAD]", "stream": False}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except Exception as exc:
        return {"error": str(exc)}


def set_keep_alive() -> None:
    os.environ["OLLAMA_KEEP_ALIVE"] = str(KEEP_ALIVE_MINUTES)
    print(f"[Ollama] OLLAMA_KEEP_ALIVE set to {KEEP_ALIVE_MINUTES} min")


def chat_warmup() -> dict:
    messages = [
        {"role": "system", "content": "Eres un asistente útil."},
        {"role": "user", "content": "Hola, responde solo OK"},
    ]
    data = json.dumps({"model": MODEL, "messages": messages, "stream": False}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except Exception as exc:
        return {"error": str(exc)}


def run_preload_loop(interval_sec: int = 600) -> None:
    set_keep_alive()
    print(f"[Ollama] Preloading model {MODEL}...")
    result = preload_model()
    print(f"[Ollama] Preload result: {result}")
    print(f"[Ollama] Chat warmup...")
    result2 = chat_warmup()
    print(f"[Ollama] Warmup result: {result2}")
    while True:
        time.sleep(interval_sec)
        print(f"[Ollama] Re-keeping model alive ({KEEP_ALIVE_MINUTES} min)...")
        try:
            data = json.dumps({"model": MODEL, "prompt": "[KEEP_ALIVE]", "stream": False}).encode()
            req = urllib.request.Request(
                f"{BASE_URL}/api/generate",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as r:
                result = json.loads(r.read())
            print(f"[Ollama] Keep-alive OK: {result.get('response', '')[:50]}")
        except Exception as exc:
            print(f"[Ollama] Keep-alive failed: {exc}")


if __name__ == "__main__":
    run_preload_loop()
