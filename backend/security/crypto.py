"""AURA Local Encrypted Vault — cifrado simétrico at-rest (Bloque 36).

Pipeline de cifrado local para proteger la Character Bible, notas y sesiones
literarias almacenadas en disco (PC y tarjeta SD del móvil), sin depender de
servicios de cifrado cloud ni de gestores de llaves externos.

Diseño local-first:
- Simétrico: Fernet (AES-128-CBC + HMAC-SHA256, autenticado) de `cryptography`
  (dependencia ya presente en el venv, usada por vault_backup).
- Derivación de llave: PBKDF2-HMAC-SHA256 (390k iteraciones) a partir de un
  secreto maestro de usuario. El secreto maestro NUNCA se persiste en texto
  plano: se lee del entorno (AURA_VAULT_SECRET) o se pasa explícitamente.
- Session Lock: la bóveda se bloquea automáticamente tras un periodo de
  inactividad (AURA_VAULT_LOCK_SECS, default 900s = 15 min). Mientras está
  bloqueada, la clave derivada solo vive en memoria y se borra al bloquear.
- Formato de fichero cifrado: JSON con magic ``AURAVLT2`` + salt + token, de
  modo que un fichero extraído del disco/SD sea ilegible sin la clave.

No modifica los contratos REST existentes: es una capa opt-in de utilidades.
"""

from __future__ import annotations

import base64
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Constantes criptográficas.
_MAGIC = "AURAVLT2"
_KDF_ITERATIONS = 390_000
_DEFAULT_LOCK_SECS = 900  # 15 minutos de inactividad antes del auto-lock.

# Entorno (nunca valores por defecto con secretos).
_SECRET_ENV = "AURA_VAULT_SECRET"
_LOCK_SECS_ENV = "AURA_VAULT_LOCK_SECS"

VaultError = Exception


class VaultLockedError(Exception):
    """Se intentó usar la bóveda mientras estaba bloqueada."""


class VaultIntegrityError(Exception):
    """El token cifrado es inválido o fue manipulado (HMAC no coincide)."""


