import json
import sys
import time
import uuid

from app.collectors.reddit_client import build_reddit_client
from app.collectors.reddit_collector import fetch_comments, fetch_threads
from app.config import load_env_config
from app.repo.config import get_config_value, parse_config_json
from app.repo.db import connect
from app.repo.ingest import ensure_thread_state, upsert_comments, upsert_thread
from app.repo.migrate import init_db_if_missing
from app.services.normalize_reddit import normalize_comment, normalize_submission


def _get_subreddits(conn):
    raw_value = get_config_value(conn, "subreddits")
    parsed = parse_config_json(raw_value)
    if isinstance(parsed, list) and parsed:
        return [str(item) for item in parsed if str(item).strip()]

    return ["Atlanta"]


def _get_active_window_days(conn):
    raw_value = get_config_value(conn, "active_window_days")
    parsed = parse_config_json(raw_value)
    if isinstance(parsed, int):
        return parsed
    return 5


def _validate_reddit_config(config):
    required = [
        "REDDIT_CLIENT_ID",
        "REDDIT_CLIENT_SECRET",
        "REDDIT_USER_AGENT",
    ]
    missing = [key for key in required if not config.get(key)]
    return missing


def main():
    config = load_env_config()
    missing = _validate_reddit_config(config)
    if missing:
        print(
            "Missing required Reddit credentials: "
            + ", ".join(missing)
            + ". Set them in .env or environment variables."
        )
        return 1

    init_db_if_missing()
    conn = connect()
    run_id = str(uuid.uuid4())
    started_at = int(time.time())

    try:
        subreddits = _get_subreddits(conn)
        active_window_days = _get_active_window_days(conn)

        conn.execute(
            """
            INSERT INTO runs (
                run_id,
                started_at_utc,
                status,
                source,
                threads_fetched,
                comments_fetched,
                threads_new,
                threads_updated,
                rule_hits,
                genai_calls,
                threads_flagged
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                started_at,
                "running",
                "reddit",
                0,
                0,
                0,
                0,
                0,
                0,
                0,
            ),
        )
        conn.commit()

        reddit = build_reddit_client(config)
        submissions = fetch_threads(reddit, subreddits, limit=25)

        threads_fetched = 0
        comments_fetched = 0
        threads_new = 0
        threads_updated = 0

        for submission in submissions:
            threads_fetched += 1
            thread_dict = normalize_submission(submission)
            existing = conn.execute(
                """
                SELECT thread_pk
                FROM threads
                WHERE source = ? AND source_thread_id = ?
                """,
                (thread_dict["source"], thread_dict["source_thread_id"]),
            ).fetchone()

            thread_pk = upsert_thread(conn, thread_dict)
            if existing is None:
                threads_new += 1
            else:
                threads_updated += 1

            ensure_thread_state(
                conn,
                thread_pk,
                thread_dict["created_at_utc"],
                active_window_days=active_window_days,
            )

            comment_rows = fetch_comments(submission)
            normalized_comments = [
                normalize_comment(comment, thread_pk, thread_dict["source_thread_id"])
                for comment in comment_rows
            ]
            comments_fetched += upsert_comments(conn, thread_pk, normalized_comments)

        conn.execute(
            """
            UPDATE runs
            SET ended_at_utc = ?,
                status = ?,
                threads_fetched = ?,
                comments_fetched = ?,
                threads_new = ?,
                threads_updated = ?
            WHERE run_id = ?
            """,
            (
                int(time.time()),
                "success",
                threads_fetched,
                comments_fetched,
                threads_new,
                threads_updated,
                run_id,
            ),
        )
        conn.commit()
    except Exception as exc:
        conn.execute(
            """
            UPDATE runs
            SET ended_at_utc = ?,
                status = ?,
                error_summary = ?
            WHERE run_id = ?
            """,
            (int(time.time()), "failed", str(exc), run_id),
        )
        conn.commit()
        print(f"Ingestion failed: {exc}")
        return 1
    finally:
        conn.close()

    if subreddits == ["Atlanta"]:
        print("Using placeholder subreddits list: ['Atlanta'].")

    print("Ingestion complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
