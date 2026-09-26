"""Database — SQLite + vectors"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional


class Database:
    """Base de datos SQLite con soporte vectorial básico"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(Path('ARIA_v4/AURA_APP/data/cerebro.db'))
        self.conn = None
        self._init_db()

    def _init_db(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_input TEXT,
                intent TEXT,
                response TEXT,
                timestamp TEXT,
                metadata TEXT
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT,
                embedding BLOB,
                category TEXT,
                created_at TEXT
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                definition TEXT,
                usage_count INTEGER DEFAULT 0,
                last_used TEXT
            )
        """)
        self.conn.commit()

    def store_interaction(self, user_input: str, intent: str, response: str, metadata: dict = None) -> int:
        cursor = self.conn.execute(
            """INSERT INTO interactions (user_input, intent, response, timestamp, metadata)
               VALUES (?, ?, ?, ?, ?)""",
            (user_input, intent, response, datetime.now().isoformat(),
             json.dumps(metadata) if metadata else None),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_interactions(self, limit: int = 50) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT * FROM interactions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def store_memory(self, content: str, category: str = "general") -> int:
        cursor = self.conn.execute(
            "INSERT INTO memories (content, embedding, category, created_at) VALUES (?, ?, ?, ?)",
            (content, None, category, datetime.now().isoformat()),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_memories(self, category: str = None, limit: int = 100) -> List[Dict]:
        query = "SELECT * FROM memories"
        params = []
        if category:
            query += " WHERE category = ?"
            params.append(category)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        if self.conn:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
