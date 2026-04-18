import sqlite3

conn = sqlite3.connect("logs/events.db")

print("\n=== RETRIEVAL MISS FAILURES ===")
for row in conn.execute("""
    SELECT json_extract(payload, '$.query'),
           json_extract(payload, '$.failure_type')
    FROM events
    WHERE event_type = 'failure'
      AND json_extract(payload, '$.failure_type') = 'retrieval_miss'
    ORDER BY ts ASC
"""):
    print(row)

print("\n=== ALL FAILURES ===")
for row in conn.execute("""
    SELECT json_extract(payload, '$.query'),
           json_extract(payload, '$.failure_type')
    FROM events
    WHERE event_type = 'failure'
    ORDER BY ts ASC
"""):
    print(row)
