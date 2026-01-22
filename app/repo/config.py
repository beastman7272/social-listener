import json


def get_config_value(conn, key):
    row = conn.execute(
        "SELECT config_value FROM config WHERE config_key = ?",
        (key,),
    ).fetchone()
    if row is None:
        return None
    return row["config_value"]


def parse_config_json(raw_value):
    if raw_value is None:
        return None
    try:
        return json.loads(raw_value)
    except Exception:
        return None


def get_config_list(conn, key, default=None):
    if default is None:
        default = []
    raw_value = get_config_value(conn, key)
    parsed = parse_config_json(raw_value)
    if isinstance(parsed, list):
        return parsed
    return default


def get_config_bool(conn, key, default=False):
    raw_value = get_config_value(conn, key)
    parsed = parse_config_json(raw_value)
    if isinstance(parsed, bool):
        return parsed
    return default


def get_config_int(conn, key, default=0):
    raw_value = get_config_value(conn, key)
    parsed = parse_config_json(raw_value)
    if isinstance(parsed, int):
        return parsed
    return default


def get_config_dict(conn, key, default=None):
    if default is None:
        default = {}
    raw_value = get_config_value(conn, key)
    parsed = parse_config_json(raw_value)
    if isinstance(parsed, dict):
        return parsed
    return default


def upsert_config_value(conn, key, value):
    payload = json.dumps(value)
    conn.execute(
        """
        INSERT INTO config (config_key, config_value, updated_at_utc)
        VALUES (?, ?, strftime('%s','now'))
        ON CONFLICT(config_key) DO UPDATE SET
            config_value = excluded.config_value,
            updated_at_utc = excluded.updated_at_utc
        """,
        (key, payload),
    )
