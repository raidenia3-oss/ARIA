import sqlite3, os

path = r'C:\Users\User\AppData\Local\Google\Chrome\User Data\Default\Network\Cookies'
try:
    conn = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    cur = conn.cursor()
    cur.execute("SELECT name, value, host_key FROM cookies WHERE host_key LIKE '%youtube%' LIMIT 10")
    rows = cur.fetchall()
    print('YouTube cookies found:', len(rows))
    for r in rows:
        print('  ', r[0], '=', r[1][:40], '|', r[2])
    conn.close()
except Exception as e:
    print('SQLITE READ ERROR:', str(e)[:300])
