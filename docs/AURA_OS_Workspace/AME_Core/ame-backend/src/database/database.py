"""
Persistencia segura y centralizada para AURA.

- Si existe DATABASE_URL (PostgreSQL/MongoDB), intenta inicializar el cliente correspondiente.
- Si no, usa almacenamiento JSON local con bloqueo de archivos multiplataforma
  (msvcrt en Windows, fcntl en Unix) para evitar corrupciones por escrituras concurrentes.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional


# ---------- File locking multiplataforma ----------
if sys.platform == "win32":  # pragma: no cover - Windows
    import msvcrt

    def _lock_file(fh):
        try:
            msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)
        except Exception:
            # En algunos entornos (p. ej. tuberías), locking no es soportado;
            # seguimos sin bloquear para no interrumpir la operación.
            pass

    def _unlock_file(fh):
        try:
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        except Exception:
            pass
else:  # pragma: no cover - Unix/Linux
    import fcntl

    def _lock_file(fh):
        try:
            fcntl.flock(fh, fcntl.LOCK_EX)
        except Exception:
            pass

    def _unlock_file(fh):
        try:
            fcntl.flock(fh, fcntl.LOCK_UN)
        except Exception:
            pass


class Database:
    """Capa de persistencia centralizada.

    Uso típico:

        db = Database()
        targets = db.read("config/targets.json", default=[])
        db.write("data/db.json", {"balance": 0.0})
    """

    def __init__(self, base_path: Optional[Path] = None) -> None:
        self.base_path: Path = base_path or Path(__file__).resolve().parent.parent
        self.db_url: str = (os.environ.get("DATABASE_URL") or "").strip()
        self._use_external: bool = False
        self._external_client: Any = None
        self._external_db: Any = None

        if self.db_url:
            self._init_external()

    # ------------------------------------------------------------------ #
    # Inicialización de motores externos
    # ------------------------------------------------------------------ #
    def _init_external(self) -> None:
        url = self.db_url.lower()
        try:
            if url.startswith("postgres") or url.startswith("postgresql"):
                try:
                    import psycopg2  # type: ignore
                    self._external_client = psycopg2.connect(self.db_url)
                    self._use_external = True
                except Exception as exc:
                    print(f"[Database] No se pudo conectar a PostgreSQL: {exc}")
            elif url.startswith("mongodb") or url.startswith("mongodb+srv"):
                try:
                    import pymongo  # type: ignore
                    self._external_client = pymongo.MongoClient(self.db_url)
                    self._external_db = self._external_client.get_default_database()
                    self._use_external = True
                except Exception as exc:
                    print(f"[Database] No se pudo conectar a MongoDB: {exc}")
            else:
                print(f"[Database] DATABASE_URL no soportada ({url}), usando JSON local.")
        except Exception as exc:
            print(f"[Database] Error inicializando motor externo: {exc}")

    # ------------------------------------------------------------------ #
    # API pública JSON local con file locking
    # ------------------------------------------------------------------ #
    def _resolve_path(self, relative_path: str) -> Path:
        return self.base_path / relative_path

    def read(self, relative_path: str, default: Any = None) -> Any:
        """Lee JSON desde disco con lock exclusivo.

        Si el archivo no existe o está corrupto, retorna ``default``.
        """
        if self._use_external:
            # Placeholder: en una implementación completa se consultaría la BD.
            return default

        path = self._resolve_path(relative_path)
        if not path.exists():
            return default if default is not None else {}

        try:
            with open(path, "r", encoding="utf-8") as fh:
                _lock_file(fh)
                try:
                    return json.load(fh)
                finally:
                    _unlock_file(fh)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[Database] Lectura corrupta en {relative_path}: {exc}")
            return default if default is not None else {}
        except Exception as exc:
            print(f"[Database] Error inesperado leyendo {relative_path}: {exc}")
            return default if default is not None else {}

    def write(self, relative_path: str, data: Any) -> bool:
        """Escribe JSON en disco con lock exclusivo y fsync."""
        if self._use_external:
            # Placeholder: en una implementación completa se guardaría en la BD.
            return False

        path = self._resolve_path(relative_path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                _lock_file(fh)
                try:
                    json.dump(data, fh, ensure_ascii=False, indent=2)
                    fh.flush()
                    try:
                        os.fsync(fh.fileno())
                    except OSError:
                        # Windows no siempre soporta fsync en handles abiertos para escritura.
                        pass
                finally:
                    _unlock_file(fh)
            return True
        except Exception as exc:
            print(f"[Database] Error escribiendo {relative_path}: {exc}")
            return False

    # ------------------------------------------------------------------ #
    # Utilidades
    # ------------------------------------------------------------------ #
    def close(self) -> None:
        """Cierra conexiones externas si aplica."""
        try:
            if self._external_client is not None:
                self._external_client.close()
        except Exception:
            pass
        self._external_client = None
        self._external_db = None
        self._use_external = False

    def is_external(self) -> bool:
        return self._use_external
