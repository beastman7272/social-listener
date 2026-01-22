import time


def normalize_submission(submission):
    now = int(time.time())
    author = submission.author.name if submission.author else None
    return {
        "source": "reddit",
        "source_thread_id": submission.id,
        "url": submission.url,
        "subreddit": str(submission.subreddit),
        "title": submission.title,
        "body": submission.selftext or "",
        "author": author,
        "created_at_utc": int(submission.created_utc),
        "last_seen_at_utc": now,
        "last_content_at_utc": int(submission.created_utc),
        "is_deleted": 1 if submission.selftext == "[deleted]" else None,
        "is_removed": 1 if submission.selftext == "[removed]" else None,
        "score": getattr(submission, "score", None),
        "num_comments_reported": getattr(submission, "num_comments", None),
    }


def normalize_comment(comment, thread_pk, thread_source_id):
    now = int(time.time())
    author = comment.author.name if comment.author else None
    body = comment.body or ""
    return {
        "thread_pk": thread_pk,
        "source": "reddit",
        "source_comment_id": comment.id,
        "parent_source_id": comment.parent_id,
        "author": author,
        "body": body,
        "created_at_utc": int(comment.created_utc),
        "last_seen_at_utc": now,
        "is_deleted": 1 if body == "[deleted]" else None,
        "depth": getattr(comment, "depth", None),
        "permalink": getattr(comment, "permalink", None),
    }
