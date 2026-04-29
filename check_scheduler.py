import sqlite3
conn = sqlite3.connect('logs/events.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:", [t[0] for t in cur.fetchall()])

# Check schema
cur.execute("PRAGMA table_info(events)")
print("\nSchema:", [col[1] for col in cur.fetchall()])

# Check for scheduler events
try:
    cur.execute("SELECT * FROM events WHERE event_type LIKE '%scheduler%' OR event_type LIKE '%touch%' ORDER BY ts DESC LIMIT 10")
    rows = cur.fetchall()
    print(f"\nScheduler/Touch events: {len(rows)}")
    for row in rows:
        print(row)
except Exception as e:
    print(f"Error: {e}")

conn.close()
