import hashlib


def insert_genai_eval(conn, eval_dict):
    cursor = conn.execute(
        """
        INSERT INTO genai_evals (
            run_id,
            thread_pk,
            eval_scope,
            delta_from_utc,
            delta_to_utc,
            relevant,
            short_reason,
            model,
            prompt_version,
            created_at_utc,
            tokens_in,
            tokens_out,
            status,
            error_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            eval_dict.get("run_id"),
            eval_dict.get("thread_pk"),
            eval_dict.get("eval_scope"),
            eval_dict.get("delta_from_utc"),
            eval_dict.get("delta_to_utc"),
            eval_dict.get("relevant"),
            eval_dict.get("short_reason"),
            eval_dict.get("model"),
            eval_dict.get("prompt_version"),
            eval_dict.get("created_at_utc"),
            eval_dict.get("tokens_in"),
            eval_dict.get("tokens_out"),
            eval_dict.get("status"),
            eval_dict.get("error_text"),
        ),
    )
    return cursor.lastrowid


def insert_draft_response(conn, thread_pk, genai_eval_pk, draft_text, status, now_utc):
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
            1,
            status,
            now_utc,
            now_utc,
        ),
    )


def _hash_detection(thread_source_id, evidence_text):
    raw = f"{thread_source_id}:{evidence_text}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def insert_detections(conn, thread_pk, thread_source_id, detection_items):
    if not detection_items:
        return 0

    count = 0
    for item in detection_items:
        comment_pk = item.get("comment_pk")
        source_hash = item.get("source_hash")
        evidence_text = item.get("evidence_text")
        if comment_pk is None and not source_hash and evidence_text:
            source_hash = _hash_detection(thread_source_id, evidence_text)

        conn.execute(
            """
            INSERT INTO detections (
                thread_pk,
                comment_pk,
                detection_type,
                evidence_text,
                source_hash,
                created_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT DO NOTHING
            """,
            (
                thread_pk,
                comment_pk,
                item.get("detection_type"),
                evidence_text,
                source_hash,
                item.get("created_at_utc"),
            ),
        )
        count += 1
    return count
