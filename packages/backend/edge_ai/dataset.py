"""BLOQUE 86 - Edge-AI local dataset formatter & synthesizer (100% local/offline).

Convierte experiencias/interacciones/RAG locales en datasets JSONL limpios
y privados. Sin red, sin telemetria, sin dependencias cloud.
"""
from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List

_WS = re.compile(r"\s+")
MAX_TEXT = 2000


def _clean(text: str) -> str:
    t = _WS.sub(" ", str(text or "")).strip()
    return t[:MAX_TEXT]


@dataclass
class TrainingExample:
    example_id: str = ""
    instruction: str = ""
    input: str = ""
    output: str = ""
    source: str = "interaction"
    score: float = 1.0
    ts: float = 0.0

    def __post_init__(self) -> None:
        if not self.example_id:
            self.example_id = uuid.uuid4().hex[:12]
        if not self.ts:
            self.ts = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "example_id": self.example_id,
            "instruction": self.instruction,
            "input": self.input,
            "output": self.output,
            "source": self.source,
            "score": self.score,
            "ts": self.ts,
        }

    def to_jsonl(self) -> str:
        import json

        return json.dumps(self.to_dict(), ensure_ascii=False)


class DatasetFormatter:
    """Estructura datasets locales desde experiencias exitosas/RAG/feedback."""

    VALID_SOURCES = ("interaction", "rag", "feedback", "manual")

    def build_example(
        self,
        instruction: str,
        output: str,
        source: str = "interaction",
        input: str = "",  # noqa: A002 - formato de dataset
        score: float = 1.0,
    ) -> TrainingExample:
        if source not in self.VALID_SOURCES:
            raise ValueError(f"source no soportada: {source}")
        ins, out = _clean(instruction), _clean(output)
        if not ins or not out:
            raise ValueError("instruction/output vacios tras limpieza")
        return TrainingExample(
            instruction=ins, input=_clean(input), output=out,
            source=source, score=max(0.0, min(1.0, float(score))),
        )

    def synthesize(
        self, records: List[Dict[str, Any]], min_score: float = 0.5
    ) -> List[TrainingExample]:
        out: List[TrainingExample] = []
        for r in records or []:
            try:
                if float(r.get("score", 1.0)) < min_score:
                    continue
                out.append(
                    self.build_example(
                        str(r.get("instruction", "")),
                        str(r.get("output", "")),
                        str(r.get("source", "interaction")),
                        str(r.get("input", "")),
                        float(r.get("score", 1.0)),
                    )
                )
            except (ValueError, TypeError):
                continue
        return out

    def to_jsonl(self, examples: List[TrainingExample]) -> str:
        return "\n".join(e.to_jsonl() for e in examples)


__all__ = ["TrainingExample", "DatasetFormatter"]
