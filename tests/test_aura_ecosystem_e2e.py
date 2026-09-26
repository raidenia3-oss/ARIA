"""Tests Bloque 39 — AURA Ecosystem End-to-End Verification.

Suite de integración global que simula el ciclo de vida completo de una
sesión literaria 100% local (sin red, sin servicios cloud):
- Crear obra + personaje en AME (StoryStorage / CharacterBible).
- Adjuntar nota de voz → transcribir localmente (stub STT) → poblar canon.
- Cifrar buffer en la SD (EncryptedStore at-rest).
- Health-check aggregator del Master Launcher.
- Verificar que ningún dato sensible (secreto maestro, texto plano) se filtra
  en los artifacts de disco o en los logs.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from backend.audio.transcriber import LocalWhisperTranscriber
from backend.security.crypto import EncryptedStore, derive_key, encrypt_json
from backend.story_memory.canon_tracker import CanonTracker
from backend.story_memory.character_bible import CharacterBible
from backend.story_memory.story_storage import StoryStorage

# -- Ciclo de vida completo (100% local, sin TestClient) ------------------------


def test_full_literary_session_lifecycle(tmp_path, monkeypatch):
    """Crear obra → personaje → voz → canon → cifrado SD → verificación."""
    monkeypatch.setenv("AURA_STORY_DIR", str(tmp_path / "story"))
    monkeypatch.setenv("AURA_AUDIO_TMP_DIR", str(tmp_path / "tmp_audio"))
    monkeypatch.setenv("AURA_WHISPER_ENGINE", "stub")

    storage = StoryStorage()
    ct = CanonTracker()
    cb = CharacterBible()

    # 1. Crear obra + personaje
    storage.create_work("eco_test", "Ecosistema Soberano", universe="local")
    cb.create(
        work_id="eco_test",
        char_id="kira",
        name="Kira",
        voice="voz neutral",
        personality={"leal": True},
        objectives=["proteger el canon"],
        conflicts=["traición en el acto III"],
        relationships={"dorian": "aliado"},
        aliases=["hero"],
        species="humano",
        age=30,
        backstory="guardián de la red local",
    )

    # 2. Nota de voz → transcribir (stub 100% local) → poblar canon
    transcriber = LocalWhisperTranscriber(engine="stub")
    audio = b"\x00\x01\x02 voice bytes eco_test"
    (tmp_path / "note.ogg").write_bytes(audio)
    result = transcriber.transcribe_file(tmp_path / "note.ogg")
    assert result["engine"] == "stub"
    text = result["text"]
    assert "sha1=" in text

    added = ct.add_canon_event(work_id="eco_test", description=text, source="ame_voice")
    assert added["status"] == "added"

    # 3. Cifrar buffer en la SD (EncryptedStore at-rest)
    vault_dir = tmp_path / "vault"
    store = EncryptedStore(vault_dir=str(vault_dir), lock_secs=60)
    store.unlock("secreto-maestro-del-escritor")
    store.write("character_bible", {"char_id": "kira", "name": "Kira"})
    assert store.read("character_bible")["name"] == "Kira"

    # 4. Verificar que el fichero en disco NO contiene texto plano
    raw = (vault_dir / "character_bible.vault").read_text(encoding="utf-8")
    assert "Kira" not in raw
    assert "secreto-maestro" not in raw

    # 5. Verificar que el canon fue persistido (100% local)
    events = storage.get_canon_events("eco_test")
    assert len(events) == 1
    assert text in events[0]["description"]


def test_no_secrets_leak_in_canon_feed(tmp_path, monkeypatch):
    """El canon feed no debe AGREGAR ni propagar el secreto maestro ni la clave.

    El storage es pasivo: guarda lo que se le pasa. La responsabilidad de no
    pasar secrets reales al canon feed es del caller (el test lo verifica
    aquí: si el caller no pasa el secreto, el storage no lo añade).
    """
    monkeypatch.setenv("AURA_STORY_DIR", str(tmp_path / "story"))
    storage = StoryStorage()
    ct = CanonTracker()
    storage.create_work("leak_test", "Leak Test")
    # El caller NO pasa el secreto maestro → el storage no lo añade.
    ct.add_canon_event(work_id="leak_test", description="nota publica del canon", source="user")
    events = storage.get_canon_events("leak_test")
    assert "secreto" not in events[0]["description"].lower()
    assert "key" not in events[0]["description"].lower()
    assert "master_secret" not in events[0]["description"].lower()


def test_encrypted_store_status_does_not_leak_secrets(tmp_path):
    store = EncryptedStore(vault_dir=str(tmp_path / "vault"), lock_secs=60)
    store.unlock("secreto-maestro-del-escritor")
    status = store.status()
    assert "secreto" not in str(status).lower()
    assert "key" not in status and "master_secret" not in status


# -- Health-check aggregator (Master Launcher) --------------------------------


def test_master_launcher_health_aggregator(monkeypatch):
    """El health-check aggregator del Master Launcher es local y no cuelga."""
    import importlib.util
    from pathlib import Path

    script = Path(__file__).resolve().parents[1] / "scripts" / "aura-master.py"
    spec = importlib.util.spec_from_file_location("aura_master", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Todo caído → degraded (no cuelga, returned quickly).
    report = mod.aggregate_health(9999, include_jan=False, include_discord=False)
    assert report["overall"] == "degraded"
    assert report["checks"][0]["service"] == "backend"

    # Mockeado: todo arriba → ok.
    def fake(url, timeout=5):  # noqa: ARG001
        if "/health" in url:
            return {"status": "ok"}
        return None

    monkeypatch.setattr(mod, "http_get_json", fake)
    report = mod.aggregate_health(8000, include_jan=False, include_discord=False)
    assert report["overall"] == "ok"
