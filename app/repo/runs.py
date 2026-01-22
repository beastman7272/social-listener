from .db import connect


def list_recent_runs(limit=20):
    conn = connect()
    try:
        rows = conn.execute(
            """
            SELECT *
            FROM runs
            ORDER BY started_at_utc DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return rows
    finally:
        conn.close()
