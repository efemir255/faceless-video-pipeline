"""
reddit_fetcher.py — Automated story sourcing from Reddit with content filters.
"""

import logging
import random
import praw
from config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT

logger = logging.getLogger(__name__)

# Content filters
FORBIDDEN_KEYWORDS = [
    "sexual", "porn", "drugs", "cocaine", "heroin", "meth", "weed",
    "propaganda", "politics", "election", "biden", "trump", "democrat", "republican"
]

SUBREDDITS = {
    "scary": "shortscarystories",
    "funny": "tifu",
    "interesting": "AskReddit"
}

def get_reddit_story(category: str = "interesting"):
    """
    Fetch a filtered story from the specified category.
    """
    if not all([REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET]):
        logger.warning("Reddit API credentials missing.")
        return None

    subreddit_name = SUBREDDITS.get(category.lower(), "AskReddit")

    try:
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT
        )

        subreddit = reddit.subreddit(subreddit_name)
        posts = list(subreddit.hot(limit=25))
        random.shuffle(posts)

        for post in posts:
            if post.stickied or post.over_18:
                continue

            # Check for forbidden keywords
            text = (post.title + " " + (post.selftext or "")).lower()
            if any(kw in text for kw in FORBIDDEN_KEYWORDS):
                continue

            # Length check for Shorts (approx 100-150 words)
            word_count = len(text.split())
            if word_count < 50 or word_count > 200:
                continue

            logger.info("Fetched story from r/%s: %s", subreddit_name, post.title)
            return {
                "title": post.title,
                "text": post.selftext,
                "url": post.url
            }

    except Exception as e:
        logger.error("Failed to fetch from Reddit: %s", e)

    return None
