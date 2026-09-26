"""Tests Bloque 36 — AURA Local Encrypted Vault (cifrado at-rest simétrico).

Valida (sin tocar la red ni servicios cloud):
- derive_key: producción determinista de la clave Fernet con PBKDF2.
- encrypt_json / decrypt_json: round-trip reversibilidad del payload.
- VaultIntegrityError: detección de token manipulado / formato corrupto.
- EncryptedStore: session lock (unlock/lock), auto-lock por inactividad.
- write/read/delete/list_entries: persistencia cifrada en disco (.vault).
- status(): no expone el secreto maestro ni la clave.
- Endpoints REST /api/vault/* (status, unlock, lock, read, write).
"""

from __future__ import annotations

import base64
import json
import os

import pytest

from backend.security.crypto import (
    EncryptedStore,
    VaultIntegrityError,
    VaultLockedError,
    decrypt_json,
    derive_key,
    encrypt_json,
)

# -- derive_key / KDF ----------------------------------------------------------


class TestKeyDerivation:
    def test_derive_key_returns_key_and_salt(self):
        result = derive_key("master-secret-123")
        assert "key" in result and "salt" in result
        assert len(result["key"]) > 0
        # La clave es base64url de 32 bytes → ~44 chars
        decoded = base64.urlsafe_b64decode(result["key"].encode("ascii"))
        assert len(decoded) == 32

    def test_derive_key_is_deterministic_with_same_salt(self):
        salt = os.urandom(16)
        r1 = derive_key("secret", salt=salt)
        r2 = derive_key("secret", salt=salt)
        assert r1["key"] == r2["key"]
        assert r1["salt"] == r2["salt"]

    def test_derive_key_differs_with_different_salt(self):
        r1 = derive_key("secret")
        r2 = derive_key("secret")
        assert r1["key"] != r2["key"]

    def test_derive_key_empty_raises(self):
        with pytest.raises(ValueError):
            derive_key("")


# -- encrypt_json / decrypt_json ----------------------------------------------


class TestEncryptionPipeline:
    @pytest.fixture()
    def key(self):
        return derive_key("test-master-secret")["key"]

    def test_round_trip_json(self, key):
        payload = {"work_id": "w1", "characters": ["a", "b"], "notes": "confidential", "n": 3.14}
        blob = encrypt_json(payload, key)
        assert isinstance(blob, str)
        assert "." in blob  # header.token
        decrypted = decrypt_json(blob, key)
        assert decrypted == payload

    def test_blob_format_has_magic_header(self, key):
        blob = encrypt_json({"a": 1}, key)
        header_b64 = blob.split(".", 1)[0]
        header = json.loads(base64.urlsafe_b64decode(header_b64.encode("ascii")))
        assert header["magic"] == "AURAVLT2"
        assert header["kdf"] == "pbkdf2-hmac-sha256"

    def test_decrypt_corrupted_raises_vault_integrity(self, key):
        blob = encrypt_json({"a": 1}, key)
        # Corromper el token (cambiar un carácter)
        header_b64, token = blob.split(".", 1)
        corrupted_token = token[:-2] + "AA"
        corrupted_blob = header_b64 + "." + corrupted_token
        with pytest.raises(VaultIntegrityError):
            decrypt_json(corrupted_blob, key)

    def test_decrypt_invalid_format_raises(self, key):
        with pytest.raises(VaultIntegrityError):
            decrypt_json("not-a-valid-blob", key)

    def test_decrypt_wrong_key_raises(self, key):
        blob = encrypt_json({"secret": "data"}, key)
        wrong_key = derive_key("wrong-secret")["key"]
        with pytest.raises(VaultIntegrityError):
            decrypt_json(blob, wrong_key)

    def test_no_secret_in_blob(self, key):
        """El blob cifrado no debe contener el secreto maestro ni la clave."""
        secret = "MY_SECRET_PASSPHRASE_12345"
        derived = derive_key(secret)
        blob = encrypt_json({"data": "sensitive"}, derived["key"])
        assert secret not in blob
        assert derived["key"] not in blob


# -- EncryptedStore ------------------------------------------------------------


class TestEncryptedStore:
    @pytest.fixture()
    def store(self, tmp_path):
        return EncryptedStore(vault_dir=str(tmp_path / "vault"))

    def test_locked_by_default(self, store):
        assert store.is_locked
        with pytest.raises(VaultLockedError):
            store.write("secret", {"data": "value"})
        with pytest.raises(VaultLockedError):
            store.read("secret")

    def test_unlock_and_read_write(self, store):
        store.unlock("my-master-secret")
        store.write("characters", {"hero": {"name": "Alice"}})
        result = store.read("characters")
        assert result == {"hero": {"name": "Alice"}}

    def test_lock_clears_key(self, store):
        store.unlock("secret")
        store.lock()
        assert store.is_locked

    def test_auto_lock_on_idle(self, store, monkeypatch):
        store.unlock(
            "secret",
        )
        store._lock_secs = 1  # 1 segundo para test
        store._last_activity = 0.0  # forzar expiración
        store.auto_lock_if_idle()
        assert store.is_locked

    def test_status_does_not_expose_secret(self, store):
        store.unlock("super-secret-key")
        status = store.status()
        assert "super-secret-key" not in json.dumps(status)
        assert "secret" not in status
        assert status["locked"] is False

    def test_delete_and_list(self, store):
        store.unlock("secret")
        store.write("entry1", {"a": 1})
        store.write("entry2", {"b": 2})
        assert "entry1" in store.list_entries()
        assert "entry2" in store.list_entries()
        result = store.delete("entry1")
        assert result["status"] == "deleted"
        assert "entry1" not in store.list_entries()

    def test_disk_file_is_not_plaintext(self, store, tmp_path):
        store.unlock("secret")
        payload = {"confidential": "TOP_SECRET_DATA_42"}
        store.write("test", payload)
        files = list((tmp_path / "vault").glob("*.vault"))
        assert len(files) == 1
        content = files[0].read_text(encoding="utf-8")
        assert "TOP_SECRET_DATA_42" not in content
        assert "confidential" not in content
        # El magic AURAVLT2 está dentro del header base64-encoded.
        header_b64 = content.split(".", 1)[0]
        header = json.loads(base64.urlsafe_b64decode(header_b64.encode("ascii")))
        assert header["magic"] == "AURAVLT2"

    def test_seconds_until_lock(self, store):
        store.unlock("secret")
        store._lock_secs = 100
        remaining = store.seconds_until_lock()
        assert 0 < remaining <= 100

    def test_read_nonexistent_returns_none(self, store):
        store.unlock("secret")
        assert store.read("nonexistent") is None


# -- REST endpoints ------------------------------------------------------------


class TestVaultRESTEndpoints:
    @pytest.fixture()
    def client(self, tmp_path, monkeypatch):
        import backend.main as main_mod

        monkeypatch.setenv("AURA_VAULT_DIR", str(tmp_path / "rest_vault"))
        main_mod._vault = None  # reset singleton para aislamiento
        from fastapi.testclient import TestClient

        from backend.main import app

        return TestClient(app)

    def test_vault_status(self, client):
        resp = client.get("/api/vault/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "locked" in data

    def test_vault_unlock_wrong_secret(self, client):
        # Primero abrir con el secreto correcto para crear el verifier persistente.
        client.post("/api/vault/unlock", json={"master_secret": "correct-secret-123"})
        client.post("/api/vault/lock")
        # Ahora un secreto incorrecto debe ser rechazado (403).
        resp = client.post("/api/vault/unlock", json={"master_secret": "incorrect"})
        assert resp.status_code == 403
        assert "detail" in resp.json()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
