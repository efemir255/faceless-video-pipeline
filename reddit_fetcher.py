"""
reddit_fetcher.py — Automated story sourcing from Reddit with content filters.
"""

import logging
import random
import re
import praw
from config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT

logger = logging.getLogger(__name__)

# Content filters
# Expanding to cover sexual content, drug use, and propaganda/politics more thoroughly
FORBIDDEN_KEYWORDS = [
    # Sexual content
    "sexual", "porn", "xxx", "nsfw", "erotic", "fetish", "onlyfans",
    # Drugs
    "drugs", "cocaine", "heroin", "meth", "weed", "marijuana", "overdose", "pill", "lsd",
    # Propaganda / Politics
    "propaganda", "politics", "election", "biden", "trump", "democrat", "republican",
    "government", "war", "israel", "palestine", "russia", "ukraine", "protest", "riot"
]

SUBREDDITS = {
    "scary": ["shortscarystories", "nosleep", "creepy"],
    "funny": ["tifu", "funny", "humor"],
    "interesting": ["AskReddit", "unpopularopinion", "todayilearned"]
}

def get_reddit_story(category: str = "interesting", seen_ids: set | None = None):
    """
    Fetch a filtered story from the specified category.
    Avoids stories in seen_ids.
    """
    if not all([REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET]):
        logger.warning("Reddit API credentials missing.")
        return None

    if seen_ids is None:
        seen_ids = set()

    # Select a random subreddit from the list for the category
    category_list = SUBREDDITS.get(category.lower(), ["AskReddit"])
    subreddit_name = random.choice(category_list)

    try:
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT
        )

        subreddit = reddit.subreddit(subreddit_name)
        # Use top(day) or hot() for good content
        posts = list(subreddit.hot(limit=25))
        random.shuffle(posts)

        for post in posts:
            if post.stickied or post.over_18 or post.id in seen_ids:
                continue

            # Get content: use selftext, or if it's AskReddit, get the top comment
            story_title = post.title
            story_text = post.selftext or ""

            if not story_text.strip() and subreddit_name.lower() == "askreddit":
                # Fetch top comments
                post.comments.replace_more(limit=0)
                comments = [c for c in post.comments if not c.stickied and c.author != "AutoModerator"]
                if comments:
                    story_text = comments[0].body

            if not story_text.strip():
                continue

            # Check for forbidden keywords using word boundaries for better accuracy
            content_lower = (story_title + " " + story_text).lower()
            found_forbidden = False
            for kw in FORBIDDEN_KEYWORDS:
                if re.search(rf"\b{re.escape(kw)}\b", content_lower):
                    found_forbidden = True
                    break

            if found_forbidden:
                continue

            # Length check for Shorts (approx 100-150 words)
            word_count = len(story_text.split())
            if word_count < 50 or word_count > 200:
                continue

            logger.info("Fetched story from r/%s: %s", subreddit_name, story_title)
            return {
                "id": post.id,
                "title": story_title,
                "text": story_text,
                "url": post.url,
                "subreddit": subreddit_name
            }

    except Exception as e:
        logger.error("Failed to fetch from Reddit: %s", e)

    return None
