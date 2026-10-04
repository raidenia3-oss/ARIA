# -*- coding: utf-8 -*-
"""Canonical bcrypt password hashing for the FastAPI backend.

There is ONE implementation because there is one `users.hashed_password`
column. Two code paths used to disagree about the 72-byte limit:

* ``backend/main.py`` truncated the secret explicitly, so a long password
  hashed fine.
* ``backend/auth/service.py`` passed ``password.encode()`` straight to
  ``bcrypt.hashpw``. bcrypt >= 4.1 raises instead of truncating, so the same
  password returned HTTP 500 through ``/api/auth/register`` and
  ``/api/auth/login`` while succeeding through ``/token``.

passlib is deliberately NOT in this path: passlib 1.7.4 probes
``bcrypt.__about__`` and its ``detect_wrap_bug`` check hashes an intentionally
long secret, which bcrypt >= 4.1 rejects. Construction of ``CryptContext`` then
succeeds and the failure surfaces only on the first hash — a 100% broken login
path that still looked healthy at import time.

Both entry points go through here so the policy cannot drift again.
"""
from __future__ import annotations

import bcrypt

#: bcrypt's hard input cap. Exceeding it raises rather than truncating.
BCRYPT_MAX_SECRET_BYTES = 72


def bcrypt_secret(password: str) -> bytes:
    """Encode a password for bcrypt, honouring its hard 72-byte input cap.

    Truncation is explicit and by BYTES, not characters: doing it here means a
    stored hash always matches what login recomputes, instead of depending on
    a library's internal behaviour.
    """
    if password is None:
        password = ""
    return password.encode("utf-8")[:BCRYPT_MAX_SECRET_BYTES]


def get_password_hash(password: str) -> str:
    """Return a fresh bcrypt hash as ASCII text."""
    return bcrypt.hashpw(bcrypt_secret(password), bcrypt.gensalt()).decode("ascii")


def verify_password(plain_password: str, hashed_password) -> bool:
    """Check a password against a stored hash.

    Accepts the stored value as ``str`` or ``bytes``: the ORM declares the
    column as ``String`` in ``backend/models.py`` and ``LargeBinary`` in
    ``backend/auth/models.py``, and SQLite hands back whatever was written.
    An unusable hash is never a valid credential, and never raises.
    """
    if not hashed_password:
        return False
    if isinstance(hashed_password, str):
        stored = hashed_password.encode("utf-8")
    elif isinstance(hashed_password, (bytes, bytearray)):
        stored = bytes(hashed_password)
    else:
        return False
    try:
        return bcrypt.checkpw(bcrypt_secret(plain_password), stored)
    except (ValueError, TypeError):
        return False