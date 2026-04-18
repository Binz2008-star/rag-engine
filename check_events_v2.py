import sqlite3


DB_PATH = "logs/events.db"


def scalar(conn: sqlite3.Connection, sql: str) -> int | float | None:
    row = conn.execute(sql).fetchone()
    return row[0] if row else None


def print_rows(conn: sqlite3.Connection, sql: str) -> None:
    for row in conn.execute(sql):
        print(row)


def main() -> None:
    conn = sqlite3.connect(DB_PATH)

    route_total = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM events
        WHERE event_type = 'route_decision'
        """,
    ) or 0
    generation_total = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM events
        WHERE event_type = 'generation_result'
        """,
    ) or 0
    failure_total = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM events
        WHERE event_type = 'failure'
        """,
    ) or 0
    query_completed_total = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM events
        WHERE event_type = 'query_completed'
        """,
    ) or 0
    query_failed_total = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM events
        WHERE event_type = 'query_failed'
        """,
    ) or 0
    retrieval_miss_total = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM events
        WHERE event_type = 'failure'
          AND json_extract(payload, '$.failure_type') = 'retrieval_miss'
        """,
    ) or 0
    hallucination_total = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM events
        WHERE event_type = 'failure'
          AND json_extract(payload, '$.failure_type') = 'hallucination'
        """,
    ) or 0
    corpus_missing_total = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM events
        WHERE event_type = 'failure'
          AND json_extract(payload, '$.failure_type') = 'corpus_missing'
        """,
    ) or 0

    low_conf_count = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM events
        WHERE event_type = 'route_decision'
          AND json_extract(payload, '$.confidence') IS NOT NULL
          AND CAST(json_extract(payload, '$.confidence') AS REAL) < 0.6
        """,
    ) or 0

    query_received_total = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM events
        WHERE event_type = 'query_received'
        """,
    ) or 0
    downstream_query_ids_total = scalar(
        conn,
        """
        SELECT COUNT(DISTINCT query_id)
        FROM events
        WHERE event_type IN ('route_decision', 'retrieval_result', 'generation_result', 'failure', 'query_completed', 'query_failed')
        """,
    ) or 0
    terminal_query_ids_total = scalar(
        conn,
        """
        SELECT COUNT(DISTINCT query_id)
        FROM events
        WHERE event_type IN ('query_completed', 'query_failed')
        """,
    ) or 0

    method_missing_count = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM events
        WHERE event_type = 'route_decision'
          AND json_type(payload, '$.intent_method') IS NULL
        """,
    ) or 0
    method_null_count = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM events
        WHERE event_type = 'route_decision'
          AND json_type(payload, '$.intent_method') = 'null'
        """,
    ) or 0
    intent_missing_count = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM events
        WHERE event_type = 'route_decision'
          AND json_type(payload, '$.intent') IS NULL
        """,
    ) or 0
    confidence_missing_count = scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM events
        WHERE event_type = 'route_decision'
          AND json_type(payload, '$.confidence') IS NULL
        """,
    ) or 0

    print("\n=== EVENT COUNTS ===")
    print_rows(
        conn,
        """
        SELECT event_type, COUNT(*)
        FROM events
        GROUP BY event_type
        ORDER BY event_type
        """,
    )

    print("\n=== FAILURE TYPES ===")
    print_rows(
        conn,
        """
        SELECT COALESCE(json_extract(payload, '$.failure_type'), '__MISSING_OR_NULL__'), COUNT(*)
        FROM events
        WHERE event_type = 'failure'
        GROUP BY COALESCE(json_extract(payload, '$.failure_type'), '__MISSING_OR_NULL__')
        ORDER BY COUNT(*) DESC
        """,
    )
    denom = generation_total if generation_total > 0 else 1
    print(f"total_failures: {failure_total}")
    print(f"completed_generations: {generation_total}")
    print(f"query_completed_total: {query_completed_total}")
    print(f"query_failed_total: {query_failed_total}")
    print(f"failure_rate_over_completed_generations: {failure_total / denom:.4f}")
    print(f"retrieval_miss_rate_over_completed_generations: {retrieval_miss_total / denom:.4f}")
    print(f"hallucination_rate_over_completed_generations: {hallucination_total / denom:.4f}")
    print(f"corpus_missing_rate_over_completed_generations: {corpus_missing_total / denom:.4f}")

    print("\n=== LOW CONFIDENCE ROUTES (<0.6) ===")
    print(f"low_conf_count: {low_conf_count}")
    print(f"route_total: {route_total}")
    if route_total > 0:
        print(f"low_conf_rate: {low_conf_count / route_total:.4f}")

    print("\n=== SAMPLE FAILURES ===")
    print_rows(
        conn,
        """
        SELECT json_extract(payload, '$.query'),
               json_extract(payload, '$.failure_type')
        FROM events
        WHERE event_type = 'failure'
        ORDER BY ts ASC
        LIMIT 10
        """,
    )

    print("\n=== ROUTE METHOD BREAKDOWN ===")
    print_rows(
        conn,
        """
        SELECT
          CASE
            WHEN json_type(payload, '$.intent_method') IS NULL THEN '__MISSING__'
            WHEN json_type(payload, '$.intent_method') = 'null' THEN '__NULL__'
            ELSE json_extract(payload, '$.intent_method')
          END AS intent_method,
          COUNT(*)
        FROM events
        WHERE event_type = 'route_decision'
        GROUP BY
          CASE
            WHEN json_type(payload, '$.intent_method') IS NULL THEN '__MISSING__'
            WHEN json_type(payload, '$.intent_method') = 'null' THEN '__NULL__'
            ELSE json_extract(payload, '$.intent_method')
          END
        ORDER BY COUNT(*) DESC
        """,
    )

    print("\n=== AVG CONFIDENCE BY INTENT ===")
    print_rows(
        conn,
        """
        SELECT
          COALESCE(json_extract(payload, '$.intent'), '__MISSING__') AS intent,
          ROUND(AVG(CAST(json_extract(payload, '$.confidence') AS REAL)), 4) AS avg_confidence,
          COUNT(*) AS n
        FROM events
        WHERE event_type = 'route_decision'
          AND json_extract(payload, '$.confidence') IS NOT NULL
        GROUP BY COALESCE(json_extract(payload, '$.intent'), '__MISSING__')
        ORDER BY n DESC
        """,
    )

    print("\n=== PIPELINE COMPLETION GAPS ===")
    print(f"query_received_total: {query_received_total}")
    print(f"distinct_downstream_query_ids: {downstream_query_ids_total}")
    print(f"distinct_terminal_query_ids: {terminal_query_ids_total}")
    print("missing_query_ids:")
    missing_rows = conn.execute(
        """
        SELECT q.query_id,
               json_extract(q.payload, '$.query')
        FROM events AS q
        WHERE q.event_type = 'query_received'
          AND q.query_id IN (
            SELECT query_id
            FROM events
            WHERE event_type = 'query_received'
            EXCEPT
            SELECT query_id
            FROM events
            WHERE event_type IN ('route_decision', 'retrieval_result', 'generation_result', 'failure')
          )
        ORDER BY q.ts ASC
        """
    ).fetchall()
    if not missing_rows:
        print("none")
    else:
        for row in missing_rows:
            print(row)

    print("\nmissing_terminal_query_ids:")
    missing_terminal_rows = conn.execute(
        """
        SELECT q.query_id,
               json_extract(q.payload, '$.query')
        FROM events AS q
        WHERE q.event_type = 'query_received'
          AND q.query_id IN (
            SELECT query_id
            FROM events
            WHERE event_type = 'query_received'
            EXCEPT
            SELECT query_id
            FROM events
            WHERE event_type IN ('query_completed', 'query_failed')
          )
        ORDER BY q.ts ASC
        """
    ).fetchall()
    if not missing_terminal_rows:
        print("none")
    else:
        for row in missing_terminal_rows:
            print(row)

    print("\n=== WARNINGS ===")
    warnings: list[str] = []
    if method_missing_count > 0 or method_null_count > 0 or intent_missing_count > 0 or confidence_missing_count > 0:
        warnings.append("WARNING: mixed legacy/new event rows detected; some observability fields are incomplete.")
    if method_missing_count > 0:
        warnings.append(f"intent_method missing in route rows: {method_missing_count}")
    if method_null_count > 0:
        warnings.append(f"intent_method null in route rows: {method_null_count}")
    if intent_missing_count > 0:
        warnings.append(f"intent missing in route rows: {intent_missing_count}")
    if confidence_missing_count > 0:
        warnings.append(f"confidence missing in route rows: {confidence_missing_count}")
    if query_received_total != downstream_query_ids_total:
        warnings.append(
            f"query pipeline gap detected: query_received={query_received_total}, downstream_distinct_query_ids={downstream_query_ids_total}"
        )
    if query_received_total != terminal_query_ids_total:
        warnings.append(
            f"terminal event gap detected: query_received={query_received_total}, terminal_distinct_query_ids={terminal_query_ids_total}"
        )

    if warnings:
        for warning in warnings:
            print(warning)
    else:
        print("No warnings.")


if __name__ == "__main__":
    main()
