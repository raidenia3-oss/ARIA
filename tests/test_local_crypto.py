"""Tests Bloque 36 — Local Encrypted Vault & SD-Card Security Layer.

Valida (sin red):
- Derivación de llave PBKDF2 desde el secreto maestro (no persistido en claro).
- Reversibilidad e integridad del cifrado (Fernet autenticado).
- EncryptedStore: persistencia at-rest cifrada; el fichero en disco NO contiene
  texto plano de la Character Bible.
- Session Lock: bloqueo automático por inactividad y acceso denegado bloqueada.
- Salt aleatorio: dos cifrados del mismo payload difieren (no determinista).
"""

from __future__ import annotations

import base64
import json

import pytest

from backend.security.crypto import (
    EncryptedStore,
    VaultIntegrityError,
    VaultLockedError,
    decrypt_json,
    derive_key,
    encrypt_json,
)

# -- Derivación de llave --------------------------------------------------------


def test_derive_key_requires_master_secret():
    with pytest.raises(ValueError):
        derive_key("")


def test_derive_key_produces_urlsafe_key_and_salt():
    derived = derive_key("secreto-maestro-del-escritor")
    assert len(derived["key"]) > 40
    assert len(derived["salt"]) > 20
    # La clave no debe contener el secreto en claro.
    assert "secreto-maestro" not in derived["key"]


def test_derive_key_deterministic_with_same_salt():
    d1 = derive_key("sec", salt=b"0123456789abcdef")
    d2 = derive_key("sec", salt=b"0123456789abcdef")
    assert d1["key"] == d2["key"]


def test_derive_key_differs_with_different_salt():
    d1 = derive_key("sec", salt=b"0123456789abcdef")
    d2 = derive_key("sec", salt=b"ffffffffffffffff")
    assert d1["key"] != d2["key"]


# -- Reversibilidad e integridad --------------------------------------------------


def test_encrypt_json_roundtrip():
    payload = {"char_id": "kira", "traits": ["valiente", "leal"], "canon": 42}
    key = derive_key("frase-secreta")["key"]
    blob = encrypt_json(payload, key)
    assert decrypt_json(blob, key) == payload


def test_ciphertext_hides_plaintext():
    """El blob cifrado no contiene el texto plano (at-rest)."""
    secret = "El villano es el hermano gemelo"
    key = derive_key("k")["key"]
    blob = encrypt_json({"note": secret}, key)
    assert secret not in blob
    assert secret.encode("utf-8") not in blob.encode("utf-8")


def test_wrong_key_raises_integrity_error():
    key_a = derive_key("clave-a")["key"]
    key_b = derive_key("clave-b")["key"]
    blob = encrypt_json({"x": 1}, key_a)
    with pytest.raises(VaultIntegrityError):
        decrypt_json(blob, key_b)


def test_tampered_blob_raises_integrity_error():
    """Un byte alterado en el token rompe el HMAC (integridad)."""
    key = derive_key("k")["key"]
    blob = encrypt_json({"x": 1}, key)
    header, token = blob.rsplit(".", 1)
    tampered_token = ("A" if token[0] != "A" else "B") + token[1:]
    with pytest.raises(VaultIntegrityError):
        decrypt_json(f"{header}.{tampered_token}", key)


def test_salts_make_ciphertext_nondeterministic():
    """Dos cifrados del mismo payload difieren (salt aleatorio por fichero)."""
    key = derive_key("k")["key"]
    b1 = encrypt_json({"same": True}, key)
    b2 = encrypt_json({"same": True}, key)
    assert b1 != b2


# -- EncryptedStore (persistencia at-rest + session lock) ---------------------------


@pytest.fixture
def store(tmp_path):
    return EncryptedStore(vault_dir=str(tmp_path / "vault"), lock_secs=60)


def test_store_locked_by_default_and_blocks_read_write(store):
    assert store.is_locked is True
    with pytest.raises(VaultLockedError):
        store.write("bible", {"x": 1})
    with pytest.raises(VaultLockedError):
        store.read("bible")


def test_store_roundtrip_on_disk(store):
    store.unlock("secreto-del-escritor")
    character_bible = {
        "char_id": "kira",
        "name": "Kira",
        "relationships": {"dorian": "aliado"},
        "notes": "Traición en el acto III",
    }
    store.write("character_bible", character_bible)
    assert store.read("character_bible") == character_bible
    assert "character_bible" in store.list_entries()


def test_store_file_on_disk_is_not_plaintext(store):
    """El fichero .vault en disco/SD no contiene el texto plano."""
    store.unlock("secreto-del-escritor")
    secret = "El mapamundi se encuentra en la biblioteca"
    store.write("notas", {"note": secret})
    raw = (store.vault_dir / "notas.vault").read_text(encoding="utf-8")
    assert secret not in raw
    assert "mapamundi" not in raw
    parsed = json.loads(base64.urlsafe_b64decode(raw.split(".")[0]))
    assert parsed["magic"] == "AURAVLT2"


def test_store_wrong_master_secret_cannot_read(store):
    store.unlock("clave-correcta")
    store.write("sesion", {"chapter": 7})
    store.lock()
    # El secreto incorrecto es rechazado al desbloquear (validator del verifier):
    # la clave derivada no puede descifrar el .vault_key persistente.
    with pytest.raises(VaultLockedError):
        store.unlock("clave-incorrecta")


def test_store_auto_lock_after_inactivity(store):
    store.unlock("secreto")
    assert store.is_locked is False
    # Simular inactividad mayor al periodo de lock (lock_secs=60).
    store._last_activity -= store.lock_secs + 1
    store.auto_lock_if_idle()
    assert store.is_locked is True
    with pytest.raises(VaultLockedError):
        store.read("anything")


def test_store_seconds_until_lock_counts_down(store):
    store.unlock("secreto")
    remaining = store.seconds_until_lock()
    assert 0 < remaining <= store.lock_secs
    store._last_activity -= 10
    assert store.seconds_until_lock() == remaining - 10


def test_store_status_does_not_leak_secrets(store):
    store.unlock("secreto-del-escritor")
    status = store.status()
    assert status["locked"] is False
    assert "secreto" not in str(status).lower()
    assert "key" not in status and "master_secret" not in status


def test_store_delete_and_missing_read(store):
    store.unlock("s")
    store.write("tmp", {"a": 1})
    assert store.delete("tmp")["status"] == "deleted"
    assert store.read("tmp") is None
    assert store.delete("tmp")["status"] == "not_found"
