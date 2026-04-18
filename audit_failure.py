import sqlite3
import json

conn = sqlite3.connect("logs/events.db")

query_id = "7c527254-7d83-4c67-b1af-9d2489222ccd"

print(f"\n=== FAILURE DETAILS FOR query_id={query_id} ===\n")

for row in conn.execute("""
    SELECT event_type, ts, payload
    FROM events
    WHERE query_id = ?
    ORDER BY ts ASC
""", (query_id,)):
    event_type, ts, payload = row
    print(f"\n[{event_type}] ts={ts}")
    payload_dict = json.loads(payload)
    print(json.dumps(payload_dict, indent=2))
