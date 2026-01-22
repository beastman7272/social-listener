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
