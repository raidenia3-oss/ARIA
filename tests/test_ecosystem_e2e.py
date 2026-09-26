"""Bloque 39 — Full-Stack Integration Suite (E2E global del ecosistema AURA).

Verifica el ciclo de vida completo de una sesión literaria cruzando TODOS los
subsistemas consolidados, sin depender de red/internet ni servicios externos:

  creación de obra (story_memory)
  → personaje (character_bible)
  → evento canónico (canon_tracker)
  → snapshot versionado (versioning)
  → cifrado at-rest (security/crypto)
  → transcripción de voz local (audio/transcriber, engine stub)
  → descubrimiento mDNS (mobile/discovery)
  → broadcast en tiempo real (websocket_manager)
  → orquestación (scripts/aura-master, funciones puras)

Cada test es independiente y usa almacenamiento temporal aislado (tmp_path).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# -- story_memory: obra + personaje + canon --------------------------------------


def test_story_memory_create_work_character_canon(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STORY_DIR", str(tmp_path / "story"))
    from backend.story_memory.canon_tracker import CanonTracker
    from backend.story_memory.character_bible import CharacterBible
    from backend.story_memory.story_storage import StoryStorage

    store = StoryStorage(store_dir=str(tmp_path / "story"))
    work = store.create_work(work_id="eco_work", title="Eco Soberano", author="tester")
    assert work["status"] == "created"

    bible = CharacterBible()
    char = bible.create(work_id="eco_work", char_id="kira", name="Kira", personality=["valiente"])
    assert char["char_id"] == "kira"

    ct = CanonTracker()
    ev = ct.add_canon_event(work_id="eco_work", description="Kira cruza el umbral", source="test")
    assert ev["status"] == "added"
    assert len(ct.get_all_events("eco_work")) == 1


# -- versioning: snapshot + diff + branch ----------------------------------------


def test_versioning_snapshot_diff_branch(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STORY_DIR", str(tmp_path / "story"))
    from backend.story_memory.versioning import LiterarySnapshotEngine, set_engine_store_path

    set_engine_store_path(str(tmp_path / "story"))
    eng = LiterarySnapshotEngine(store_dir=str(tmp_path / "story"))
    from backend.story_memory.canon_tracker import CanonTracker
    from backend.story_memory.story_storage import StoryStorage

    StoryStorage(store_dir=str(tmp_path / "story")).create_work(
        work_id="eco_work", title="Eco", author="t"
    )
    CanonTracker().add_canon_event(work_id="eco_work", description="A", source="t")

    s1 = eng.create_snapshot("eco_work", message="v1")
    assert s1["status"] == "created"
    CanonTracker().add_canon_event(work_id="eco_work", description="B", source="t")
    s2 = eng.create_snapshot("eco_work", message="v2")
    assert s2["status"] == "created"

    diff = eng.diff_snapshots(
        "eco_work", s1["snapshot"]["snapshot_id"], s2["snapshot"]["snapshot_id"]
    )
    assert diff["changed"] is True

    branches = eng.list_branches("eco_work")
    assert "main" in branches
    set_engine_store_path(None)


# -- security: cifrado at-rest + session lock ------------------------------------


def test_security_encrypted_store_roundtrip(tmp_path):
    from backend.security.crypto import EncryptedStore

    store = EncryptedStore(vault_dir=str(tmp_path / "vault"), lock_secs=60)
    store.unlock("secreto-soberano")
    store.write("bible", {"char_id": "kira", "note": "secreto"})
    raw = (tmp_path / "vault" / "bible.vault").read_text(encoding="utf-8")
    assert "secreto" not in raw  # at-rest: sin texto plano en disco
    assert store.read("bible") == {"char_id": "kira", "note": "secreto"}


def test_security_session_lock_blocks_access(tmp_path):
    from backend.security.crypto import EncryptedStore, VaultLockedError

    store = EncryptedStore(vault_dir=str(tmp_path / "vault"), lock_secs=1)
    store.unlock("clave")
    store.write("x", {"a": 1})
    store._last_activity -= 2  # fuerza inactividad
    store.auto_lock_if_idle()
    assert store.is_locked is True
    with pytest.raises(VaultLockedError):
        store.read("x")


# -- audio: transcripción local (stub, sin torch) ---------------------------------


def test_audio_transcribe_stub_local(tmp_path):
    from backend.audio.transcriber import LocalWhisperTranscriber

    t = LocalWhisperTranscriber(tmp_dir=str(tmp_path / "audio"), engine="stub")
    assert t.available is True
    p = t.save_upload("nota.wav", b"\x00" * 100)
    result = t.transcribe_file(p)
    assert result["engine"] == "stub"
    assert "STT local stub" in result["text"]


# -- mobile: mDNS discovery + fallback manual ------------------------------------


def test_mobile_discovery_manual_fallback(tmp_path, monkeypatch):
    from backend.mobile.discovery import MDNSDiscovery, parse_manual_hosts

    monkeypatch.setenv("AURA_HOST_IPS", "10.0.0.5, 10.0.0.6")
    monkeypatch.setenv("TAILSCALE_IP", "100.64.0.1")
    hosts = parse_manual_hosts()
    assert "10.0.0.5" in hosts and "100.64.0.1" in hosts

    disc = MDNSDiscovery(port=8000)
    # get_discovered_hosts() ya fusiona los hosts manuales como fallback.
    found = disc.get_discovered_hosts()
    assert found["manual-10.0.0.5"]["address"] == "10.0.0.5"
    assert found["manual-100.64.0.1"]["port"] == 8000


# -- websocket: broadcast a suscriptores ------------------------------------------


def test_websocket_broadcast_to_subscribers():
    import asyncio

    from backend.websocket_manager import WSGateway

    gw = WSGateway()
    work_id = "eco_work_ws"
    c1, c2 = MagicMock(), MagicMock()

    async def _send(m):
        pass

    c1.send = _send
    c2.send = _send
    gw.add_connection(c1)
    gw.add_connection(c2)
    gw.subscribe(c1, work_id)
    # c2 no suscrito a work_id → no recibe

    sent = asyncio.run(gw.broadcast("canon_event", {"d": "hola"}, work_id=work_id))
    assert sent == 1  # solo c1 suscrito
    gw.remove_connection(c1)
    gw.remove_connection(c2)


# -- master launcher: funciones puras de orquestación -----------------------------


def test_master_launcher_pure_functions():
    import importlib.util

    script = Path(__file__).resolve().parents[1] / "scripts" / "aura-master.py"
    spec = importlib.util.spec_from_file_location("am", script)
    am = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(am)

    args = am.parse_args(["--port", "9090", "--no-discord"])
    assert args.port == 9090 and args.no_discord is True
    services = am.build_services(9090, include_discord=False)
    assert "backend" in services and "uvicorn" in services["backend"]


# -- ciclo de vida completo integrado (obra → canon → snapshot → cifrado) ---------


def test_full_lifecycle_sovereign_session(tmp_path, monkeypatch):
    """Ciclo de vida completo: obra → personaje → canon → snapshot → cifrado at-rest."""
    monkeypatch.setenv("AURA_STORY_DIR", str(tmp_path / "story"))
    from backend.security.crypto import EncryptedStore
    from backend.story_memory.canon_tracker import CanonTracker
    from backend.story_memory.story_storage import StoryStorage
    from backend.story_memory.versioning import LiterarySnapshotEngine, set_engine_store_path

    # 1. Obra + canon
    store = StoryStorage(store_dir=str(tmp_path / "story"))
    store.create_work(work_id="lifecycle", title="Soberana", author="user")
    CanonTracker().add_canon_event(
        work_id="lifecycle", description="Inicio de la trama", source="ame"
    )

    # 2. Snapshot versionado
    set_engine_store_path(str(tmp_path / "story"))
    eng = LiterarySnapshotEngine(store_dir=str(tmp_path / "story"))
    snap = eng.create_snapshot("lifecycle", message="checkpoint inicial")
    assert snap["status"] == "created"

    # 3. Cifrado at-rest del snapshot
    vault = EncryptedStore(vault_dir=str(tmp_path / "vault"), lock_secs=900)
    vault.unlock("master-user-secret")
    vault.write("lifecycle_snapshot", snap["snapshot"])
    raw = (tmp_path / "vault" / "lifecycle_snapshot.vault").read_text(encoding="utf-8")
    assert "lifecycle" not in raw  # cifrado: sin fuga del work_id en claro
    assert vault.read("lifecycle_snapshot") == snap["snapshot"]
    set_engine_store_path(None)
