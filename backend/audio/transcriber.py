"""AURA Local Audio STT — transcripción de voz 100% local (Bloque 37).

Motor de transcripción basado en Faster-Whisper (CPU, int8) que procesa las
notas de voz enviadas por el bot de Discord o el cliente móvil AME sin enviar
audio a APIs de terceros en la nube.

Diseño:
- Carga perezosa (lazy) del modelo: la primera transcripción inicializa
  ``faster_whisper.WhisperModel`` (AURA_WHISPER_MODEL, default "base";
  idioma AURA_WHISPER_LANG, default "es").
- Directorio temporal de procesamiento (AURA_AUDIO_TMP_DIR, default
  ``./data/tmp_audio``) con limpieza automática de ficheros antiguos.
- La inferencia corre en un hilo (``asyncio.to_thread``) para no bloquear
  el event loop de FastAPI.
- Formatos aceptados: .ogg, .oga, .wav, .mp3, .m4a, .webm, .flac.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURA.Audio.STT")

SUPPORTED_EXTENSIONS = {".ogg", ".oga", ".wav", ".mp3", ".m4a", ".webm", ".flac"}
_DEFAULT_TMP_DIR = os.path.join("data", "tmp_audio")
_TMP_MAX_AGE_SECS = 3600  # 1 hora


class UnsupportedAudioFormat(ValueError):
    """El formato de audio no está entre los soportados."""


def _env(key: str, default: str) -> str:
    return os.getenv(key, default)


class LocalWhisperTranscriber:
    """Motor STT local (Faster-Whisper) con tmp dir y limpieza automática."""

    def __init__(
        self,
        model_size: Optional[str] = None,
        language: Optional[str] = None,
        tmp_dir: Optional[str] = None,
        engine: Optional[str] = None,
    ) -> None:
        self.model_size = model_size or _env("AURA_WHISPER_MODEL", "base")
        self.language = language or _env("AURA_WHISPER_LANG", "es")
        self.tmp_dir = Path(tmp_dir or _env("AURA_AUDIO_TMP_DIR", _DEFAULT_TMP_DIR))
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self._model: Any = None
        # Motor seleccionado vía entorno: "auto" (real si está disponible,
        # si no 503), "stub" (transcripción simulada para tests/demo sin torch).
        self.engine = (engine or _env("AURA_WHISPER_ENGINE", "auto")).lower()

    @property
    def engine_available(self) -> bool:
        """True si faster-whisper + torch pueden cargar el modelo para inferencia real."""
        if self.engine == "stub":
            return False
        try:
            from faster_whisper import WhisperModel  # noqa: F401
            import torch  # noqa: F401
            return True
        except Exception:  # noqa: BLE001
            return False

    @property
    def available(self) -> bool:
        """True si hay un motor usable (real o stub)."""
        return self.engine_available or self.engine == "stub"

    @property
    def engine_name(self) -> str:
        """Nombre del motor efectivamente en uso."""
        if self.engine == "stub":
            return "stub"
        return "faster-whisper" if self.engine_available else "unavailable"

    def _load_model(self) -> Any:
        """Carga perezosa del modelo Whisper."""
        if self._model is not None:
            return self._model
        from faster_whisper import WhisperModel

        logger.info("Cargando modelo Whisper '%s' (cpu/int8)...", self.model_size)
        self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
        return self._model

    def _safe_name(self, filename: str) -> str:
        base = os.path.basename(filename or "audio.ogg")
        stem = re.sub(r"[^A-Za-z0-9._-]", "_", base)
        return f"{int(time.time() * 1000)}_{stem}"

    def save_upload(self, filename: str, data: bytes) -> Path:
        """Valida la extensión y guarda el upload en el tmp dir."""
        ext = os.path.splitext(filename or "")[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise UnsupportedAudioFormat(
                f"formato '{ext or 'desconocido'}' no soportado; use {sorted(SUPPORTED_EXTENSIONS)}"
            )
        path = self.tmp_dir / self._safe_name(filename)
        path.write_bytes(data)
        return path

    def cleanup(self, max_age_secs: int = _TMP_MAX_AGE_SECS) -> int:
        """Borra ficheros temporales más antiguos que max_age_secs."""
        removed = 0
        now = time.time()
        for p in self.tmp_dir.glob("*"):
            try:
                if p.is_file() and now - p.stat().st_mtime > max_age_secs:
                    p.unlink()
                    removed += 1
            except OSError as exc:
                logger.debug("cleanup skip %s: %s", p, exc)
        return removed

    # -- inferencia -----------------------------------------------------------------

    def _transcribe_stub(self, path: Path) -> Dict[str, Any]:
        """Motor de reserva (stub): transcripción simulada cuando no hay modelo real.

        Útil para tests, demo local y entornos sin torch/model. Nunca envía
        datos a la nube: la salida es determinista a partir del propio audio.
        """
        import hashlib

        data = Path(path).read_bytes()
        digest = hashlib.sha1(data).hexdigest()[:12]
        size = len(data)
        logger.info("STT stub (sin modelo Whisper) para %s (%d bytes)", path.name, size)
        return {
            "text": (
                "[STT local stub] notas de voz procesadas 100% en local. "
                f"sha1={digest} size={size}B — engine más whisper no disponible."
            ),
            "language": self.language,
            "duration": round(size / 32000.0, 3),
            "model": self.model_size,
            "engine": "stub",
        }

    def transcribe_file(self, path: Path, beam_size: int = 5) -> Dict[str, Any]:
        """Transcribe un fichero de audio localmente (bloqueante; llamar en hilo)."""
        if not Path(path).exists():
            raise FileNotFoundError(f"audio no encontrado: {path}")
        if not self.engine_available:
            return self._transcribe_stub(path)
        model = self._load_model()
        segments, info = model.transcribe(
            str(path),
            language=self.language or None,
            beam_size=beam_size,
        )
        text_parts: List[str] = []
        for seg in segments:
            piece = (getattr(seg, "text", "") or "").strip()
            if piece:
                text_parts.append(piece)
        return {
            "text": " ".join(text_parts).strip(),
            "language": getattr(info, "language", None) or self.language,
            "duration": round(float(getattr(info, "duration", 0.0) or 0.0), 2),
            "model": self.model_size,
            "engine": "faster-whisper",
        }

    async def transcribe_bytes(self, filename: str, data: bytes) -> Dict[str, Any]:
        """Pipeline completo: validar → tmp → inferir (en hilo) → limpiar tmp.

        No bloquea el event loop: la inferencia corre vía asyncio.to_thread.
        """
        path = self.save_upload(filename, data)
        try:
            return await asyncio.to_thread(self.transcribe_file, path)
        finally:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    def status(self) -> Dict[str, Any]:
        """Estado del motor sin exponer rutas internas sensibles."""
        return {
            "status": "ok",
            "engine": self.engine_name,
            "engine_requested": self.engine,
            "available": self.available,
            "real_available": self.engine_available,
            "model": self.model_size,
            "language": self.language,
            "supported_extensions": sorted(SUPPORTED_EXTENSIONS),
        }


_transcriber: Optional[LocalWhisperTranscriber] = None


def get_transcriber() -> LocalWhisperTranscriber:
    """Singleton del transcriptor local."""
    global _transcriber
    if _transcriber is None:
        _transcriber = LocalWhisperTranscriber()
    return _transcriber


def reset_transcriber() -> None:
    """Reinicia el singleton (testing)."""
    global _transcriber
    _transcriber = None