import os
import time

from .db import connect, get_db_path
from .schema import create_all


def _ensure_schema_migrations(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at_utc INTEGER,
            notes TEXT
        );
        """
    )
    conn.commit()


def init_db(db_path=None):
    if db_path is None:
        db_path = get_db_path()

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = connect(db_path)
    try:
        _ensure_schema_migrations(conn)
        row = conn.execute(
            "SELECT 1 FROM schema_migrations WHERE version = 1"
        ).fetchone()
        if row is None:
            create_all(conn)
            conn.execute(
                "INSERT INTO schema_migrations (version, applied_at_utc, notes) "
                "VALUES (?, ?, ?)",
                (1, int(time.time()), "initial schema"),
            )
            conn.commit()
    finally:
        conn.close()


def init_db_if_missing(db_path=None):
    if db_path is None:
        db_path = get_db_path()
    if not os.path.exists(db_path):
        init_db(db_path)
