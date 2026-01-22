def upsert_thread(conn, thread_dict):
    conn.execute(
        """
        INSERT INTO threads (
            source,
            source_thread_id,
            url,
            subreddit,
            title,
            body,
            author,
            created_at_utc,
            last_seen_at_utc,
            last_content_at_utc,
            is_deleted,
            is_removed,
            score,
            num_comments_reported
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (source, source_thread_id) DO UPDATE SET
            url=excluded.url,
            subreddit=excluded.subreddit,
            title=excluded.title,
            body=excluded.body,
            author=excluded.author,
            last_seen_at_utc=excluded.last_seen_at_utc,
            last_content_at_utc=excluded.last_content_at_utc,
            is_deleted=excluded.is_deleted,
            is_removed=excluded.is_removed,
            score=excluded.score,
            num_comments_reported=excluded.num_comments_reported
        """,
        (
            thread_dict["source"],
            thread_dict["source_thread_id"],
            thread_dict.get("url"),
            thread_dict.get("subreddit"),
            thread_dict.get("title"),
            thread_dict.get("body"),
            thread_dict.get("author"),
            thread_dict.get("created_at_utc"),
            thread_dict.get("last_seen_at_utc"),
            thread_dict.get("last_content_at_utc"),
            thread_dict.get("is_deleted"),
            thread_dict.get("is_removed"),
            thread_dict.get("score"),
            thread_dict.get("num_comments_reported"),
        ),
    )
    row = conn.execute(
        """
        SELECT thread_pk
        FROM threads
        WHERE source = ? AND source_thread_id = ?
        """,
        (thread_dict["source"], thread_dict["source_thread_id"]),
    ).fetchone()
    return row["thread_pk"]


def upsert_comments(conn, thread_pk, comment_dicts):
    if not comment_dicts:
        return 0

    payload = []
    for comment in comment_dicts:
        payload.append(
            (
                thread_pk,
                comment["source"],
                comment["source_comment_id"],
                comment.get("parent_source_id"),
                comment.get("author"),
                comment.get("body"),
                comment.get("created_at_utc"),
                comment.get("last_seen_at_utc"),
                comment.get("is_deleted"),
                comment.get("depth"),
                comment.get("permalink"),
            )
        )

    conn.executemany(
        """
        INSERT INTO comments (
            thread_pk,
            source,
            source_comment_id,
            parent_source_id,
            author,
            body,
            created_at_utc,
            last_seen_at_utc,
            is_deleted,
            depth,
            permalink
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (source, source_comment_id) DO UPDATE SET
            thread_pk=excluded.thread_pk,
            parent_source_id=excluded.parent_source_id,
            author=excluded.author,
            body=excluded.body,
            last_seen_at_utc=excluded.last_seen_at_utc,
            is_deleted=excluded.is_deleted,
            depth=excluded.depth,
            permalink=excluded.permalink
        """,
        payload,
    )
    return len(comment_dicts)


def ensure_thread_state(conn, thread_pk, thread_created_at_utc, active_window_days=5):
    row = conn.execute(
        "SELECT thread_pk FROM thread_state WHERE thread_pk = ?",
        (thread_pk,),
    ).fetchone()
    if row is not None:
        return

    active_until_utc = thread_created_at_utc + (active_window_days * 86400)
    conn.execute(
        """
        INSERT INTO thread_state (
            thread_pk,
            watching,
            active_until_utc,
            closed,
            in_area,
            genai_eval_count,
            flagged,
            dismissed
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            thread_pk,
            0,
            active_until_utc,
            0,
            "unknown",
            0,
            0,
            0,
        ),
    )
