#!/usr/bin/env python3
"""
AURA - Start Services (PocketBase-style)
Levanta servidor FastAPI + inicializa SQLite y ChromaDB en un solo comando.
"""

import os
import sys
import sqlite3
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "AURA_Core" / "aura_local.db"
CHROMA_DIR = BASE_DIR / "AURA_Core" / "chroma_db"


def init_sqlite():
    """Inicializa SQLite con tablas base si no existen."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            role TEXT,
            content TEXT,
            ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(session_id) REFERENCES sessions(id)
        )
        """)
    conn.commit()
    conn.close()
    print(f"[OK] SQLite listo en {DB_PATH}")


def init_chromadb():
    """Inicializa directorio ChromaDB (vector store)."""
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    count = len(list(CHROMA_DIR.iterdir()))
    print(f"[OK] ChromaDB lista en {CHROMA_DIR} (archivos: {count})")


def start_fastapi():
    """Lanza uvicorn contra aura_api.py."""
    print("[INFO] Levantando FastAPI en http://0.0.0.0:8000 ...")
    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "aura_api:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
                "--log-level",
                "info",
            ],
            cwd=str(BASE_DIR),
            check=False,
        )
    except KeyboardInterrupt:
        print("\n[INFO] Servidor detenido por usuario.")
    except Exception as e:
        print(f"[ERROR] No se pudo levantar FastAPI: {e}")


def main():
    print("=== AURA Start Services ===")
    init_sqlite()
    init_chromadb()
    start_fastapi()


if __name__ == "__main__":
    main()
