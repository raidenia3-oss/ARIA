import json
from datetime import datetime
from pathlib import Path

data_dir = Path("ARIA_v4/AURA_APP/data")
data_dir.mkdir(parents=True, exist_ok=True)

profile = {
    "name": "Usuario",
    "language": "es",
    "timezone": "America/Lima",
    "preferences": {"auto_adapt": True, "proactive_suggestions": True},
    "behavior_patterns": [],
    "favorite_commands": [],
    "learning_style": "visual",
    "created": datetime.now().isoformat(),
    "last_active": None,
    "active_hours": [],
    "total_interactions": 0,
}

with open(data_dir / "user_profile.json", "w") as f:
    json.dump(profile, f, indent=2, ensure_ascii=False)

empty_files = [
    ("short_term.json", []),
    ("long_term.json", []),
    ("learning_history.json", []),
    ("behavior_patterns.json", {"interactions": [], "hourly": {}, "commands": {}, "intents": {}}),
    ("context_patterns.json", {}),
    ("proactive_tasks.json", {"tasks": [], "completed": []}),
    ("adaptive_history.json", []),
    ("insights.json", []),
    ("error_log.json", {"errors": [], "recovery_count": 0, "last_recovery": None}),
]

for name, content in empty_files:
    p = data_dir / name
    if not p.exists():
        with open(p, "w") as f:
            json.dump(content, f, indent=2, ensure_ascii=False)

# Create minimal SQLite DB
db_path = data_dir / "cerebro.db"
if not db_path.exists():
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    conn.execute("""CREATE TABLE IF NOT EXISTS memories (
        id TEXT PRIMARY KEY,
        content TEXT,
        category TEXT DEFAULT 'general',
        priority REAL DEFAULT 0.5,
        timestamp TEXT,
        tags TEXT DEFAULT '[]',
        context TEXT DEFAULT '',
        importance REAL DEFAULT 0.5,
        access_count INTEGER DEFAULT 0,
        last_accessed TEXT DEFAULT ''
    )""")
    conn.commit()
    conn.close()

print("Datos inicializados en ARIA_v4/AURA_APP/data/")
