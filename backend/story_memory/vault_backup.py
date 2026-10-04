"""Discord Vault Auto-Backup — respaldo cifrado y asíncrono de snapshots literarios.

Integra el Literary Snapshot Engine (BLOQUE 32) con la Bóveda de Discord (BLOQUE 30)
sin bloquear el hilo principal del backend y sin depender de servicios externos.

Diseño local-first y soberanía de datos:
- El respaldo es OPCIONAL: solo se activa si la configuración está presente.
- Los snapshots se empaquetan en un bundle JSON y se cifran con Fernet
  (AES-128-CBC + HMAC) antes de salir de la máquina. Nunca viajan en texto plano.
- La clave se deriva con PBKDF2-HMAC-SHA256 de una frase de paso (passphrase) que se
  lee SOLO de variables de entorno. No se hardcodean ni exponen credenciales.
- La subida se ejecuta en un hilo daemon (no bloquea el event loop / main thread).

Configuración (variables de entorno, nunca en código):
  DISCORD_VAULT_WEBHOOK_URL  -> URL del webhook del canal de respaldo de Discord.
  DISCORD_VAULT_PASSPHRASE   -> Frase de paso para derivar la clave de cifrado.
  AURA_STORY_DIR             -> (opcional) ruta del storage literario.
"""

from __future__ import annotations

import base64
import json
import os
import threading
import time
from typing import Any, Dict, List, Optional

from backend.story_memory.versioning import LiterarySnapshotEngine, get_snapshot_engine

# Valor centinela para distinguir "no provisto" de "provisto como None".
_UNSET = object()

# Iteraciones PBKDF2 recomendadas por OWASP para SHA256.
_KDF_ITERATIONS = 390_000


