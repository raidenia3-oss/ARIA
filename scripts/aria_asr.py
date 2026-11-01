"""Transcripción de audio con faster-whisper para el canal de voz de ARIA.

Uso:
    .venv\\Scripts\\python.exe scripts\\aria_asr.py <archivo> [--language es] [--model base]

Imprime UNA línea JSON por stdout:
    {"text": "...", "language": "es", "duration": 1.84, "engine": "faster-whisper/base"}

El backend Rust (v6/axum-poc/src/voice.rs) lo invoca como hijo y lee esa
línea. Si algo falla, la línea de error va a stderr y el proceso sale con
código 1: el backend distingue "no hubo transcripción" de "el motor falló"
por el código de salida, no por adivinar.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ARIA ASR (faster-whisper)")
    parser.add_argument("audio", help="archivo de audio a transcribir")
    parser.add_argument("--language", default="es", help="código ISO del idioma")
    parser.add_argument("--model", default="base", help="tamaño del modelo whisper")
    parser.add_argument(
        "--beams",
        type=int,
        default=1,
        help="beam size de la decodificación (1 = greedy, más rápido)",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    audio = Path(args.audio)
    if not audio.is_file():
        print(f"audio no encontrado: {audio}", file=sys.stderr)
        return 2

    try:
        from faster_whisper import WhisperModel
    except Exception as exc:  # pragma: no cover - depende del entorno
        print(f"faster-whisper no disponible: {exc}", file=sys.stderr)
        return 3

    # compute_type=int8 mantiene el modelo dentro de la RAM de un portátil;
    # cpu evita depender de una GPU que puede estar ocupada con el orb 3D.
    try:
        model = WhisperModel(
            args.model,
            device=os.environ.get("ARIA_ASR_DEVICE", "cpu"),
            compute_type=os.environ.get("ARIA_ASR_COMPUTE", "int8"),
        )
    except Exception as exc:
        print(f"no se pudo cargar el modelo '{args.model}': {exc}", file=sys.stderr)
        return 4

    try:
        segments, info = model.transcribe(
            str(audio),
            language=args.language,
            beam_size=args.beams,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 400},
        )
        text = "".join(segment.text for segment in segments).strip()
        detected = getattr(info, "language", args.language) or args.language
    except Exception as exc:
        print(f"fallo la transcripción: {exc}", file=sys.stderr)
        return 5

    payload = {
        "text": text,
        "language": detected,
        "duration": round(float(getattr(info, "duration", 0.0) or 0.0), 3),
        "engine": f"faster-whisper/{args.model}",
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
