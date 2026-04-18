import sqlite3
conn = sqlite3.connect("logs/events.db")
for row in conn.execute("SELECT event_type, COUNT(*) FROM events GROUP BY event_type ORDER BY event_type"):
    print(row)
