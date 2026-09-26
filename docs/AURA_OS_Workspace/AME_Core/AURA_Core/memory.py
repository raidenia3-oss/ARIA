import os
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "aura_memory.db"


def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                title TEXT
            )
            """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                provider_used TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
            """)


def create_session(title: str | None = None) -> int:
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO sessions (created_at, title) VALUES (?, ?)",
            (datetime.utcnow().isoformat(), title),
        )
        return cur.lastrowid


def add_message(session_id: int, role: str, content: str, provider_used: str | None = None) -> int:
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO messages (session_id, role, content, timestamp, provider_used) VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, datetime.utcnow().isoformat(), provider_used),
        )
        return cur.lastrowid


def get_chat_history(session_id: int, limit: int = 20) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT id, role, content, timestamp, provider_used FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    rows = list(reversed(rows))
    return [dict(r) for r in rows]


def clear_history(session_id: int) -> None:
    with _conn() as con:
        con.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
