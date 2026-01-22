import time

from .db import connect


def save_edited_draft(thread_pk, draft_text):
    conn = connect()
    try:
        thread = conn.execute(
            "SELECT thread_pk FROM threads WHERE thread_pk = ?",
            (thread_pk,),
        ).fetchone()
        if thread is None:
            return False

        latest = conn.execute(
            """
            SELECT draft_version, genai_eval_pk
            FROM draft_responses
            WHERE thread_pk = ?
            ORDER BY updated_at_utc DESC, created_at_utc DESC
            LIMIT 1
            """,
            (thread_pk,),
        ).fetchone()

        draft_version = 1
        genai_eval_pk = None
        if latest:
            draft_version = (latest["draft_version"] or 0) + 1
            genai_eval_pk = latest["genai_eval_pk"]

        now = int(time.time())
        conn.execute(
            """
            INSERT INTO draft_responses (
                thread_pk,
                genai_eval_pk,
                draft_text,
                draft_version,
                status,
                created_at_utc,
                updated_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                thread_pk,
                genai_eval_pk,
                draft_text,
                draft_version,
                "edited",
                now,
                now,
            ),
        )
        conn.commit()
        return True
    finally:
        conn.close()
