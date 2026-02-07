import sqlite3
import praw
from datetime import datetime, timedelta

DB_PATH = "instance/db.sqlite"
USER_AGENT = "script:social-listener:v1.0 (by /u/Mysterious_Range4275)"

def cleanup_deleted_content():
    # 1. Setup Reddit Client (PRAW)
    reddit = praw.Reddit(
        client_id="YOUR_CLIENT_ID",
        client_secret="YOUR_CLIENT_SECRET",
        user_agent=USER_AGENT
    )
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 2. Identify threads to check (those not already marked is_deleted)
    # Using 'threads' table and 'source_thread_id' from Data Model
    cursor.execute("SELECT thread_pk, source_thread_id FROM threads WHERE is_deleted = 0 OR is_deleted IS NULL")
    threads = cursor.fetchall()

    for pk, thread_id in threads:
        try:
            submission = reddit.submission(id=thread_id)
            # Reddit policy: delete if body/title is gone or author is [deleted]
            if submission.author is None or submission.selftext == "[deleted]" or submission.removed_by_category:
                print(f"Hard deleting thread {thread_id} - removed from Reddit.")
                # Hard delete to ensure compliance with 48-hour rule
                cursor.execute("DELETE FROM threads WHERE thread_pk = ?", (pk,))
                cursor.execute("DELETE FROM comments WHERE thread_pk = ?", (pk,))
        except Exception as e:
            print(f"Error checking thread {thread_id}: {e}")

    # 3. Identify individual comments to check
    # Using 'comments' table and 'source_comment_id' from Data Model
    cursor.execute("SELECT comment_pk, source_comment_id FROM comments WHERE is_deleted = 0 OR is_deleted IS NULL")
    comments = cursor.fetchall()

    for pk, comment_id in comments:
        try:
            comment = reddit.comment(id=comment_id)
            if comment.author is None or comment.body == "[deleted]":
                print(f"Hard deleting comment {comment_id} - removed from Reddit.")
                cursor.execute("DELETE FROM comments WHERE comment_pk = ?", (pk,))
        except Exception as e:
            print(f"Error checking comment {comment_id}: {e}")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    cleanup_deleted_content()