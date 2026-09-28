import sqlite3
import os
db_path = r'C:\Users\User\Downloads\AURA\aura.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('Tables:', [t[0] for t in tables])
for t in tables:
    cursor.execute(f'PRAGMA table_info({t[0]})')
    cols = cursor.fetchall()
    print(f'\n{t[0]}:')
    for c in cols:
        print(f'  {c[1]} {c[2]}')
conn.close()