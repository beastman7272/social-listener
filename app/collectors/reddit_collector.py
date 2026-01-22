def fetch_threads(reddit, subreddits, limit):
    submissions = []
    for subreddit_name in subreddits:
        subreddit = reddit.subreddit(subreddit_name)
        submissions.extend(list(subreddit.new(limit=limit)))
    return submissions


def fetch_comments(submission):
    submission.comments.replace_more(limit=0)
    return list(submission.comments.list())
