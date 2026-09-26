from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


@dataclass
class TranscriptionSegment:
    start: float
    end: float
    text: str
    confidence: Optional[float] = None


@dataclass
class TranscriptionResult:
    language: str = ""
    language_probability: float = 0.0
    segments: List[TranscriptionSegment] = field(default_factory=list)
    full_text: str = ""
    duration_seconds: float = 0.0
    source_path: str = ""


class WhisperTranscriber:

    def __init__(self, model_size: str = "base", device: str = "auto") -> None:
        self.model_size = model_size
        self.device = device
        self._model = None
        self._model_loaded = False

    def _load_model(self):
        if self._model_loaded:
            return
        try:
            from faster_whisper import WhisperModel

            device = "cuda" if self.device == "auto" else self.device
            if device == "auto":
                try:
                    import torch

                    device = "cuda" if torch.cuda.is_available() else "cpu"
                except ImportError:
                    device = "cpu"
            compute_type = "float16" if device == "cuda" else "int8"
            self._model = WhisperModel(model_size, device=device, compute_type=compute_type)
            self._model_loaded = True
        except Exception as e:
            raise RuntimeError(f"Error cargando Whisper model: {e}")

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> TranscriptionResult:
        self._load_model()
        try:
            segments, info = self._model.transcribe(
                audio_path,
                beam_size=5,
                language=language,
                condition_on_previous_text=False,
            )
            segment_list = [
                TranscriptionSegment(
                    start=s.start,
                    end=s.end,
                    text=s.text.strip(),
                    confidence=s.probability if hasattr(s, "probability") else None,
                )
                for s in segments
            ]
            return TranscriptionResult(
                language=info.language or "",
                language_probability=info.language_probability or 0.0,
                segments=segment_list,
                full_text=" ".join(s.text.strip() for s in segment_list),
                duration_seconds=sum(s.end - s.start for s in segment_list),
                source_path=audio_path,
            )
        except Exception as e:
            raise RuntimeError(f"Error transcribiendo audio: {e}")

    def transcribe_file(self, audio_path: str, language: Optional[str] = None) -> str:
        result = self.transcribe(audio_path, language=language)
        return result.full_text

    def transcribe_bytes(
        self, audio_bytes: bytes, language: Optional[str] = None
    ) -> TranscriptionResult:
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        try:
            return self.transcribe(tmp_path, language=language)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def get_segment_summary(self, result: TranscriptionResult, max_text_length: int = 300) -> str:
        if not result.segments:
            return ""
        texts = [s.text for s in result.segments]
        full = " ".join(texts)
        if len(full) <= max_text_length:
            return full
        return full[:max_text_length] + "..."
