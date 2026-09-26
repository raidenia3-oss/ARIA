"""Memoria Sistema — Gestión de memoria semántica mejorada.

Almacena y recupera memorias con contexto temporal,
prioridad y auto-organización.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class MemoriaManager:
    """Gestión avanzada de memoria semántica."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(Path('ARIA_v4/AURA_APP/data/cerebro.db'))
        self.memories: List[dict] = []
        self._init_db()
        self._load_memories()

    def _init_db(self):
        """Inicializa base de datos SQLite."""
        try:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    priority REAL DEFAULT 0.5,
                    timestamp TEXT NOT NULL,
                    tags TEXT DEFAULT '[]',
                    context TEXT DEFAULT '',
                    importance REAL DEFAULT 0.5,
                    access_count INTEGER DEFAULT 0,
                    last_accessed TEXT DEFAULT ''
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_memories_timestamp
                ON memories(timestamp)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_memories_category
                ON memories(category)
            ''')
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[MemoriaManager] DB init error: {e}")

    def _load_memories(self):
        """Carga memorias de la BD."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM memories ORDER BY timestamp DESC LIMIT 200')
            rows = cursor.fetchall()
            self.memories = [dict(row) for row in rows]
            conn.close()
        except Exception as e:
            print(f"[MemoriaManager] Load error: {e}")

    async def store(self, memory: dict) -> str:
        """Almacena memoria con contexto."""
        import uuid
        memory_id = str(uuid.uuid4())[:16]
        now = datetime.now().isoformat()

        memory.setdefault('id', memory_id)
        memory.setdefault('timestamp', now)
        memory.setdefault('category', memory.get('category', 'general'))
        memory.setdefault('priority', memory.get('priority', 0.5))
        memory.setdefault('tags', json.dumps(memory.get('tags', [])))
        memory.setdefault('context', memory.get('context', ''))
        memory.setdefault('importance', memory.get('importance', 0.5))
        memory.setdefault('access_count', 0)
        memory.setdefault('last_accessed', '')

        self.memories.insert(0, memory)
        if len(self.memories) > 500:
            self.memories = self.memories[:500]

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO memories
                (id, content, category, priority, timestamp, tags, context, importance, access_count, last_accessed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                memory_id,
                memory.get('content', str(memory)),
                memory.get('category', 'general'),
                memory.get('priority', 0.5),
                now,
                json.dumps(memory.get('tags', [])),
                memory.get('context', ''),
                memory.get('importance', 0.5),
                0,
                '',
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[MemoriaManager] Store error: {e}")

        return memory_id

    async def retrieve(self, query: str, limit: int = 5) -> List[dict]:
        """Recupera memorias relevantes."""
        query_lower = query.lower()
        relevant = []

        for m in self.memories:
            content = str(m.get('content', ''))
            context = str(m.get('context', ''))
            tags = m.get('tags', '[]')
            try:
                tags_list = json.loads(tags) if isinstance(tags, str) else tags
            except Exception:
                tags_list = []

            score = 0
            if query_lower in content.lower():
                score += 3.0
            if query_lower in context.lower():
                score += 2.0
            for tag in tags_list:
                if query_lower in str(tag).lower():
                    score += 1.5

            score += m.get('importance', 0.5) * 0.5

            if score > 0:
                relevant.append((score, m))

        relevant.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in relevant[:limit]]

    async def delete(self, memory_id: str) -> bool:
        """Elimina memoria."""
        self.memories = [m for m in self.memories if m.get('id') != memory_id]
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute('DELETE FROM memories WHERE id = ?', (memory_id,))
            conn.commit()
            conn.close()
        except Exception:
            pass
        return True

    def all(self) -> List[dict]:
        return self.memories

    def get_by_category(self, category: str) -> List[dict]:
        return [m for m in self.memories if m.get('category') == category]

    def get_important(self, threshold: float = 0.7) -> List[dict]:
        return [m for m in self.memories if m.get('importance', 0) >= threshold]

    def get_recent(self, hours: int = 24) -> List[dict]:
        cutoff = datetime.now().timestamp() - (hours * 3600)
        return [
            m for m in self.memories
            if datetime.fromisoformat(m.get('timestamp', '2000-01-01')).timestamp() > cutoff
        ]
