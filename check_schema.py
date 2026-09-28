import sqlite3
conn = sqlite3.connect('aura.db')
cursor = conn.cursor()
tables = ['messages', 'memories', 'tasks', 'improvements', 'chat_history', 'neural_state', 'semantic_memory', 'sessions', 'log_entries', 'conversations']
for t in tables:
    try:
        cursor.execute(f"PRAGMA table_info({t})")
        cols = cursor.fetchall()
        print(f"\n=== {t} ===")
        for c in cols:
            print(f"  {c[1]} {c[2]} {'NOT NULL' if c[3] else ''} {'DEFAULT ' + str(c[4]) if c[4] is not None else ''} {'PK' if c[5] else ''}")
    except Exception as e:
        print(f"\n=== {t} === ERROR: {e}")