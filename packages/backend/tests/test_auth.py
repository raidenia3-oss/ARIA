import pytest
from backend.auth.security import hash_password, verify_password, create_access_token, verify_token


def test_hash_password():
    password = "test123"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed)
    assert not verify_password("wrong", hashed)


def test_jwt_token_creation():
    token = create_access_token("user_123")
    assert token is not None
    assert isinstance(token, str)


def test_jwt_token_verification():
    user_id = "user_123"
    token = create_access_token(user_id)
    token_data = verify_token(token)
    assert token_data.sub == user_id
