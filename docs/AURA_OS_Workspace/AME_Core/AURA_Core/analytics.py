import sqlite3
import time
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "aura_metrics.db"

# Tarifas aproximadas por 1M de tokens (USD). LM Studio = 0 (local).
PRICING = {
    "groq-whisper": {"input": 0.0, "output": 0.0},
    "gemini-whisper": {"input": 0.0, "output": 0.0},
    "openrouter": {"input": 0.5, "output": 1.0},
    "lm-studio-local": {"input": 0.0, "output": 0.0},
    "mistralai/mistral-small-3.1-24b-instruct:free": {"input": 0.0, "output": 0.0},
}

DEFAULT_PRICING = {"input": 0.2, "output": 0.4}


def _get_price(provider: str, model: str) -> dict:
    key = provider.lower()
    if key in PRICING:
        return PRICING[key]
    if model and model.lower() in PRICING:
        return PRICING[model.lower()]
    return DEFAULT_PRICING


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            provider TEXT,
            model TEXT,
            latency_ms REAL,
            input_tokens INTEGER,
            output_tokens INTEGER,
            cost_usd REAL,
            endpoint TEXT
        )
        """)
    conn.commit()
    conn.close()


def record(
    provider: str,
    model: str,
    latency_ms: float,
    input_tokens: int,
    output_tokens: int,
    endpoint: str,
):
    price = _get_price(provider, model)
    cost = (input_tokens * price["input"] + output_tokens * price["output"]) / 1_000_000
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO metrics (provider, model, latency_ms, input_tokens, output_tokens, cost_usd, endpoint)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            provider or "",
            model or "",
            latency_ms,
            input_tokens,
            output_tokens,
            cost,
            endpoint or "",
        ),
    )
    conn.commit()
    conn.close()


def dashboard() -> dict:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT SUM(cost_usd) FROM metrics")
    total_cost = cur.fetchone()[0] or 0.0
    cur.execute("""
        SELECT provider, AVG(latency_ms) as avg_latency
        FROM metrics
        WHERE provider != ''
        GROUP BY provider
        """)
    rows = cur.fetchall()
    avg_by_provider = {r[0]: r[1] for r in rows}
    cur.execute("""
        SELECT model, COUNT(*) as cnt
        FROM metrics
        WHERE model != ''
        GROUP BY model
        ORDER BY cnt DESC
        LIMIT 5
        """)
    top_models = [{"model": r[0], "count": r[1]} for r in cur.fetchall()]
    conn.close()
    return {
        "total_cost_usd": round(total_cost, 4),
        "avg_latency_by_provider": avg_by_provider,
        "top_models": top_models,
    }
