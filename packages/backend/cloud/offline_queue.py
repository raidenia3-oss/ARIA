# -*- coding: utf-8 -*-
"""AURA OS — Offline-First Sync Queue.

Guarda acciones localmente cuando sin internet y
las reintenta cuando vuelve la conexion.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AURA.OfflineQueue")


class OfflineQueue:
    """Cola de acciones offline con SQLite local + memory buffer."""

    def __init__(self, db_path: str = "data/aura_offline.db") -> None:
        self.db_path = db_path
        self._memory_buffer: List[Dict[str, Any]] = []
        self._buffer_limit = 100
        self._initialized: bool = False
        self._queue: List[Dict[str, Any]] = []
        self._init_db()

    def _init_db(self) -> None:
        """Inicializa SQLite local para la cola offline."""
        import os
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS offline_queue (
                    action_id TEXT PRIMARY KEY,
                    device_id TEXT,
                    action TEXT,
                    data TEXT,
                    created_at REAL,
                    attempts INTEGER DEFAULT 0,
                    last_attempt REAL,
                    status TEXT DEFAULT 'pending'
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_id TEXT,
                    device_id TEXT,
                    action TEXT,
                    status TEXT,
                    timestamp REAL
                )
            """)
            conn.commit()
            conn.close()
            self._initialized = True
            logger.info("SQLite offline queue init: %s", self.db_path)
        except Exception as exc:
            logger.warning("SQLite init failed, using memory only: %s", exc)
            self._initialized = False

    async def queue_action(self, action: Dict[str, Any]) -> str:
        """Guarda accion localmente cuando sin internet."""
        action_id = f"off_{uuid.uuid4().hex[:12]}"
        now = time.time()
        entry = {
            "action_id": action_id,
            "device_id": action.get("device_id", "unknown"),
            "action": action.get("action", "unknown"),
            "data": action.get("data", {}),
            "created_at": now,
            "attempts": 0,
            "last_attempt": 0,
            "status": "pending",
        }

        self._memory_buffer.append(entry)
        if len(self._memory_buffer) > self._buffer_limit:
            self._flush_buffer_to_db()

        if self._initialized:
            self._save_to_db(entry)

        logger.debug("Queued action: %s", action_id)
        return action_id

    async def retry_offline_queue(self) -> Dict[str, Any]:
        """Reintenta acciones pendientes cuando vuelve conexion."""
        pending = self._get_pending_actions()
        retried = 0
        failed: List[str] = []

        for entry in pending:
            entry["attempts"] += 1
            entry["last_attempt"] = time.time()

            try:
                self._execute_action(entry)
                entry["status"] = "completed"
                self._mark_completed(entry["action_id"])
                retried += 1
                logger.debug("Retried action: %s -> OK", entry["action_id"])
            except Exception as exc:
                failed.append(entry["action_id"])
                logger.debug("Retried action: %s -> FAIL: %s", entry["action_id"], exc)

        if len(self._memory_buffer) > self._buffer_limit * 2:
            self._memory_buffer = self._memory_buffer[-self._buffer_limit:]

        self._cleanup_completed()

        return {
            "retried": retried,
            "failed": failed,
            "remaining_pending": len(self._get_pending_actions()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def get_queue_status(self) -> Dict[str, Any]:
        """Retorna estado de la cola offline."""
        pending = self._get_pending_actions()
        total_bytes = sum(len(json.dumps(e.get("data", {}))) for e in pending)
        mb_pending = round(total_bytes / (1024 * 1024), 4)

        avg_wait = 0.0
        if pending:
            now = time.time()
            total_wait = sum(now - e["created_at"] for e in pending)
            avg_wait = round(total_wait / len(pending), 1)

        eta_seconds = int(avg_wait * len(pending))
        eta_str = f"{eta_seconds}s" if eta_seconds < 60 else f"{eta_seconds // 60}m {eta_seconds % 60}s"

        return {
            "pending_actions": len(pending),
            "memory_buffer_size": len(self._memory_buffer),
            "mb_pending": mb_pending,
            "avg_wait_seconds": avg_wait,
            "eta_sync": eta_str,
            "sqlite_available": self._initialized,
            "oldest_pending": pending[0]["created_at"] if pending else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _get_pending_actions(self) -> List[Dict[str, Any]]:
        """Obtiene acciones pendientes."""
        pending: List[Dict[str, Any]] = []

        for entry in self._memory_buffer:
            if entry.get("status") == "pending":
                pending.append(entry)

        if self._initialized:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT action_id, device_id, action, data, created_at, attempts, status FROM offline_queue WHERE status = 'pending'")
                for row in cursor.fetchall():
                    pending.append({
                        "action_id": row[0],
                        "device_id": row[1],
                        "action": row[2],
                        "data": json.loads(row[3]) if isinstance(row[3], str) else row[3],
                        "created_at": row[4],
                        "attempts": row[5],
                        "status": row[6],
                    })
                conn.close()
            except Exception:
                pass

        return sorted(pending, key=lambda e: e.get("created_at", 0))

    def _flush_buffer_to_db(self) -> None:
        """Vacia el buffer de memoria a SQLite."""
        if not self._initialized:
            return
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            for entry in self._memory_buffer:
                cursor.execute(
                    "INSERT OR REPLACE INTO offline_queue (action_id, device_id, action, data, created_at, attempts, last_attempt, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (entry["action_id"], entry["device_id"], entry["action"],
                     json.dumps(entry.get("data", {})), entry["created_at"],
                     entry["attempts"], entry["last_attempt"], entry["status"]),
                )
            conn.commit()
            conn.close()
            logger.debug("Buffer flushed to DB: %d entries", len(self._memory_buffer))
        except Exception as exc:
            logger.warning("Buffer flush failed: %s", exc)

    def _save_to_db(self, entry: Dict[str, Any]) -> None:
        """Guarda una entrada en SQLite."""
        if not self._initialized:
            return
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO offline_queue (action_id, device_id, action, data, created_at, attempts, last_attempt, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (entry["action_id"], entry["device_id"], entry["action"],
                 json.dumps(entry.get("data", {})), entry["created_at"],
                 entry["attempts"], entry["last_attempt"], entry["status"]),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def _execute_action(self, entry: Dict[str, Any]) -> None:
        """Simula la ejecucion de una accion."""
        logger.debug("Executing action: %s", entry["action_id"])

    def _mark_completed(self, action_id: str) -> None:
        """Marca una accion como completada."""
        for entry in self._memory_buffer:
            if entry["action_id"] == action_id:
                entry["status"] = "completed"
                break
        if self._initialized:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("UPDATE offline_queue SET status = 'completed' WHERE action_id = ?", (action_id,))
                cursor.execute("INSERT INTO sync_log (action_id, device_id, action, status, timestamp) VALUES (?, ?, ?, ?, ?)",
                               (action_id, "unknown", "retry", "completed", time.time()))
                conn.commit()
                conn.close()
            except Exception:
                pass

    def _cleanup_completed(self) -> None:
        """Limpia acciones completadas de la memoria."""
        self._memory_buffer = [e for e in self._memory_buffer if e.get("status") != "completed"]


offline_queue = OfflineQueue()
