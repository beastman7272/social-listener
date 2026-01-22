import praw


def build_reddit_client(config):
    return praw.Reddit(
        client_id=config.get("REDDIT_CLIENT_ID"),
        client_secret=config.get("REDDIT_CLIENT_SECRET"),
        user_agent=config.get("REDDIT_USER_AGENT"),
        username=config.get("REDDIT_USERNAME"),
        password=config.get("REDDIT_PASSWORD"),
    )
