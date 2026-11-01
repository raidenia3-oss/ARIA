"""Import-time regressions for `backend.main`.

The passlib/bcrypt probe in `backend/main.py` used to raise `ValueError`
("password cannot be longer than 72 bytes") the first time a password was
hashed or verified, which broke login and registration at runtime while the
module itself still imported fine. These tests pin the two halves of that
contract: the module imports, and the hashing path actually works.
"""


def test_backend_main_imports_without_error():
    """Verify backend.main can be imported without crypto errors"""
    import backend.main
    assert backend.main is not None  # Just verify it imported


def test_password_hash_round_trip_uses_bcrypt_directly():
    """Hashing and verifying must work without passlib in the import path."""
    import backend.main as main

    hashed = main.get_password_hash("secret123")

    assert hashed.startswith("$2"), f"not a bcrypt hash: {hashed!r}"
    assert main.verify_password("secret123", hashed) is True
    assert main.verify_password("wrong-password", hashed) is False


def test_verify_password_rejects_unusable_hashes():
    """An empty or malformed hash is not a valid credential, and must not raise."""
    import backend.main as main

    assert main.verify_password("secret123", "") is False
    assert main.verify_password("secret123", "not-a-bcrypt-hash") is False


def test_password_longer_than_bcrypt_limit_is_handled():
    """bcrypt caps input at 72 bytes; a longer password must still round-trip."""
    import backend.main as main

    long_password = "a" * 200
    hashed = main.get_password_hash(long_password)

    assert main.verify_password(long_password, hashed) is True
