def _normalize_terms(terms):
    if not terms:
        return []
    return [str(term).strip().lower() for term in terms if str(term).strip()]


def _find_terms(text, terms):
    if not text:
        return []
    haystack = text.lower()
    matches = []
    for term in terms:
        if term and term in haystack:
            matches.append(term)
    return matches


def _build_hits(terms, hit_type, context, comment_pk=None):
    hits = []
    for term in terms:
        hits.append(
            {
                "hit_type": hit_type,
                "matched_term": term,
                "match_context": context,
                "comment_pk": comment_pk,
            }
        )
    return hits


def _get_value(obj, key, default=None):
    try:
        return obj[key]
    except Exception:
        return default


def evaluate_comment(comment, config):
    hits = []
    body = comment["body"] or ""

    service_terms = _normalize_terms(config.get("keywords_include"))
    intent_terms = _normalize_terms(config.get("keywords_intent"))
    negative_terms = _normalize_terms(config.get("keywords_negative"))

    hits.extend(
        _build_hits(
            _find_terms(body, service_terms),
            "keyword",
            "comment",
            comment_pk=comment["comment_pk"],
        )
    )
    hits.extend(
        _build_hits(
            _find_terms(body, intent_terms),
            "phrase",
            "comment",
            comment_pk=comment["comment_pk"],
        )
    )
    hits.extend(
        _build_hits(
            _find_terms(body, negative_terms),
            "negative",
            "comment",
            comment_pk=comment["comment_pk"],
        )
    )
    return hits


def evaluate_thread(thread, comments, config):
    hits = []
    title = _get_value(thread, "title") or ""
    body = _get_value(thread, "body") or ""

    service_terms = _normalize_terms(config.get("keywords_include"))
    intent_terms = _normalize_terms(config.get("keywords_intent"))
    negative_terms = _normalize_terms(config.get("keywords_negative"))

    hits.extend(
        _build_hits(_find_terms(title, service_terms), "keyword", "title")
    )
    hits.extend(
        _build_hits(_find_terms(title, intent_terms), "phrase", "title")
    )
    hits.extend(
        _build_hits(_find_terms(title, negative_terms), "negative", "title")
    )

    hits.extend(
        _build_hits(_find_terms(body, service_terms), "keyword", "body")
    )
    hits.extend(
        _build_hits(_find_terms(body, intent_terms), "phrase", "body")
    )
    hits.extend(
        _build_hits(_find_terms(body, negative_terms), "negative", "body")
    )

    for comment in comments:
        hits.extend(evaluate_comment(comment, config))

    return hits


def infer_location(thread, comments, config):
    subreddit = (_get_value(thread, "subreddit") or "").lower()
    subreddit_map = config.get("subreddit_geo_map") or {}
    if subreddit and subreddit in subreddit_map:
        mapped_value = subreddit_map[subreddit]
        if isinstance(mapped_value, bool):
            return ("true" if mapped_value else "false", f"subreddit={subreddit}")
        if isinstance(mapped_value, str) and mapped_value.strip():
            return ("true", f"subreddit={subreddit}:{mapped_value.strip()}")

    service_tokens = _normalize_terms(config.get("geo_service_area"))
    out_of_area_tokens = _normalize_terms(config.get("geo_out_of_area"))

    text_chunks = [_get_value(thread, "title") or "", _get_value(thread, "body") or ""]
    for comment in comments:
        text_chunks.append(_get_value(comment, "body") or "")
    combined_text = " ".join(text_chunks).lower()

    for token in out_of_area_tokens:
        if token and token in combined_text:
            return ("false", f"text={token}")

    for token in service_tokens:
        if token and token in combined_text:
            return ("true", f"text={token}")

    return ("unknown", None)
