import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP_ROOT = os.path.join(REPO_ROOT, "app")
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

from repo.config import upsert_config_value
from repo.db import connect
from repo.migrate import init_db_if_missing


def main():
    init_db_if_missing()
    conn = connect()
    try:
        defaults = {
            "subreddits": ["Atlanta"],
            "keywords_include": [],
            "keywords_intent": [],
            "keywords_negative": [],
            "include_unknown_location": True,
            "active_window_days": 5,
            "max_genai_evals_per_thread": 5,
            "genai_cooldown_minutes": 120,
            "delta_min_new_comments": 1,
            "max_delta_comments_sent": 25,
        }
        for key, value in defaults.items():
            upsert_config_value(conn, key, value)
        conn.commit()
    finally:
        conn.close()

    print("Seeded config defaults.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