def _fernet_key(master_secret: str, salt: bytes, iterations: int = _KDF_ITERATIONS) -> bytes:
    """Deriva una clave Fernet de 32 bytes con PBKDF2-HMAC-SHA256."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return base64.urlsafe_b64encode(kdf.derive(master_secret.encode("utf-8")))


def derive_key(master_secret: str, salt: Optional[bytes] = None) -> Dict[str, Any]:
    """Deriva la clave de bóveda desde el secreto maestro del usuario.

    Retorna ``{"key": urlsafe_b64_str, "salt": urlsafe_b64_str}``. La clave se
    retorna codificada base64url para transporte; no se escribe a disco.
    """
    if not master_secret:
        raise ValueError("master_secret vacío: se requiere un secreto maestro de usuario")
    salt = salt or os.urandom(16)
    key = _fernet_key(master_secret, salt)
    return {
        "key": key.decode("ascii"),
        "salt": base64.urlsafe_b64encode(salt).decode("ascii"),
    }


def encrypt_bytes(plaintext: bytes, key_b64: str) -> bytes:
    """Cifra bytes arbitrarios con la clave derivada (Fernet, autenticado)."""
    from cryptography.fernet import Fernet

    return Fernet(key_b64.encode("ascii")).encrypt(plaintext)


def decrypt_bytes(token: bytes, key_b64: str) -> bytes:
    """Descifra bytes; lanza VaultIntegrityError si el token es inválido."""
    from cryptography.fernet import Fernet, InvalidToken

    try:
        return Fernet(key_b64.encode("ascii")).decrypt(token)
    except InvalidToken as exc:
        raise VaultIntegrityError("token cifrado inválido o manipulado") from exc


def encrypt_json(payload: Any, key_b64: str) -> str:
    """Cifra un payload JSON-serializable y retorna un fichero cifrado (str)."""
    plaintext = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    salt = os.urandom(16)
    # Nota: key_b64 ya es la clave derivada; el salt del fichero es metadata de
    # contexto para la rotación futura (KDF versionada).
    token = encrypt_bytes(plaintext, key_b64)
    header = {"magic": _MAGIC, "kdf": "pbkdf2-hmac-sha256", "iterations": _KDF_ITERATIONS,
              "salt": base64.urlsafe_b64encode(salt).decode("ascii")}
    return base64.urlsafe_b64encode(json.dumps(header).encode("utf-8")).decode("ascii") + "." + \
        token.decode("ascii")


def decrypt_json(blob: str, key_b64: str) -> Any:
    """Descifra un fichero producido por :func:`encrypt_json`."""
    try:
        header_b64, token_b64 = blob.split(".", 1)
    except ValueError as exc:
        raise VaultIntegrityError("formato de bóveda no reconocido") from exc
    try:
        header = json.loads(base64.urlsafe_b64decode(header_b64.encode("ascii")))
    except Exception as exc:  # noqa: BLE001
        raise VaultIntegrityError("cabecera de bóveda corrupta") from exc
    if header.get("magic") != _MAGIC:
        raise VaultIntegrityError("magic de bóveda no reconocido")
    return json.loads(decrypt_bytes(token_b64.encode("ascii"), key_b64))


class EncryptedStore:
    """Bóveda literaria cifrada at-rest con bloqueo por inactividad (func. 3).

    - ``unlock(master_secret)``: deriva la clave en memoria (nunca se persiste).
    - ``write(name, payload)`` / ``read(name)``: ficheros JSON cifrados en
      ``vault_dir`` (PC o tarjeta SD montada). En disco solo hay cabecera +
      token Fernet: sin la clave, los datos son ilegibles.
    - ``lock()``: borra la clave de memoria. ``auto_lock_if_idle()`` se invoca
      en cada operación y bloquea si pasó el periodo de inactividad.
    """

    def __init__(self, vault_dir: Optional[str] = None, lock_secs: Optional[int] = None) -> None:
        self.vault_dir = Path(vault_dir or os.getenv("AURA_VAULT_DIR", "./secure_vault"))
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        self._lock_secs = int(lock_secs or os.getenv(_LOCK_SECS_ENV, str(_DEFAULT_LOCK_SECS)))
        self._key_b64: Optional[str] = None
        self._last_activity: float = 0.0
        self._mutex = threading.RLock()
        # Archivo de verificación: token Fernet cifrado con la clave derivada
        # que permite validar el secreto maestro sin persistirlo en texto plano.
        self._verify_path = self.vault_dir / ".vault_key"

    # -- estado del session lock ------------------------------------------------

    @property
    def is_locked(self) -> bool:
        return self._key_b64 is None

    @property
    def lock_secs(self) -> int:
        return self._lock_secs

    def seconds_until_lock(self) -> int:
        """Segundos restantes antes del auto-lock (0 si ya bloqueada)."""
        if self.is_locked:
            return 0
        remaining = self._lock_secs - (time.time() - self._last_activity)
        return max(0, int(remaining))

    def unlock(self, master_secret: str) -> Dict[str, Any]:
        """Deriva la clave en memoria y abre la sesión de bóveda.

        Valida el secreto maestro contra un verifier persistente (``.vault_key``).
        Si es la primera vez (sin verifier), se crea. Si el secreto es incorrecto,
        lanza ``VaultLockedError``.
        """
        with self._mutex:
            derived = derive_key(master_secret)
            key_b64 = derived["key"]
            if self._verify_path.exists():
                try:
                    decrypt_json(self._verify_path.read_text(encoding="utf-8"), key_b64)
                except (VaultIntegrityError, ValueError):
                    raise VaultLockedError("secreto maestro incorrecto: la bóveda está bloqueada con otro secreto")
            else:
                self._verify_path.write_text(encrypt_json({"verify": True, "ts": time.time()}, key_b64), encoding="utf-8")
            self._key_b64 = key_b64
            self._last_activity = time.time()
            return {"status": "unlocked", "lock_secs": self._lock_secs}

    def lock(self) -> Dict[str, Any]:
        """Cierra la sesión: borra la clave de memoria (session lock)."""
        with self._mutex:
            self._key_b64 = None
            self._last_activity = 0.0
            return {"status": "locked"}

    def auto_lock_if_idle(self) -> None:
        """Bloquea la bóveda si superó el periodo de inactividad."""
        with self._mutex:
            if not self.is_locked and self.seconds_until_lock() == 0:
                self.lock()

    # -- persistencia cifrada -----------------------------------------------------

    def _require_unlocked(self) -> str:
        with self._mutex:
            self.auto_lock_if_idle()
            if self._key_b64 is None:
                raise VaultLockedError("bóveda bloqueada: se requiere unlock(master_secret)")
            return self._key_b64

    def _path(self, name: str) -> Path:
        safe = "".join(c for c in name if c.isalnum() or c in ("-", "_", "."))
        return self.vault_dir / f"{safe}.vault"

    def write(self, name: str, payload: Any) -> Dict[str, Any]:
        """Cifra y escribe un payload JSON en la bóveda (at-rest)."""
        key = self._require_unlocked()
        blob = encrypt_json(payload, key)
        with self._mutex:
            self._path(name).write_text(blob, encoding="utf-8")
            self._last_activity = time.time()
        return {"status": "written", "name": name, "encrypted": True}

    def read(self, name: str) -> Any:
        """Lee y descifra un fichero de la bóveda."""
        key = self._require_unlocked()
        path = self._path(name)
        if not path.exists():
            return None
        with self._mutex:
            self._last_activity = time.time()
        return decrypt_json(path.read_text(encoding="utf-8"), key)

    def delete(self, name: str) -> Dict[str, Any]:
        """Elimina un fichero cifrado de la bóveda."""
        path = self._path(name)
        if path.exists():
            path.unlink()
            return {"status": "deleted", "name": name}
        return {"status": "not_found", "name": name}

    def list_entries(self) -> List[str]:
        """Lista los nombres de ficheros cifrados en la bóveda."""
        return sorted(p.stem for p in self.vault_dir.glob("*.vault"))

    def status(self) -> Dict[str, Any]:
        """Estado de la bóveda sin exponer secretos."""
        return {
            "status": "ok",
            "locked": self.is_locked,
            "lock_secs": self._lock_secs,
            "seconds_until_lock": self.seconds_until_lock(),
            "entries": len(self.list_entries()),
            "vault_dir_set": True,
        }


def get_default_store() -> EncryptedStore:
    """Bóveda por defecto configurada desde el entorno (sin secretos en código)."""
    return EncryptedStore()