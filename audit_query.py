import sqlite3
import json

conn = sqlite3.connect("logs/events.db")

query = "What is Eco company?"

print(f"\n=== AUDITING: {query} ===\n")

# Get all events for this query
print("=== ALL EVENTS FOR THIS QUERY ===")
for row in conn.execute("""
    SELECT event_type, query_id, ts, payload
    FROM events
    WHERE json_extract(payload, '$.query') = ?
    ORDER BY ts ASC
""", (query,)):
    event_type, query_id, ts, payload = row
    print(f"\n[{event_type}] query_id={query_id} ts={ts}")
    print(f"  payload: {payload[:500]}")

# Get the specific query_id for this query
query_id = conn.execute("""
    SELECT query_id
    FROM events
    WHERE json_extract(payload, '$.query') = ?
    LIMIT 1
""", (query,)).fetchone()

if query_id:
    query_id = query_id[0]
    print(f"\n=== FULL TRACE FOR query_id={query_id} ===\n")
    
    for row in conn.execute("""
        SELECT event_type, ts, payload
        FROM events
        WHERE query_id = ?
        ORDER BY ts ASC
    """, (query_id,)):
        event_type, ts, payload = row
        print(f"\n[{event_type}] ts={ts}")
        print(f"  payload: {payload[:800]}")
else:
    print("No events found for this query")
