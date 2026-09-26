"""BLOQUE 68 - Local Secure Credential Vault & Encrypted Session Management Engine tests."""

import os
import tempfile

import pytest

from backend.security.vault import (
    CredentialEntry,
    CredentialVaultEngine,
    SessionCookie,
    SessionManager,
    VaultError,
    VaultManager,
    VaultProfile,
    get_engine,
    reset_engine,
)


@pytest.fixture
def engine(tmp_path):
    reset_engine()
    store_dir = tmp_path / "vault"
    store_dir.mkdir()
    os.environ["AURA_VAULT_DIR"] = str(store_dir)
    from backend.security.crypto import EncryptedStore

    store = EncryptedStore(vault_dir=store_dir)
    eng = CredentialVaultEngine(store=store)
    yield eng
    reset_engine()
    os.environ.pop("AURA_VAULT_DIR", None)


class TestCredentialEntry:
    def test_roundtrip(self):
        e = CredentialEntry(key="api_key", value="secret123", kind="token")
        d = e.to_dict()
        assert d["key"] == "api_key"
        assert d["value"] == "secret123"
        e2 = CredentialEntry.from_dict(d)
        assert e2.key == e.key
        assert e2.value == e.value
        assert e2.version == 1

    def test_version_increment(self):
        p = VaultProfile(profile_id="p1", name="n", service="s")
        e = CredentialEntry(key="k", value="v1")
        p.set_credential(e)
        e2 = CredentialEntry(key="k", value="v2")
        p.set_credential(e2)
        assert p.get_credential("k").version == 2


class TestVaultProfile:
    def test_get_set_remove_credential(self):
        p = VaultProfile(profile_id="p1", name="n", service="s")
        e = CredentialEntry(key="k", value="v")
        p.set_credential(e)
        assert p.get_credential("k") is not None
        e2 = CredentialEntry(key="k", value="v2")
        p.set_credential(e2)
        assert p.get_credential("k").value == "v2"
        assert p.get_credential("k").version == 2
        assert p.remove_credential("k") is True
        assert p.get_credential("k") is None
        assert p.remove_credential("k") is False

    def test_roundtrip(self):
        p = VaultProfile(profile_id="p1", name="n", service="s")
        p.set_credential(CredentialEntry(key="k", value="v"))
        d = p.to_dict()
        p2 = VaultProfile.from_dict(d)
        assert p2.profile_id == "p1"
        assert p2.get_credential("k") is not None


class TestSessionManager:
    def test_set_get_remove(self):
        sm = SessionManager()
        c = SessionCookie(cookie_name="sess", cookie_value="abc")
        sm.set("p1", [c])
        assert len(sm.get("p1")) == 1
        assert sm.remove("p1", "sess") is True
        assert sm.get("p1") == []
        assert sm.remove("p1", "sess") is False

    def test_add_dedup(self):
        sm = SessionManager()
        sm.add("p1", SessionCookie(cookie_name="x", cookie_value="1"))
        sm.add("p1", SessionCookie(cookie_name="x", cookie_value="2"))
        assert len(sm.get("p1")) == 1
        assert sm.get("p1")[0].cookie_value == "2"

    def test_clear_all(self):
        sm = SessionManager()
        sm.set("p1", [SessionCookie(cookie_name="a", cookie_value="1")])
        sm.set("p2", [SessionCookie(cookie_name="b", cookie_value="2")])
        sm.clear_all()
        assert sm.active_profiles() == []

    def test_expired(self):
        sm = SessionManager()
        c = SessionCookie(cookie_name="x", cookie_value="1", expires_at=1.0)
        sm.set("p1", [c])
        assert sm.get("p1") == []
        assert sm.purge_expired() == 1


class TestEngine:
    def test_lock_default(self, engine):
        assert engine.is_locked is True

    def test_unlock_lock(self, engine):
        r = engine.unlock("master-secret")
        assert engine.is_locked is False
        assert r["status"] == "unlocked"
        r2 = engine.lock()
        assert engine.is_locked is True
        assert r2["status"] == "locked"

    def test_audit(self, engine):
        engine.unlock("master-secret")
        engine.create_profile(VaultProfile(profile_id="p1", name="n", service="s"))
        events = engine.get_audit(limit=10)
        assert any(e["type"] == "profile_create" for e in events)

    def test_profiles_crud(self, engine):
        engine.unlock("master-secret")
        p = VaultProfile(profile_id="p1", name="n", service="s")
        created = engine.create_profile(p)
        assert created.profile_id == "p1"
        assert len(engine.list_profiles()) == 1
        assert engine.get_profile("p1") is not None
        engine.update_profile("p1", {"name": "n2"})
        assert engine.get_profile("p1").name == "n2"
        assert engine.delete_profile("p1") is True
        assert engine.get_profile("p1") is None
        assert engine.delete_profile("p1") is False

    def test_duplicate_profile(self, engine):
        engine.unlock("master-secret")
        engine.create_profile(VaultProfile(profile_id="p1", name="n", service="s"))
        with pytest.raises(VaultError):
            engine.create_profile(VaultProfile(profile_id="p1", name="n2", service="s2"))

    def test_credentials(self, engine):
        engine.unlock("master-secret")
        engine.create_profile(VaultProfile(profile_id="p1", name="n", service="s"))
        e = CredentialEntry(key="api_key", value="secret123")
        engine.set_credential("p1", e)
        got = engine.get_credential("p1", "api_key")
        assert got is not None
        assert got.value == "secret123"
        assert got.version == 1
        e2 = CredentialEntry(key="api_key", value="secret456")
        engine.set_credential("p1", e2)
        got2 = engine.get_credential("p1", "api_key")
        assert got2.value == "secret456"
        assert got2.version == 2
        assert engine.remove_credential("p1", "api_key") is True
        assert engine.get_credential("p1", "api_key") is None

    def test_sessions(self, engine):
        engine.unlock("master-secret")
        engine.create_profile(VaultProfile(profile_id="p1", name="n", service="s"))
        c = SessionCookie(cookie_name="sess", cookie_value="abc")
        engine.set_session("p1", [c])
        assert len(engine.get_session("p1")) == 1
        headers = engine.inject_session_headers("p1")
        assert headers == {"Cookie": "sess=abc"}
        assert engine.inject_session_headers("nope") == {}
        engine.clear_session("p1")
        assert engine.get_session("p1") == []

    def test_status(self, engine):
        s = engine.status()
        assert s["is_locked"] is True
        engine.unlock("master-secret")
        engine.create_profile(VaultProfile(profile_id="p1", name="n", service="s"))
        s2 = engine.status()
        assert s2["is_locked"] is False
        assert s2["profiles_total"] == 1
        assert s2["audit_entries"] >= 1


class TestSingleton:
    def test_get_reset(self, tmp_path):
        reset_engine()
        os.environ["AURA_VAULT_DIR"] = str(tmp_path / "v")
        a = get_engine()
        b = get_engine()
        assert a is b
        reset_engine()
        c = get_engine()
        assert c is not a
        reset_engine()
        os.environ.pop("AURA_VAULT_DIR", None)
