from .db import connect


def list_flagged_threads(limit=50, offset=0):
    conn = connect()
    try:
        rows = conn.execute(
            """
            SELECT
                t.*,
                ts.watching,
                ts.active_until_utc,
                ts.closed,
                ts.in_area,
                ts.location_confidence,
                ts.flagged,
                ts.flagged_at_utc,
                ts.dismissed,
                ts.snoozed_until_utc,
                dr.draft_text AS latest_draft_text,
                dr.status AS latest_draft_status
            FROM threads AS t
            JOIN thread_state AS ts ON ts.thread_pk = t.thread_pk
            LEFT JOIN draft_responses AS dr
                ON dr.draft_pk = (
                    SELECT draft_pk
                    FROM draft_responses
                    WHERE thread_pk = t.thread_pk
                    ORDER BY updated_at_utc DESC, created_at_utc DESC
                    LIMIT 1
                )
            WHERE ts.flagged = 1 AND (ts.dismissed IS NULL OR ts.dismissed = 0)
            ORDER BY COALESCE(ts.flagged_at_utc, t.last_content_at_utc, t.created_at_utc) DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
        return rows
    finally:
        conn.close()


def list_recent_threads(limit=50):
    conn = connect()
    try:
        rows = conn.execute(
            """
            SELECT
                t.*,
                ts.watching,
                ts.in_area,
                ts.last_rule_check_at_utc
            FROM threads AS t
            LEFT JOIN thread_state AS ts ON ts.thread_pk = t.thread_pk
            ORDER BY COALESCE(last_content_at_utc, created_at_utc) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return rows
    finally:
        conn.close()


def list_comments_for_thread(conn, thread_pk):
    return conn.execute(
        """
        SELECT *
        FROM comments
        WHERE thread_pk = ?
        ORDER BY created_at_utc ASC
        """,
        (thread_pk,),
    ).fetchall()


def list_comments_since(conn, thread_pk, since_utc):
    return conn.execute(
        """
        SELECT *
        FROM comments
        WHERE thread_pk = ? AND created_at_utc > ?
        ORDER BY created_at_utc ASC
        """,
        (thread_pk, since_utc),
    ).fetchall()


def get_comment_pk_by_source_id(conn, thread_pk, source_comment_id):
    row = conn.execute(
        """
        SELECT comment_pk
        FROM comments
        WHERE thread_pk = ? AND source_comment_id = ?
        """,
        (thread_pk, source_comment_id),
    ).fetchone()
    return row["comment_pk"] if row else None


def list_rule_hits_for_run(conn, thread_pk, run_id):
    return conn.execute(
        """
        SELECT *
        FROM rule_hits
        WHERE thread_pk = ? AND run_id = ?
        ORDER BY created_at_utc DESC
        """,
        (thread_pk, run_id),
    ).fetchall()


def get_comment_source_id(conn, comment_pk):
    row = conn.execute(
        """
        SELECT source_comment_id
        FROM comments
        WHERE comment_pk = ?
        """,
        (comment_pk,),
    ).fetchone()
    return row["source_comment_id"] if row else None


def get_thread_detail(thread_pk):
    conn = connect()
    try:
        thread = conn.execute(
            "SELECT * FROM threads WHERE thread_pk = ?",
            (thread_pk,),
        ).fetchone()
        if thread is None:
            return None

        thread_state = conn.execute(
            "SELECT * FROM thread_state WHERE thread_pk = ?",
            (thread_pk,),
        ).fetchone()

        comments = conn.execute(
            """
            SELECT *
            FROM comments
            WHERE thread_pk = ?
            ORDER BY created_at_utc ASC
            """,
            (thread_pk,),
        ).fetchall()

        latest_draft = conn.execute(
            """
            SELECT *
            FROM draft_responses
            WHERE thread_pk = ?
            ORDER BY updated_at_utc DESC, created_at_utc DESC
            LIMIT 1
            """,
            (thread_pk,),
        ).fetchone()

        latest_genai_eval = conn.execute(
            """
            SELECT *
            FROM genai_evals
            WHERE thread_pk = ?
            ORDER BY created_at_utc DESC
            LIMIT 1
            """,
            (thread_pk,),
        ).fetchone()

        detections = conn.execute(
            """
            SELECT *
            FROM detections
            WHERE thread_pk = ?
            ORDER BY created_at_utc DESC
            """,
            (thread_pk,),
        ).fetchall()

        rule_hits = conn.execute(
            """
            SELECT *
            FROM rule_hits
            WHERE thread_pk = ?
            ORDER BY created_at_utc DESC
            """,
            (thread_pk,),
        ).fetchall()

        return {
            "thread": thread,
            "thread_state": thread_state,
            "comments": comments,
            "latest_draft": latest_draft,
            "latest_genai_eval": latest_genai_eval,
            "detections": detections,
            "rule_hits": rule_hits,
        }
    finally:
        conn.close()