class DiscordVaultBackup:
    """Empaqueta y sube snapshots cifrados a la Bóveda de Discord.

    Sin webhook o sin passphrase configurados, las operaciones de subida se abortan
    con status ``"disabled"`` en lugar de fallar, manteniendo la compatibilidad REST.
    """

    FORMAT_ID = "aura-literary-snapshot-vault"
    FORMAT_VERSION = 1
    FORMAT_PREFIX = b"AURAVLT1."

    def __init__(
        self,
        engine: Optional[LiterarySnapshotEngine] = None,
        webhook_url: Optional[str] = _UNSET,
        passphrase: Optional[str] = _UNSET,
    ) -> None:
        self.engine = engine or get_snapshot_engine()
        self.webhook_url: Optional[str] = (
            self._normalize(webhook_url)
            if webhook_url is not _UNSET
            else self._normalize(os.getenv("DISCORD_VAULT_WEBHOOK_URL"))
        )
        self.passphrase: Optional[str] = (
            self._normalize(passphrase)
            if passphrase is not _UNSET
            else self._normalize(os.getenv("DISCORD_VAULT_PASSPHRASE"))
        )
        self._lock = threading.Lock()

    @staticmethod
    def _normalize(value: Any) -> Optional[str]:
        """Normaliza a str, tratando None/vacío como 'ausencia'."""
        if value is None:
            return None
        s = str(value).strip()
        return s or None

    # -- estado de configuración ---------------------------------------------------

    @property
    def configured(self) -> bool:
        """El backup está disponible solo si hay webhook Y passphrase."""
        return bool(self.webhook_url and self.passphrase)

    def status(self) -> Dict[str, Any]:
        """Reporte de estado sin exponer secretos (solo flags booleanos)."""
        if self.configured:
            level = "ready"
        elif self.webhook_url and not self.passphrase:
            level = "missing-passphrase"
        elif self.passphrase and not self.webhook_url:
            level = "missing-webhook"
        else:
            level = "disabled"
        return {
            "status": "ok",
            "source": "env",
            "level": level,
            "configured": self.configured,
            # Nunca devolvemos el webhook ni la passphrase.
            "webhook_set": bool(self.webhook_url),
            "passphrase_set": bool(self.passphrase),
        }

    # -- cifrado ---------------------------------------------------------------------

    @staticmethod
    def _fernet_key(passphrase: str, salt: bytes, iterations: int = _KDF_ITERATIONS) -> bytes:
        """Deriva la clave Fernet de 32 bytes con PBKDF2-HMAC-SHA256."""
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=iterations,
        )
        return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))

    def encrypt(self, plaintext: bytes) -> bytes:
        """Cifra bytes con Fernet (clave derivada por PBKDF2-HMAC-SHA256).

        Retorna ``<FORMAT_PREFIX><salt_b64>.<token_b64>`` para autenticar el formato.
        Lanza ValueError si no hay passphrase configurada.
        """
        if not self.passphrase:
            raise ValueError("DISCORD_VAULT_PASSPHRASE no está configurada")

        from cryptography.fernet import Fernet

        salt = os.urandom(16)
        key = self._fernet_key(self.passphrase, salt)
        token = Fernet(key).encrypt(plaintext)
        salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii")
        return self.FORMAT_PREFIX + f"{salt_b64}.".encode("ascii") + token

    def decrypt(self, blob: bytes) -> bytes:
        """Descifra un blob producido por :meth:`encrypt` (tests/diagnóstico)."""
        if not self.passphrase:
            raise ValueError("DISCORD_VAULT_PASSPHRASE no está configurada")
        if not blob.startswith(self.FORMAT_PREFIX):
            raise ValueError("formato de vault no reconocido")

        body = blob[len(self.FORMAT_PREFIX):].split(b".", 1)
        if len(body) != 2:
            raise ValueError("blob de vault corrupto")

        from cryptography.fernet import Fernet

        salt = base64.urlsafe_b64decode(body[0])
        key = self._fernet_key(self.passphrase, salt)
        return Fernet(key).decrypt(body[1])

    # -- empaquetado ------------------------------------------------------------------

    def package(self, work_id: str, branch: str = "main", recent_n: int = 5) -> bytes:
        """Empaqueta los últimos ``recent_n`` snapshots en un bundle cifrado."""
        snapshots = self.engine.list_snapshots(work_id, branch=branch)
        recent = snapshots[-recent_n:] if recent_n > 0 else snapshots

        items: List[Dict[str, Any]] = []
        for manifest in recent:
            snap_id = manifest.get("snapshot_id")
            if not snap_id:
                continue
            raw = self.engine.export_snapshot(work_id, snap_id, branch=branch)
            if raw:
                items.append(json.loads(raw))

        bundle = {
            "format": self.FORMAT_ID,
            "version": self.FORMAT_VERSION,
            "type": "literary-snapshots-vault-backup",
            "work_id": work_id,
            "branch": branch,
            "count": len(items),
            "created_at": time.time(),
            "snapshots": items,
        }
        return self.encrypt(json.dumps(bundle, ensure_ascii=False).encode("utf-8"))

    def _bundle_count(self, payload: bytes) -> int:
        """Descifra y devuelve el número de snapshots del bundle (para telemetría).

        No expone contenido del snapshot, solo la métrica. Fallo => 0.
        """
        try:
            plain = self.decrypt(payload)
            return int(json.loads(plain).get("count", 0))
        except Exception:  # noqa: BLE001
            return 0

    # -- subida ---------------------------------------------------------------------

    def push(self, work_id: str, branch: str = "main", recent_n: int = 5) -> Dict[str, Any]:
        """Sube el bundle cifrado al webhook de Discord (bloqueante, best-effort).

        Retorna dict con resultado. Aborta sin excepción si no está configurado.
        """
        if not self.configured:
            return {
                "status": "disabled",
                "reason": "vault backup not configured (webhook y/o passphrase)",
                "work_id": work_id,
            }

        try:
            payload = self.package(work_id, branch=branch, recent_n=recent_n)
            count = self._bundle_count(payload)
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "error": "encrypt_failed", "detail": str(exc)}

        import httpx

        try:
            resp = httpx.post(
                self.webhook_url,
                files=[
                    (
                        "upload",
                        (f"literary-{branch}.bin", payload, "application/octet-stream"),
                    )
                ],
                timeout=30.0,
            )
            ok = resp.status_code < 300
            return {
                "status": "ok" if ok else "error",
                "uploaded": ok,
                "http_status": resp.status_code,
                "work_id": work_id,
                "branch": branch,
                "encrypted": True,
                "bytes": len(payload),
                "count": count,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "error",
                "uploaded": False,
                "error": "upload_failed",
                "detail": str(exc),
                "work_id": work_id,
            }

    def push_async(self, work_id: str, branch: str = "main", recent_n: int = 5) -> Dict[str, Any]:
        """Sube el backup en un hilo daemon sin bloquear el hilo principal (FASE 3)."""
        if not self.configured:
            return {
                "status": "disabled",
                "reason": "vault backup not configured (webhook y/o passphrase)",
                "work_id": work_id,
            }

        def _run() -> None:
            try:
                self.push(work_id, branch=branch, recent_n=recent_n)
            except Exception:  # noqa: BLE001 — backup best-effort y silencioso
                pass

        threading.Thread(target=_run, name="aura-vault-backup", daemon=True).start()
        return {
            "status": "accepted",
            "work_id": work_id,
            "branch": branch,
            "note": "backup en segundo plano (asíncrono)",
        }


_vault: Optional[DiscordVaultBackup] = None
_vault_lock = threading.Lock()


def get_vault_backup() -> DiscordVaultBackup:
    """Singleton del respaldo a la Bóveda (configurado desde el entorno)."""
    global _vault
    if _vault is None:
        with _vault_lock:
            if _vault is None:
                _vault = DiscordVaultBackup()
    return _vault


def reset_vault_backup() -> None:
    """Reinicia el singleton aislado (útil para tests)."""
    global _vault
    with _vault_lock:
        _vault = None