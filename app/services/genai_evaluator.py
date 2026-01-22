import json

from openai import OpenAI

MODEL_NAME = "gpt-4o-mini"
PROMPT_VERSION = "v1"


def _get_value(obj, key, default=None):
    try:
        return obj[key]
    except Exception:
        return default


def build_genai_payload(thread, delta_comments, rule_hits, business_context):
    return {
        "business_context": business_context,
        "thread_seed": {
            "title": _get_value(thread, "title"),
            "body": _get_value(thread, "body"),
            "subreddit": _get_value(thread, "subreddit"),
            "url": _get_value(thread, "url"),
        },
        "delta_comments": delta_comments,
        "rule_evidence": rule_hits,
    }


def _coerce_relevant(value):
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, int):
        return 1 if value == 1 else 0
    if isinstance(value, str):
        return 1 if value.strip().lower() in {"1", "true", "yes"} else 0
    return 0


def _validate_detection_items(items):
    validated = []
    if not items:
        return validated
    if not isinstance(items, list):
        return validated
    for item in items:
        if not isinstance(item, dict):
            continue
        detection_type = item.get("detection_type")
        evidence_excerpt = item.get("evidence_excerpt")
        if not detection_type or not evidence_excerpt:
            continue
        validated.append(
            {
                "comment_id": item.get("comment_id"),
                "detection_type": str(detection_type),
                "evidence_excerpt": str(evidence_excerpt),
            }
        )
    return validated


def call_genai(payload, api_key):
    client = OpenAI(api_key=api_key)
    system_prompt = (
        "You are a classifier for a local service business. "
        "Return a JSON object with keys: relevant (0/1), short_reason (string, optional), "
        "draft_response (string, required if relevant=1), detection_items (array, optional). "
        "Each detection_item should include: comment_id (nullable), detection_type, evidence_excerpt."
    )
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload)},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    content = response.choices[0].message.content or "{}"
    data = json.loads(content)
    result = {
        "relevant": _coerce_relevant(data.get("relevant")),
        "short_reason": data.get("short_reason"),
        "draft_response": data.get("draft_response"),
        "detection_items": _validate_detection_items(data.get("detection_items")),
    }
    if result["relevant"] == 1 and not result["draft_response"]:
        raise ValueError("Missing draft_response for relevant thread.")

    usage = response.usage
    tokens_in = getattr(usage, "prompt_tokens", None) if usage else None
    tokens_out = getattr(usage, "completion_tokens", None) if usage else None
    return result, tokens_in, tokens_out


def evaluate_thread(payload, api_key):
    result, _, _ = call_genai(payload, api_key)
    return result
