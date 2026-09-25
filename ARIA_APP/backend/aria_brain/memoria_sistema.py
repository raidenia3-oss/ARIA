import asyncio
import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


class ShortTermMemory:
    def __init__(self, capacity: int = 10) -> None:
        self.capacity = capacity
        self._items: List[Dict[str, Any]] = []

    def store(self, item: Dict[str, Any]) -> None:
        item["timestamp"] = datetime.now().isoformat()
        self._items.append(item)
        if len(self._items) > self.capacity:
            self._items = self._items[-self.capacity :]

    def get_recent(self, n: int = 5) -> List[Dict[str, Any]]:
        return self._items[-n:]

    def query(self, query: str) -> List[Dict[str, Any]]:
        query_lower = query.lower()
        return [i for i in self._items if query_lower in str(i.get("content", "")).lower()]

    def clear(self) -> None:
        self._items.clear()

    @property
    def size(self) -> int:
        return len(self._items)


class LongTermMemory:
    def __init__(self, db_path: str = "") -> None:
        self.db_path = db_path or os.path.join(
            os.path.dirname(__file__), "..", "memory", "aria_long.db"
        )
        self._init_db()

    def _init_db(self) -> None:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            metadata TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now')),
            importance REAL DEFAULT 0.5
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS concepts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            embeddings TEXT DEFAULT '[]',
            relations TEXT DEFAULT '[]',
            visit_count INTEGER DEFAULT 0
        )""")
        conn.commit()
        conn.close()

    def store(
        self,
        content: str,
        category: str = "general",
        metadata: Optional[Dict] = None,
        importance: float = 0.5,
    ) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "INSERT INTO memories (content, category, metadata, importance) VALUES (?, ?, ?, ?)",
            (content, category, json.dumps(metadata or {}), importance),
        )
        conn.commit()
        conn.close()
        return cursor.lastrowid

    def query(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT content, category, metadata, importance FROM memories WHERE content LIKE ? ORDER BY importance DESC LIMIT ?",
            (f"%{query}%", limit),
        )
        results = [
            {"content": r[0], "category": r[1], "metadata": json.loads(r[2]), "importance": r[3]}
            for r in cursor.fetchall()
        ]
        conn.close()
        return results

    def get_by_category(self, category: str, limit: int = 50) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT content, category, metadata, importance FROM memories WHERE category = ? ORDER BY created_at DESC LIMIT ?",
            (category, limit),
        )
        results = [
            {"content": r[0], "category": r[1], "metadata": json.loads(r[2]), "importance": r[3]}
            for r in cursor.fetchall()
        ]
        conn.close()
        return results


class SemanticMemory:
    def __init__(self) -> None:
        self._concepts: Dict[str, Dict[str, Any]] = {}
        self._relations: List[Tuple[str, str, str]] = []

    def add_concept(
        self, name: str, embeddings: List[float] = None, attributes: Optional[Dict] = None
    ) -> None:
        if name not in self._concepts:
            self._concepts[name] = {
                "name": name,
                "embeddings": embeddings or [],
                "attributes": attributes or {},
                "visit_count": 0,
            }

    def add_relation(self, concept_a: str, concept_b: str, relation_type: str) -> None:
        self.add_concept(concept_a)
        self.add_concept(concept_b)
        self._relations.append((concept_a, concept_b, relation_type))

    def get_related(self, concept: str, relation_type: str = None) -> List[str]:
        return [
            r[1]
            for r in self._relations
            if r[0] == concept and (relation_type is None or r[2] == relation_type)
        ]

    def query(self, query: str) -> List[Dict[str, Any]]:
        results = []
        for name, data in self._concepts.items():
            if query.lower() in name.lower():
                results.append(
                    {
                        "concept": name,
                        "attributes": data["attributes"],
                        "relations": self.get_related(name),
                    }
                )
        return results


class EpisodicMemory:
    def __init__(self) -> None:
        self._events: List[Dict[str, Any]] = []

    def store_event(
        self, event: str, context: Dict[str, Any] = None, importance: float = 0.5
    ) -> None:
        self._events.append(
            {
                "event": event,
                "context": context or {},
                "importance": importance,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def get_events(self, last_n: int = 20) -> List[Dict[str, Any]]:
        return self._events[-last_n:]

    def search(self, query: str) -> List[Dict[str, Any]]:
        query_lower = query.lower()
        return [
            e
            for e in self._events
            if query_lower in str(e.get("event", "")).lower()
            or query_lower in str(e.get("context", "")).lower()
        ]
