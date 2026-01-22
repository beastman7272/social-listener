import os
import sys
import time
import uuid

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP_ROOT = os.path.join(REPO_ROOT, "app")
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

from collectors.reddit_collector import fetch_comments, fetch_threads
from config import load_env_config
from repo.config import (
    get_config_bool,
    get_config_dict,
    get_config_int,
    get_config_list,
    get_config_value,
    parse_config_json,
)
from repo.db import connect
from repo.ingest import ensure_thread_state, upsert_comments, upsert_thread
from repo.migrate import init_db_if_missing
from repo.threads import list_comments_for_thread, list_comments_since
from services.normalize_reddit import normalize_comment, normalize_submission
from services.rules_engine import evaluate_comment, evaluate_thread, infer_location


def _get_subreddits(conn):
    raw_value = get_config_value(conn, "subreddits")
    parsed = parse_config_json(raw_value)
    if isinstance(parsed, list) and parsed:
        return [str(item) for item in parsed if str(item).strip()]

    return ["Atlanta"]


def _get_rule_config(conn):
    return {
        "keywords_include": get_config_list(conn, "keywords_include", []),
        "keywords_intent": get_config_list(conn, "keywords_intent", []),
        "keywords_negative": get_config_list(conn, "keywords_negative", []),
        "include_unknown_location": get_config_bool(
            conn, "include_unknown_location", True
        ),
        "active_window_days": get_config_int(conn, "active_window_days", 5),
        "geo_service_area": get_config_list(conn, "geo_service_area", []),
        "subreddit_geo_map": get_config_dict(conn, "subreddit_geo_map", {}),
        "geo_out_of_area": get_config_list(conn, "geo_out_of_area", []),
    }


def _validate_reddit_config(config):
    required = [
        "REDDIT_CLIENT_ID",
        "REDDIT_CLIENT_SECRET",
        "REDDIT_USER_AGENT",
    ]
    missing = [key for key in required if not config.get(key)]
    return missing


def _run_rules_for_threads(conn, run_id, thread_pks, rules_config):
    now = int(time.time())
    rule_hits_count = 0
    include_unknown = rules_config.get("include_unknown_location", True)
    active_window_days = rules_config.get("active_window_days", 5)

    for thread_pk in thread_pks:
        thread = conn.execute(
            "SELECT * FROM threads WHERE thread_pk = ?",
            (thread_pk,),
        ).fetchone()
        thread_state = conn.execute(
            "SELECT * FROM thread_state WHERE thread_pk = ?",
            (thread_pk,),
        ).fetchone()
        if thread is None or thread_state is None:
            continue
        if thread_state["closed"] == 1 or thread_state["dismissed"] == 1:
            continue

        last_rule_check = thread_state["last_rule_check_at_utc"]
        if last_rule_check:
            comments = list_comments_since(conn, thread_pk, last_rule_check)
            if not comments:
                continue
            hits = []
            for comment in comments:
                hits.extend(evaluate_comment(comment, rules_config))
        else:
            comments = list_comments_for_thread(conn, thread_pk)
            hits = evaluate_thread(thread, comments, rules_config)

        in_area, evidence = infer_location(thread, comments, rules_config)
        has_negative = any(hit["hit_type"] == "negative" for hit in hits)
        has_service = any(hit["hit_type"] == "keyword" for hit in hits)
        has_intent = any(hit["hit_type"] == "phrase" for hit in hits)

        should_watch = (not has_negative) and has_service and has_intent
        if in_area == "false":
            should_watch = False
        elif in_area == "unknown" and not include_unknown:
            should_watch = False

        if hits:
            payload = []
            for hit in hits:
                payload.append(
                    (
                        run_id,
                        thread_pk,
                        hit.get("comment_pk"),
                        hit["hit_type"],
                        hit["matched_term"],
                        hit["match_context"],
                        now,
                    )
                )
            conn.executemany(
                """
                INSERT INTO rule_hits (
                    run_id,
                    thread_pk,
                    comment_pk,
                    hit_type,
                    matched_term,
                    match_context,
                    created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                payload,
            )
            rule_hits_count += len(payload)

        last_seen_comment = None
        if comments:
            last_seen_comment = max(
                comment["created_at_utc"]
                for comment in comments
                if comment["created_at_utc"] is not None
            )

        conn.execute(
            """
            UPDATE thread_state
            SET last_rule_check_at_utc = ?,
                last_seen_comment_at_utc = ?,
                in_area = ?,
                location_evidence = ?
            WHERE thread_pk = ?
            """,
            (now, last_seen_comment, in_area, evidence, thread_pk),
        )

        if (
            should_watch
            and thread_state["watching"] != 1
            and thread_state["dismissed"] != 1
        ):
            active_until_utc = thread["created_at_utc"] + (active_window_days * 86400)
            conn.execute(
                """
                UPDATE thread_state
                SET watching = 1,
                    active_until_utc = ?
                WHERE thread_pk = ?
                """,
                (active_until_utc, thread_pk),
            )

    return rule_hits_count


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
        from collectors.reddit_client import build_reddit_client

        subreddits = _get_subreddits(conn)
        rules_config = _get_rule_config(conn)
        active_window_days = rules_config["active_window_days"]

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
        rule_hits_total = 0
        ingested_thread_pks = []

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
            ingested_thread_pks.append(thread_pk)

        rule_hits_total = _run_rules_for_threads(
            conn, run_id, ingested_thread_pks, rules_config
        )

        conn.execute(
            """
            UPDATE runs
            SET ended_at_utc = ?,
                status = ?,
                threads_fetched = ?,
                comments_fetched = ?,
                threads_new = ?,
                threads_updated = ?,
                rule_hits = ?
            WHERE run_id = ?
            """,
            (
                int(time.time()),
                "success",
                threads_fetched,
                comments_fetched,
                threads_new,
                threads_updated,
                rule_hits_total,
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
