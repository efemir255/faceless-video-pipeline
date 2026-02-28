"""
reddit_fetcher.py — Automated story sourcing from Reddit with content filters.
"""

import logging
import random
import requests

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
    Fetch a filtered story from the specified category using public JSON API.
    Bypasses the need for Reddit API credentials by using a browser-like User-Agent.
    """
    subreddit_name = SUBREDDITS.get(category.lower(), "AskReddit")
    url = f"https://www.reddit.com/r/{subreddit_name}/hot.json?limit=25"
    
    # We use a browser-like User-Agent to avoid 403 Forbidden errors
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        posts = data.get("data", {}).get("children", [])
        random.shuffle(posts)

        for post_data in posts:
            post = post_data.get("data", {})
            
            # Skip stickied or NSFW posts
            if post.get("stickied") or post.get("over_18"):
                continue

            # Skip posts that are just links/images (need selftext for stories)
            if not post.get("selftext"):
                continue

            # Check for forbidden keywords
            title = post.get("title", "")
            text = post.get("selftext", "")
            combined_text = (title + " " + text).lower()
            if any(kw in combined_text for kw in FORBIDDEN_KEYWORDS):
                continue

            # Length check for Shorts (approx 50-600 words)
            word_count = len(combined_text.split())
            if word_count < 30 or word_count > 600:
                continue

            logger.info("Fetched story from r/%s: %s", subreddit_name, title)
            return {
                "title": title,
                "text": text,
                "url": f"https://reddit.com{post.get('permalink', '')}"
            }

    except Exception as e:
        logger.error("Failed to fetch from Reddit JSON API: %s", e)

    return None
