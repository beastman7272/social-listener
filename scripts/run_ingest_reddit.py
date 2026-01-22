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
from repo.genai import insert_detections, insert_draft_response, insert_genai_eval
from repo.migrate import init_db_if_missing
from repo.threads import (
    get_comment_pk_by_source_id,
    get_comment_source_id,
    list_comments_for_thread,
    list_comments_since,
    list_rule_hits_for_run,
)
from services.normalize_reddit import normalize_comment, normalize_submission
from services.genai_evaluator import (
    MODEL_NAME,
    PROMPT_VERSION,
    build_genai_payload,
    call_genai,
)
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


def _get_genai_config(conn):
    return {
        "max_genai_evals_per_thread": get_config_int(
            conn, "max_genai_evals_per_thread", 5
        ),
        "genai_cooldown_minutes": get_config_int(
            conn, "genai_cooldown_minutes", 120
        ),
        "delta_min_new_comments": get_config_int(
            conn, "delta_min_new_comments", 1
        ),
        "max_delta_comments_sent": get_config_int(
            conn, "max_delta_comments_sent", 25
        ),
        "business_context": get_config_dict(
            conn,
            "business_context",
            {
                "service": "local service",
                "service_area": "unspecified",
                "tone": "helpful",
            },
        ),
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
    thread_results = {}

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
                thread_results[thread_pk] = {
                    "positive_hit": False,
                    "rule_hit_count": 0,
                    "in_area": thread_state["in_area"],
                }
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

        positive_hit = (not has_negative) and has_service and has_intent
        should_watch = positive_hit
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

        thread_results[thread_pk] = {
            "positive_hit": positive_hit,
            "rule_hit_count": len(hits),
            "in_area": in_area,
        }

    return rule_hits_count, thread_results


def _select_delta_comments(comments, thread_author, max_count):
    op_comments = [
        comment
        for comment in comments
        if thread_author and comment["author"] == thread_author
    ]
    other_comments = [
        comment
        for comment in comments
        if not (thread_author and comment["author"] == thread_author)
    ]
    op_comments.sort(key=lambda row: row["created_at_utc"] or 0, reverse=True)
    other_comments.sort(key=lambda row: row["created_at_utc"] or 0, reverse=True)
    selected = op_comments + other_comments
    selected = selected[:max_count]
    selected.sort(key=lambda row: row["created_at_utc"] or 0)
    return selected


def _build_delta_payload_comments(comments):
    payload = []
    for comment in comments:
        payload.append(
            {
                "comment_id": comment["source_comment_id"],
                "author": comment["author"],
                "created_at": comment["created_at_utc"],
                "text": comment["body"],
            }
        )
    return payload


def _build_rule_evidence(conn, thread_pk, run_id):
    hits = list_rule_hits_for_run(conn, thread_pk, run_id)
    payload = []
    for hit in hits:
        comment_id = None
        if hit["comment_pk"] is not None:
            comment_id = get_comment_source_id(conn, hit["comment_pk"])
        payload.append(
            {
                "matched_term": hit["matched_term"],
                "hit_type": hit["hit_type"],
                "match_context": hit["match_context"],
                "comment_id": comment_id,
            }
        )
    return payload


def _run_genai_for_threads(
    conn, run_id, thread_pks, rules_config, genai_config, api_key, rule_results
):
    now = int(time.time())
    genai_calls = 0
    threads_flagged = 0

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

        if thread_state["snoozed_until_utc"] and now < thread_state["snoozed_until_utc"]:
            continue

        if thread_state["in_area"] == "false":
            continue
        if (
            thread_state["in_area"] == "unknown"
            and not rules_config.get("include_unknown_location", True)
        ):
            continue

        if thread_state["genai_eval_count"] >= genai_config["max_genai_evals_per_thread"]:
            continue

        last_genai_eval = thread_state["last_genai_eval_at_utc"]
        if last_genai_eval:
            cooldown_seconds = genai_config["genai_cooldown_minutes"] * 60
            if now - last_genai_eval < cooldown_seconds:
                continue

        if last_genai_eval:
            delta_comments = list_comments_since(conn, thread_pk, last_genai_eval)
        else:
            delta_comments = list_comments_for_thread(conn, thread_pk)

        delta_min = genai_config["delta_min_new_comments"]
        trigger_a = (
            rule_results.get(thread_pk, {}).get("positive_hit", False)
            and thread_state["flagged"] != 1
        )
        trigger_b = thread_state["watching"] == 1 and len(delta_comments) >= delta_min
        if not (trigger_a or trigger_b):
            continue

        selected_delta = _select_delta_comments(
            delta_comments,
            thread["author"],
            genai_config["max_delta_comments_sent"],
        )
        delta_payload = _build_delta_payload_comments(selected_delta)
        rule_evidence = _build_rule_evidence(conn, thread_pk, run_id)
        payload = build_genai_payload(
            thread,
            delta_payload,
            rule_evidence,
            genai_config["business_context"],
        )

        eval_scope = "delta" if last_genai_eval else "thread_seed"
        delta_to_utc = None
        if selected_delta:
            delta_to_utc = max(
                comment["created_at_utc"]
                for comment in selected_delta
                if comment["created_at_utc"] is not None
            )

        genai_calls += 1
        result = None
        error_text = None
        tokens_in = None
        tokens_out = None
        status = "success"
        try:
            result, tokens_in, tokens_out = call_genai(payload, api_key)
        except Exception as exc:
            try:
                result, tokens_in, tokens_out = call_genai(payload, api_key)
            except Exception as retry_exc:
                status = "failed"
                error_text = str(retry_exc)
                result = {
                    "relevant": 0,
                    "short_reason": None,
                    "draft_response": None,
                    "detection_items": [],
                }

        genai_eval_pk = insert_genai_eval(
            conn,
            {
                "run_id": run_id,
                "thread_pk": thread_pk,
                "eval_scope": eval_scope,
                "delta_from_utc": last_genai_eval,
                "delta_to_utc": delta_to_utc,
                "relevant": result["relevant"],
                "short_reason": result.get("short_reason"),
                "model": MODEL_NAME,
                "prompt_version": PROMPT_VERSION,
                "created_at_utc": now,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "status": status,
                "error_text": error_text,
            },
        )

        conn.execute(
            """
            UPDATE thread_state
            SET last_genai_eval_at_utc = ?,
                genai_eval_count = genai_eval_count + 1
            WHERE thread_pk = ?
            """,
            (now, thread_pk),
        )

        if result["relevant"] == 1 and status == "success":
            if thread_state["flagged"] != 1:
                conn.execute(
                    """
                    UPDATE thread_state
                    SET flagged = 1,
                        flagged_at_utc = ?
                    WHERE thread_pk = ?
                    """,
                    (now, thread_pk),
                )
                threads_flagged += 1

            insert_draft_response(
                conn,
                thread_pk,
                genai_eval_pk,
                result.get("draft_response") or "",
                "suggested",
                now,
            )

            detection_payload = []
            for item in result.get("detection_items", []):
                comment_pk = None
                if item.get("comment_id"):
                    comment_pk = get_comment_pk_by_source_id(
                        conn, thread_pk, item["comment_id"]
                    )
                detection_payload.append(
                    {
                        "comment_pk": comment_pk,
                        "detection_type": item.get("detection_type"),
                        "evidence_text": item.get("evidence_excerpt"),
                        "source_hash": None,
                        "created_at_utc": now,
                    }
                )
            insert_detections(
                conn,
                thread_pk,
                thread["source_thread_id"],
                detection_payload,
            )

    return genai_calls, threads_flagged


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
        genai_config = _get_genai_config(conn)
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

        rule_hits_total, rule_results = _run_rules_for_threads(
            conn, run_id, ingested_thread_pks, rules_config
        )

        genai_calls = 0
        threads_flagged = 0
        if not config.get("OPENAI_API_KEY"):
            print(
                "Missing OPENAI_API_KEY. Skipping GenAI stage for this run."
            )
        else:
            genai_calls, threads_flagged = _run_genai_for_threads(
                conn,
                run_id,
                ingested_thread_pks,
                rules_config,
                genai_config,
                config.get("OPENAI_API_KEY"),
                rule_results,
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
                rule_hits = ?,
                genai_calls = ?,
                threads_flagged = ?
            WHERE run_id = ?
            """,
            (
                int(time.time()),
                "partial" if not config.get("OPENAI_API_KEY") else "success",
                threads_fetched,
                comments_fetched,
                threads_new,
                threads_updated,
                rule_hits_total,
                genai_calls,
                threads_flagged,
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
