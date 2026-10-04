# -*- coding: utf-8 -*-
"""Voice-to-agent intent router.

Classifies a voice transcript into a primary agent universe plus optional
supporting agents so the UI can highlight attribution during dispatch.
Uses the LLM adapter registry for classification when available, with a
deterministic keyword fallback that never blocks the pipeline.
"""
from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from backend.agents.universe_registry import Universe, UniverseRegistry

logger = logging.getLogger("AURA.VoiceRouter")


@dataclass
class VoiceIntent:
    """Result of classifying a voice transcript."""

    transcript: str
    primary: Universe = Universe.NEXUS
    supporting: List[Universe] = field(default_factory=list)
    confidence: float = 0.0
    method: str = "keyword"
    routed: Optional[Universe] = None
    blocked: bool = False


# keyword -> universe mapping (deterministic fallback)
#
# Matching is per TOKEN, never `keyword in text`: substring matching routed
# "construir la app" to UIUX because "ui" is inside "construir", and
# "already"/"capital" to KNOWLEDGE/INTEGRATION via "read"/"api". Tokens are
# accent-folded first so "diseñar" matches the ASCII stem "dise".
#
# A keyword shorter than MIN_STEM_LEN only ever matches a whole token, so short
# keywords like "js" or "ui" cannot claim a longer word that happens to start
# with them ("json", "uir").
MIN_STEM_LEN = 4

_KEYWORD_MAP: List[Tuple[List[str], Universe]] = [
    (["compilar", "compila", "construir", "construye", "build", "compile", "test", "tests", "refactor", "revisar", "code", "python", "rust", "js", "typescript", "javascript"], Universe.CODING),
    (["video", "render", "renderizar", "audio", "image", "imagen", "edicion", "editing", "media"], Universe.MEDIA),
    (["investigar", "search", "busca", "buscar", "find", "research", "leer", "read", "summarize", "resumen", "knowledge", "conocimiento"], Universe.KNOWLEDGE),
    (["api", "cloud", "sync", "sincronizar", "webhook", "integration", "integrar", "integracion"], Universe.INTEGRATION),
    (["diseno", "dise", "design", "layout", "theme", "tema", "animation", "animacion", "animar", "ui", "ux"], Universe.UIUX),
    (["admin", "config", "configurar", "permissions", "permisos", "users", "usuario", "audit", "auditar"], Universe.ADMIN),
]


def _fold(token: str) -> str:
    """Lowercase and strip accents so `diseñar` matches the ASCII stem `dise`."""
    decomposed = unicodedata.normalize("NFD", token.lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _token_matches(token: str, keyword: str) -> bool:
    """Whole-token match, or a stem match when the keyword is long enough."""
    if token == keyword:
        return True
    return len(keyword) >= MIN_STEM_LEN and token.startswith(keyword)


def _tokenize(transcript: str) -> set:
    raw = (transcript or "").lower()
    if not raw.strip():
        return set()
    folded = _fold(raw)
    # Keep only alphanumerics so "app." and "build," tokenize cleanly.
    return {t for t in "".join(c if c.isalnum() else " " for c in folded).split() if t}


def _keyword_classify(transcript: str) -> Tuple[Universe, float]:
    """Keyword-based classification. Returns (universe, confidence)."""
    tokens = _tokenize(transcript)
    if not tokens:
        return Universe.NEXUS, 0.0
    best: Optional[Universe] = None
    best_score = 0.0
    for words, universe in _KEYWORD_MAP:
        keywords = [_fold(w) for w in words]
        hits = sum(1 for kw in keywords if any(_token_matches(t, kw) for t in tokens))
        if hits:
            # Denominator is the TRANSCRIPT length, not the size of the keyword
            # list: scoring against list length let a long list dilute a genuine
            # hit ("investigar el tema" scored 1/12 for KNOWLEDGE but 1/11 for
            # UIUX, and "tema" won).
            score = hits / len(tokens)
            if score > best_score:
                best_score = score
                best = universe
    if best is None:
        return Universe.NEXUS, 0.0
    return best, min(1.0, best_score)


class VoiceIntentRouter:
    """Routes voice transcripts to agent universes.

    Prefers the LLM adapter registry for semantic classification; falls back
    to deterministic keyword matching so the pipeline never blocks.
    """

    def __init__(self, registry: Optional[Any] = None) -> None:
        self.registry = registry
        self._universe_registry = UniverseRegistry()

    async def classify(self, transcript: str, source: Universe = Universe.NEXUS) -> VoiceIntent:
        """Classify a transcript into a primary + supporting universes."""
        if not transcript or not transcript.strip():
            return VoiceIntent(transcript=transcript or "", confidence=0.0, method="empty")
        primary, confidence = _keyword_classify(transcript)
        method = "keyword"
        if self.registry is not None:
            try:
                adapter = self.registry.get_adapter("claude") or self.registry.get_adapter("ollama")
                if adapter is not None and hasattr(adapter, "generate_response") and confidence < 0.8:
                    names = [u.value for u in Universe]
                    prompt = (
                        "Classify this voice command into ONE of: "
                        + str(names)
                        + "\n\nTranscript: \"" + transcript + "\"\n\n"
                        + "Return only the universe name, nothing else."
                    )
                    result = await adapter.generate_response(prompt)
                    name = (result.text if hasattr(result, "text") else str(result)).strip().lower()
                    candidate = Universe.from_string(name)
                    if candidate != Universe.NEXUS:
                        primary = candidate
                        confidence = max(confidence, 0.85)
                        method = "llm"
            except Exception as exc:
                logger.debug("llm voice classify failed: %s", exc)
        routed = self._universe_registry.route(source, primary, task=transcript)
        blocked = routed is None
        return VoiceIntent(
            transcript=transcript,
            primary=primary,
            supporting=[],
            confidence=confidence,
            method=method,
            routed=routed,
            blocked=blocked,
        )

    def classify_sync(self, transcript: str, source: Universe = Universe.NEXUS) -> VoiceIntent:
        """Synchronous keyword-only classification (no LLM)."""
        if not transcript or not transcript.strip():
            return VoiceIntent(transcript=transcript or "", confidence=0.0, method="empty")
        primary, confidence = _keyword_classify(transcript)
        routed = self._universe_registry.route(source, primary, task=transcript)
        return VoiceIntent(
            transcript=transcript,
            primary=primary,
            supporting=[],
            confidence=confidence,
            method="keyword",
            routed=routed,
            blocked=routed is None,
        )

    def to_dict(self, intent: VoiceIntent) -> Dict[str, Any]:
        return {
            "transcript": intent.transcript,
            "primary": intent.primary.value,
            "supporting": [u.value for u in intent.supporting],
            "confidence": intent.confidence,
            "method": intent.method,
            "routed": intent.routed.value if intent.routed else None,
            "blocked": intent.blocked,
        }


_router: Optional[VoiceIntentRouter] = None


def get_voice_intent_router() -> VoiceIntentRouter:
    """Singleton accessor."""
    global _router
    if _router is None:
        _router = VoiceIntentRouter()
    return _router


def reset_voice_intent_router() -> None:
    """Drop the singleton (used in tests)."""
    global _router
    _router = None