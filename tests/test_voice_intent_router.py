# -*- coding: utf-8 -*-
"""Tests for the Voice-to-Agent intent router."""
from __future__ import annotations

import pytest

from backend.agents.universe_registry import Universe
from backend.agents.voice_intent_router import (
    VoiceIntentRouter,
    get_voice_intent_router,
    reset_voice_intent_router,
)


@pytest.fixture(autouse=True)
def reset_router():
    reset_voice_intent_router()
    yield
    reset_voice_intent_router()


def test_singleton():
    a = get_voice_intent_router()
    b = get_voice_intent_router()
    assert a is b


def test_classify_coding():
    r = VoiceIntentRouter()
    intent = r.classify_sync("compilar el proyecto y correr tests")
    assert intent.primary == Universe.CODING
    assert intent.routed == Universe.CODING
    assert intent.blocked is False
    assert intent.confidence > 0


def test_classify_media():
    r = VoiceIntentRouter()
    intent = r.classify_sync("renderizar el video")
    assert intent.primary == Universe.MEDIA
    assert intent.routed == Universe.MEDIA


def test_classify_knowledge():
    r = VoiceIntentRouter()
    intent = r.classify_sync("investigar sobre machine learning")
    assert intent.primary == Universe.KNOWLEDGE


def test_classify_admin():
    r = VoiceIntentRouter()
    intent = r.classify_sync("configurar permisos de usuario")
    assert intent.primary == Universe.ADMIN


def test_classify_empty():
    r = VoiceIntentRouter()
    intent = r.classify_sync("")
    assert intent.primary == Universe.NEXUS
    assert intent.confidence == 0.0
    assert intent.method == "empty"


def test_classify_to_dict():
    r = VoiceIntentRouter()
    intent = r.classify_sync("compilar tests")
    d = r.to_dict(intent)
    assert d["primary"] == "coding"
    assert d["method"] == "keyword"
    assert d["blocked"] is False


def test_cross_universe_route_blocked():
    """Direct A->B (non-NEXUS source) is blocked by the universe registry."""
    r = VoiceIntentRouter()
    intent = r.classify_sync("compilar tests", source=Universe.ADMIN)
    assert intent.blocked is True
    assert intent.routed is None


@pytest.mark.asyncio
async def test_classify_async_keyword_path():
    """Async classify falls back to keyword when no registry is set."""
    r = VoiceIntentRouter()
    intent = await r.classify("renderizar video")
    assert intent.primary == Universe.MEDIA
    assert intent.method in ("keyword", "llm")


@pytest.mark.parametrize(
    "transcript,expected",
    [
        # Regresión: el matching era `keyword in text`, así que "ui" (UIUX)
        # entraba dentro de "construir" y una petición de build acababa en el
        # universo de diseño. Ahora se compara token a token.
        ("construir la app", Universe.CODING),
        # "ui"/"js" son demasiado cortos para prefijo: no reclaman palabras
        # largas que sólo empiezan por ellos.
        ("un json pequeno", Universe.NEXUS),
        ("already done", Universe.NEXUS),
        ("la capital de francia", Universe.NEXUS),
    ],
)
def test_substring_matches_do_not_trigger_a_universe(transcript, expected):
    r = VoiceIntentRouter()
    assert r.classify_sync(transcript).primary == expected


def test_accented_stem_still_matches():
    """El folding de acentos debe mantener `diseñar` -> UIUX."""
    r = VoiceIntentRouter()
    assert r.classify_sync("diseñar la interfaz").primary == Universe.UIUX


def test_keyword_lists_have_no_duplicates():
    """Las listas duplicadas inflaban el denominador y hundían la confianza."""
    from backend.agents.voice_intent_router import _KEYWORD_MAP

    for words, _universe in _KEYWORD_MAP:
        assert len(words) == len(set(words)), f"keywords duplicadas: {words}"