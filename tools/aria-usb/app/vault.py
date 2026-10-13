from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1
KEY_LEN = 32
SALT_LEN = 16


@dataclass
class VaultBlob:
    version: int
    salt: bytes
    ciphertext: bytes

    def to_bytes(self) -> bytes:
        return json.dumps({
            "v": self.version,
            "salt": self.salt.hex(),
            "ct": self.ciphertext.hex(),
        }).encode()

    @classmethod
    def from_bytes(cls, data: bytes) -> "VaultBlob":
        obj = json.loads(data.decode())
        return cls(
            version=obj["v"],
            salt=bytes.fromhex(obj["salt"]),
            ciphertext=bytes.fromhex(obj["ct"]),
        )


def derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = Scrypt(
        salt=salt,
        length=KEY_LEN,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
    )
    return kdf.derive(passphrase.encode())


def encrypt_blob(plaintext: bytes, passphrase: str) -> VaultBlob:
    salt = os.urandom(SALT_LEN)
    key = derive_key(passphrase, salt)
    f = Fernet(base64.urlsafe_b64encode(key))
    ct = f.encrypt(plaintext)
    return VaultBlob(version=1, salt=salt, ciphertext=ct)


def decrypt_blob(blob: VaultBlob, passphrase: str) -> bytes:
    key = derive_key(passphrase, blob.salt)
    f = Fernet(base64.urlsafe_b64encode(key))
    return f.decrypt(blob.ciphertext)


class Vault:
    def __init__(self, path: str):
        self._path = path
        self._key: Optional[bytes] = None

    def create(self, passphrase: str, data: bytes) -> None:
        blob = encrypt_blob(data, passphrase)
        with open(self._path, "wb") as f:
            f.write(blob.to_bytes())

    def open(self, passphrase: str) -> bytes:
        with open(self._path, "rb") as f:
            raw = f.read()
        try:
            blob = VaultBlob.from_bytes(raw)
        except (json.JSONDecodeError, KeyError, ValueError):
            raise ValueError("passphrase incorrecta o archivo manipulado")
        try:
            data = decrypt_blob(blob, passphrase)
        except InvalidToken:
            raise ValueError("passphrase incorrecta o archivo manipulado")
        self._key = derive_key(passphrase, blob.salt)
        return data

    def close(self) -> None:
        self._key = None

    @property
    def is_open(self) -> bool:
        return self._key is not None