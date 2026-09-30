"""Database and directory initialisation.

ARIA's state is SQLite, created on demand by each subsystem. Setup's job is to
make sure the *directories* exist and that the primary database has its schema,
without touching data that already exists.

Both operations are read-mostly: an existing table is never dropped or altered.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .model import StepResult

# Directories ARIA assumes exist. Created if missing, never emptied.
REQUIRED_DIRS: tuple[str, ...] = (
    ".aura",
    "data",
    "logs",
    "storage",
    "config",
    "aria_memory_db",
    "LongMemory",
    "ARIA_APP/data",
    "ARIA_APP/logs",
    "ARIA_APP/backend/memory",
    "ARIA_APP/backend/logs",
    "ARIA_APP/backend/data",
)

# The core schema. Mirrors what the backends open on first use, so a fresh
# checkout is immediately readable by the API layer.
CORE_TABLES: tuple[tuple[str, str], ...] = (
    (
        "conversations",
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            title TEXT,
            metadata TEXT DEFAULT '{}'
        )
        """,
    ),
    (
        "messages",
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (conversation_id) REFERENCES conversations (id)
        )
        """,
    ),
    (
        "memories",
        """
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE,
            value TEXT,
            kind TEXT DEFAULT 'note',
            score REAL DEFAULT 0.0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
        """,
    ),
    (
        "tasks",
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            task_type TEXT DEFAULT 'generic',
            payload TEXT DEFAULT '{}',
            status TEXT DEFAULT 'pending',
            assigned_to TEXT,
            result TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT
        )
        """,
    ),
    (
        "events",
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            detail TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now'))
        )
        """,
    ),
    (
        "setup_runs",
        """
        CREATE TABLE IF NOT EXISTS setup_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            finished_at TEXT DEFAULT (datetime('now')),
            success INTEGER DEFAULT 0,
            report TEXT
        )
        """,
    ),
)

INDEXES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages (conversation_id)",
    "CREATE INDEX IF NOT EXISTS idx_memories_kind ON memories (kind)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status)",
    "CREATE INDEX IF NOT EXISTS idx_events_kind ON events (kind)",
)


class Initializer:
    """Creates the directory layout and the primary SQLite schema."""

    def __init__(self, project_root: Path, dry_run: bool = False) -> None:
        self.root = project_root
        self.dry_run = dry_run

    @property
    def db_path(self) -> Path:
        return self.root / "aura.db"

    def setup_directories(self) -> StepResult:
        created: list[str] = []
        existing: list[str] = []
        for relative in REQUIRED_DIRS:
            path = self.root / relative
            if path.is_dir():
                existing.append(relative)
                continue
            created.append(relative)
            if not self.dry_run:
                try:
                    path.mkdir(parents=True, exist_ok=True)
                except OSError as exc:
                    return StepResult.fail(f"could not create {relative}: {exc}")

        if self.dry_run:
            return StepResult.warn(f"dry-run: would create {len(created)} directories", created=created)
        return StepResult.ok(
            f"{len(created)} created, {len(existing)} already present",
            created=created,
        )

    def setup_databases(self) -> StepResult:
        """Create the core schema. Idempotent: `IF NOT EXISTS` throughout."""
        db = self.db_path
        if self.dry_run:
            return StepResult.warn(f"dry-run: would initialise {db.name}", database=str(db))

        # Pre-existing databases are upgraded in place; SQLite handles the
        # open-migrate-close cycle and `IF NOT EXISTS` makes it safe to repeat.
        try:
            connection = sqlite3.connect(db, timeout=15)
        except sqlite3.Error as exc:
            return StepResult.fail(f"could not open {db.name}: {exc}")

        created: list[str] = []
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            for name, ddl in CORE_TABLES:
                existed = _table_exists(connection, name)
                connection.execute(ddl)
                if not existed:
                    created.append(name)
            for statement in INDEXES:
                connection.execute(statement)
            connection.commit()
        except sqlite3.Error as exc:
            connection.rollback()
            return StepResult.fail(f"schema migration failed: {exc}")
        finally:
            connection.close()

        return StepResult.ok(
            f"{len(created)} new table(s), {len(CORE_TABLES) - len(created)} already present",
            database=str(db),
            created_tables=created,
        )

    def setup_legacy_databases(self) -> StepResult:
        """Touch the other databases ARIA opens, without migrating them.

        These are owned by individual subsystems with their own schemas; setup
        only verifies the file is reachable so a later health check does not
        fail for the wrong reason.
        """
        candidates = [
            self.root / "data" / "aura.db",
            self.root / "ARIA_APP" / "backend" / "memory" / "aria_brain.db",
            self.root / "ARIA_APP" / "backend" / "memory" / "aria_long.db",
        ]
        checked, missing = [], []
        for path in candidates:
            if not path.parent.is_dir():
                missing.append(str(path.relative_to(self.root)))
                continue
            try:
                connection = sqlite3.connect(path, timeout=10)
                connection.execute("PRAGMA quick_check(1)").fetchone()
                connection.close()
                checked.append(str(path.relative_to(self.root)))
            except sqlite3.Error as exc:
                return StepResult.warn(f"could not verify {path.name}: {exc}", database=str(path))

        if missing:
            return StepResult.warn(
                f"{len(missing)} subsystem database(s) not present yet",
                verified=checked,
                missing=missing,
            )
        return StepResult.ok(f"verified {len(checked)} subsystem database(s)", verified=checked)

    def record_run(self, report: dict) -> StepResult:
        """Append this run to `setup_runs` so history survives restarts."""
        import json

        if self.dry_run:
            return StepResult.skip("dry-run")
        try:
            connection = sqlite3.connect(self.db_path, timeout=15)
            connection.execute(
                "INSERT INTO setup_runs (success, report) VALUES (?, ?)",
                (1 if report.get("success") else 0, json.dumps(report, default=str)[:20000]),
            )
            connection.commit()
            connection.close()
        except sqlite3.Error as exc:
            return StepResult.warn(f"could not record run: {exc}")
        return StepResult.ok("run recorded in setup_runs")


def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None
