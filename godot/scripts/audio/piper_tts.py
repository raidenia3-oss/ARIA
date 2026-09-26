#!/usr/bin/env python3
"""
Piper TTS local - Genera voz femenina en español sin cloud.

Uso:
    python piper_tts.py "Hola AURA" -o salida.wav
    python piper_tts.py "texto"  # guarda en tts_cache/<hash>.wav
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

CACHE_DIR = Path(os.getenv("AURA_TTS_CACHE", "tts_cache"))
MODEL_NAME = "es_ES-davefx-medium"
DEFAULT_VOICE_URL = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/davefx/medium/"
    "es_ES-davefx-medium.onnx"
)


def _find_piper() -> str | None:
    for cmd in ("piper", "piper.exe"):
        path = shutil.which(cmd)
        if path:
            return path
    return None


def ensure_piper() -> bool:
    return _find_piper() is not None


def ensure_model() -> Path | None:
    model_path = CACHE_DIR / f"{MODEL_NAME}.onnx"
    if model_path.exists():
        return model_path
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Descargando modelo Piper {MODEL_NAME}...", file=sys.stderr)
    try:
        import urllib.request

        urllib.request.urlretrieve(DEFAULT_VOICE_URL, model_path)
        return model_path
    except Exception as exc:
        print(f"[ERROR] No se pudo descargar modelo: {exc}", file=sys.stderr)
        return None


def synthesize(text: str, output: str | None = None) -> str | None:
    if not ensure_piper():
        print("[ERROR] Piper no instalado. `pip install piper-tts`", file=sys.stderr)
        return None

    model = ensure_model()
    if not model:
        return None

    piper = _find_piper()
    if not output:
        cache = CACHE_DIR
        cache.mkdir(parents=True, exist_ok=True)
        h = hashlib.md5(text.encode()).hexdigest()[:12]
        output = str(cache / f"tts_{h}.wav")

    try:
        cmd = [piper, "-m", str(model), "-f", output]
        result = subprocess.run(cmd, input=text.encode(), capture_output=True, timeout=60)
        if result.returncode == 0 and os.path.exists(output):
            return output
        print(f"[ERROR] Piper falló: {result.stderr.decode()}", file=sys.stderr)
    except Exception as exc:
        print(f"[ERROR] Error TTS: {exc}", file=sys.stderr)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Piper TTS local")
    parser.add_argument("text", help="Texto a sintetizar")
    parser.add_argument("-o", "--output", help="Archivo WAV de salida")
    args = parser.parse_args()
    out = synthesize(args.text, args.output)
    if out:
        print(out)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
