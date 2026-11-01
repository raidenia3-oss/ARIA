"""La voz de ARIA: local primero, y sin despertarse por cualquier cosa.

Dos cosas se comprueban aquí:

1. La transcripción sale del motor local (Whisper, luego Vosk). Google es una
   capacidad de red, no un requisito: sin permiso explícito no se llama, y
   aunque se llame, el motor local manda.
2. La llamada a ARIA se reconoce bien: con comas ("hey, aria, abre la luz"),
   sin despertar por palabras parecidas ("arial") y sin perder la orden que
   viene detrás de la llamada.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _path in (str(ROOT), str(ROOT / "ARIA_APP")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from aria_va_core import LocalVoice  # noqa: E402


class FakeRecognizer:
    """Reconocedor de mentira: cuenta a quien se le llama."""

    def __init__(self) -> None:
        self.google: list = []
        self.whisper: list = []

    def recognize_google(self, audio, language=None):
        self.google.append(language)
        return "esto es de google"

    def recognize_whisper(self, audio, language=None):
        self.whisper.append(language)
        return "esto es local"


def test_google_no_se_llama_sin_permiso(monkeypatch):
    monkeypatch.delenv("ARIA_STT_GOOGLE", raising=False)
    voice = LocalVoice()
    voice._local_engine = ""
    voice._allow_google = False
    recognizer = FakeRecognizer()

    texto = voice._transcribe(recognizer, object())

    assert texto == ""
    assert recognizer.google == []


def test_el_motor_local_manda_sobre_google(monkeypatch):
    monkeypatch.setenv("ARIA_STT_GOOGLE", "1")
    voice = LocalVoice()
    voice._local_engine = "whisper"
    voice._allow_google = True
    recognizer = FakeRecognizer()

    texto = voice._transcribe(recognizer, object())

    assert texto == "esto es local"
    assert recognizer.google == []


def test_google_solo_si_no_hay_motor_local(monkeypatch):
    monkeypatch.setenv("ARIA_STT_GOOGLE", "1")
    voice = LocalVoice()
    voice._local_engine = ""
    voice._allow_google = True
    recognizer = FakeRecognizer()

    texto = voice._transcribe(recognizer, object())

    assert texto == "esto es de google"
    assert recognizer.google == ["es-ES"]


def test_la_voz_no_es_una_dependencia():
    """Sin motor de voz, ARIA sigue existiendo: la voz es un extra."""
    voice = LocalVoice()

    caps = voice.capabilities()

    assert caps["local_only"] is True
    assert "stt" in caps and "tts" in caps


@pytest.mark.parametrize(
    "texto",
    [
        "hey aria",
        "Hey, aria, abre la luz",
        "hola aria como estas",
        "oye aria que tal",
        "aria",
    ],
)
def test_aria_se_despierta_cuando_la_llaman(texto):
    assert LocalVoice().is_wake(texto) is True


@pytest.mark.parametrize(
    "texto",
    [
        "arial font de 16 pixeles",
        "¿que hace ARIA?",
        "la aria de la canción",
        "",
    ],
)
def test_aria_no_se_despierta_sin_que_la_llamen(texto):
    assert LocalVoice().is_wake(texto) is False


def test_la_orden_que_viene_despues_de_la_llamada_no_se_pierde():
    voice = LocalVoice()

    assert voice.strip_wake("Hey, aria, abre la luz") == "abre la luz"
    assert voice.strip_wake("hey aria") == ""
    assert voice.strip_wake("aria, estado del sistema") == "estado del sistema"
    # Sin llamada, la frase se queda como estaba.
    assert voice.strip_wake("abre la luz") == "abre la luz"
