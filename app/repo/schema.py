def create_all(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            started_at_utc INTEGER,
            ended_at_utc INTEGER,
            status TEXT,
            source TEXT,
            threads_fetched INTEGER,
            comments_fetched INTEGER,
            threads_new INTEGER,
            threads_updated INTEGER,
            rule_hits INTEGER,
            genai_calls INTEGER,
            threads_flagged INTEGER,
            error_summary TEXT
        );

        CREATE TABLE IF NOT EXISTS threads (
            thread_pk INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            source_thread_id TEXT,
            url TEXT,
            subreddit TEXT,
            title TEXT,
            body TEXT,
            author TEXT,
            created_at_utc INTEGER,
            last_seen_at_utc INTEGER,
            last_content_at_utc INTEGER,
            is_deleted INTEGER,
            is_removed INTEGER,
            score INTEGER,
            num_comments_reported INTEGER,
            UNIQUE (source, source_thread_id)
        );

        CREATE TABLE IF NOT EXISTS comments (
            comment_pk INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_pk INTEGER,
            source TEXT,
            source_comment_id TEXT,
            parent_source_id TEXT,
            author TEXT,
            body TEXT,
            created_at_utc INTEGER,
            last_seen_at_utc INTEGER,
            is_deleted INTEGER,
            depth INTEGER,
            permalink TEXT,
            UNIQUE (source, source_comment_id),
            FOREIGN KEY (thread_pk) REFERENCES threads(thread_pk)
        );

        CREATE TABLE IF NOT EXISTS thread_state (
            thread_pk INTEGER PRIMARY KEY,
            watching INTEGER,
            active_until_utc INTEGER,
            closed INTEGER,
            in_area TEXT,
            location_confidence REAL,
            location_evidence TEXT,
            last_rule_check_at_utc INTEGER,
            last_genai_eval_at_utc INTEGER,
            last_seen_comment_at_utc INTEGER,
            genai_eval_count INTEGER DEFAULT 0,
            flagged INTEGER DEFAULT 0,
            flagged_at_utc INTEGER,
            dismissed INTEGER DEFAULT 0,
            snoozed_until_utc INTEGER,
            FOREIGN KEY (thread_pk) REFERENCES threads(thread_pk)
        );

        CREATE TABLE IF NOT EXISTS rule_hits (
            rule_hit_pk INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            thread_pk INTEGER,
            comment_pk INTEGER,
            hit_type TEXT,
            matched_term TEXT,
            match_context TEXT,
            created_at_utc INTEGER,
            FOREIGN KEY (run_id) REFERENCES runs(run_id),
            FOREIGN KEY (thread_pk) REFERENCES threads(thread_pk),
            FOREIGN KEY (comment_pk) REFERENCES comments(comment_pk)
        );

        CREATE TABLE IF NOT EXISTS genai_evals (
            genai_eval_pk INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            thread_pk INTEGER,
            eval_scope TEXT,
            delta_from_utc INTEGER,
            delta_to_utc INTEGER,
            relevant INTEGER,
            short_reason TEXT,
            model TEXT,
            prompt_version TEXT,
            created_at_utc INTEGER,
            tokens_in INTEGER,
            tokens_out INTEGER,
            status TEXT,
            error_text TEXT,
            FOREIGN KEY (run_id) REFERENCES runs(run_id),
            FOREIGN KEY (thread_pk) REFERENCES threads(thread_pk)
        );

        CREATE TABLE IF NOT EXISTS draft_responses (
            draft_pk INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_pk INTEGER,
            genai_eval_pk INTEGER,
            draft_text TEXT,
            draft_version INTEGER DEFAULT 1,
            status TEXT,
            created_at_utc INTEGER,
            updated_at_utc INTEGER,
            FOREIGN KEY (thread_pk) REFERENCES threads(thread_pk),
            FOREIGN KEY (genai_eval_pk) REFERENCES genai_evals(genai_eval_pk)
        );

        CREATE TABLE IF NOT EXISTS detections (
            detection_pk INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_pk INTEGER,
            comment_pk INTEGER,
            detection_type TEXT,
            evidence_text TEXT,
            source_hash TEXT,
            created_at_utc INTEGER,
            FOREIGN KEY (thread_pk) REFERENCES threads(thread_pk),
            FOREIGN KEY (comment_pk) REFERENCES comments(comment_pk)
        );

        CREATE TABLE IF NOT EXISTS review_actions (
            action_pk INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_pk INTEGER,
            action_type TEXT,
            action_value TEXT,
            actor TEXT,
            created_at_utc INTEGER,
            FOREIGN KEY (thread_pk) REFERENCES threads(thread_pk)
        );

        CREATE TABLE IF NOT EXISTS config (
            config_key TEXT PRIMARY KEY,
            config_value TEXT,
            updated_at_utc INTEGER
        );

        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at_utc INTEGER,
            notes TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_runs_started_at_utc
            ON runs (started_at_utc);

        CREATE INDEX IF NOT EXISTS idx_threads_source_created_at
            ON threads (source, created_at_utc);
        CREATE INDEX IF NOT EXISTS idx_threads_subreddit
            ON threads (subreddit);
        CREATE INDEX IF NOT EXISTS idx_threads_last_content_at_utc
            ON threads (last_content_at_utc);

        CREATE INDEX IF NOT EXISTS idx_comments_thread_created_at
            ON comments (thread_pk, created_at_utc);
        CREATE INDEX IF NOT EXISTS idx_comments_created_at_utc
            ON comments (created_at_utc);

        CREATE INDEX IF NOT EXISTS idx_thread_state_flags
            ON thread_state (flagged, dismissed, snoozed_until_utc);
        CREATE INDEX IF NOT EXISTS idx_thread_state_active_until_utc
            ON thread_state (active_until_utc);
        CREATE INDEX IF NOT EXISTS idx_thread_state_watching
            ON thread_state (watching);

        CREATE INDEX IF NOT EXISTS idx_rule_hits_thread_created_at
            ON rule_hits (thread_pk, created_at_utc);
        CREATE INDEX IF NOT EXISTS idx_rule_hits_run_id
            ON rule_hits (run_id);

        CREATE INDEX IF NOT EXISTS idx_genai_evals_thread_created_at
            ON genai_evals (thread_pk, created_at_utc);
        CREATE INDEX IF NOT EXISTS idx_genai_evals_run_id
            ON genai_evals (run_id);
        CREATE INDEX IF NOT EXISTS idx_genai_evals_relevant
            ON genai_evals (relevant);

        CREATE INDEX IF NOT EXISTS idx_draft_responses_thread_updated_at
            ON draft_responses (thread_pk, updated_at_utc);
        CREATE INDEX IF NOT EXISTS idx_draft_responses_status
            ON draft_responses (status);

        CREATE UNIQUE INDEX IF NOT EXISTS ux_detections_thread_comment_type
            ON detections (thread_pk, comment_pk, detection_type)
            WHERE comment_pk IS NOT NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS ux_detections_thread_sourcehash_type
            ON detections (thread_pk, source_hash, detection_type)
            WHERE comment_pk IS NULL;
        CREATE INDEX IF NOT EXISTS idx_detections_thread_pk
            ON detections (thread_pk);
        CREATE INDEX IF NOT EXISTS idx_detections_created_at_utc
            ON detections (created_at_utc);

        CREATE INDEX IF NOT EXISTS idx_review_actions_thread_created_at
            ON review_actions (thread_pk, created_at_utc);
        CREATE INDEX IF NOT EXISTS idx_review_actions_action_type
            ON review_actions (action_type);
        """
    )
