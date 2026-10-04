"""Gate C4 — el validador de coherencia distingue "no validado" de "coherente".

`_coherence_check_via_jan` devolvía `{'provider': 'none', 'pass': True}` cuando
jan estaba caído, y `AMESyncEngine.apply_batch` sólo miraba `pass`. Resultado:
un evento JAMÁS validado se trataba como aprobado y el llamador no podía
distinguir "coherente" de "no validado".

El fix correcto fue cambiar el CONTRATO (añadir `validated` explícito) y no
invertir el literal de `pass`, porque `pass: False` haría que un jan caído
rechazara TODOS los eventos.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import backend.sync_engine as sync_engine


@pytest.fixture()
def isolated_state(tmp_path, monkeypatch):
    """Redirige el estado del motor a un tmpdir: no toca data/."""
    monkeypatch.setenv(sync_engine.SYNC_DIR_ENV, str(tmp_path))
    return tmp_path


@pytest.fixture()
def literary_ctx(monkeypatch):
    """Contexto literario activo (work_id presente) sin tocar disco."""
    monkeypatch.setattr(
        "backend.story_memory.session_context.get_session_context",
        lambda sess_id: {"work_id": "obra-x", "character_id": "c1"},
    )


def _chat_event(event_id: str = "e1", text: str = "hola") -> dict:
    return {
        "eventId": event_id,
        "type": "chat_message",
        "createdAt": "2026-01-01T00:00:00Z",
        "payload": {"content": text},
    }


def _patch_verdict(monkeypatch, verdict: dict) -> None:
    monkeypatch.setattr(sync_engine, "_coherence_check_via_jan", lambda *a, **k: dict(verdict))


def test_real_fallback_reports_unvalidated_when_jan_is_down(monkeypatch):
    """El fallback real (router inalcanzable) debe declarar validated=False."""

    class _Boom:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("jan caido")

    monkeypatch.setattr("backend.ai_router.AIRouter", _Boom)
    verdict = sync_engine._coherence_check_via_jan("texto", "obra-x", "c1")
    assert verdict["validated"] is False
    assert verdict["pass"] is None
    assert verdict["provider"] == "none"


def test_unvalidated_event_is_not_rejected_but_counted_separately(
    isolated_state, literary_ctx, monkeypatch
):
    """jan caído NO es "coherente": se cuenta aparte y nunca se rechaza."""
    _patch_verdict(
        monkeypatch,
        {"provider": "none", "validated": False, "pass": None, "note": "jan down"},
    )
    engine = sync_engine.AMESyncEngine()
    result = engine.apply_batch([_chat_event()], device_id="dev1", session_id="s1")
    assert result["coherence_checked"] == 1
    assert result["coherence_unvalidated"] == 1
    assert result["rejected"] == 0


def test_validated_incoherent_event_is_rejected(isolated_state, literary_ctx, monkeypatch):
    _patch_verdict(
        monkeypatch,
        {"provider": "jan", "validated": True, "pass": False, "note": "validated via jan"},
    )
    engine = sync_engine.AMESyncEngine()
    result = engine.apply_batch([_chat_event()], device_id="dev1", session_id="s1")
    assert result["coherence_checked"] == 1
    assert result["coherence_unvalidated"] == 0
    assert result["rejected"] == 1
    assert result["rejected_details"][0]["reason"] == "incoherent"


def test_validated_coherent_event_is_not_rejected(isolated_state, literary_ctx, monkeypatch):
    _patch_verdict(
        monkeypatch,
        {"provider": "jan", "validated": True, "pass": True, "note": "validated via jan"},
    )
    engine = sync_engine.AMESyncEngine()
    result = engine.apply_batch([_chat_event()], device_id="dev1", session_id="s1")
    assert result["coherence_checked"] == 1
    assert result["coherence_unvalidated"] == 0
    assert result["rejected"] == 0
