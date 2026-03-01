"""
reddit_fetcher.py — Automated story sourcing from Reddit with content filters.
"""

import logging
import random
import requests
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

# Browser-like User-Agents to avoid 403 Forbidden errors
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
]

def get_reddit_story(category: str = "interesting", seen_ids: set | None = None):
    """
    Fetch a filtered story from the specified category.
    Prefers PRAW if credentials exist; otherwise falls back to public JSON API.
    """
    if seen_ids is None:
        seen_ids = set()

    # Try PRAW first if credentials are set
    if REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET:
        try:
            logger.info("Attempting fetch with PRAW...")
            reddit = praw.Reddit(
                client_id=REDDIT_CLIENT_ID,
                client_secret=REDDIT_CLIENT_SECRET,
                user_agent=REDDIT_USER_AGENT
            )

            category_list = list(SUBREDDITS.get(category.lower(), ["AskReddit"]))
            random.shuffle(category_list)

            for subreddit_name in category_list:
                subreddit = reddit.subreddit(subreddit_name)
                for submission in subreddit.hot(limit=25):
                    if submission.stickied or submission.over_18 or submission.id in seen_ids:
                        continue

                    story_title = submission.title
                    story_text = submission.selftext

                    if not story_text.strip() and subreddit_name.lower() == "askreddit":
                        submission.comment_sort = "top"
                        for comment in submission.comments:
                            if not comment.stickied and comment.author != "AutoModerator":
                                story_text = comment.body
                                break

                    res = _validate_and_format_story(submission.id, story_title, story_text, submission.permalink, subreddit_name)
                    if res:
                        logger.info("Fetched story with PRAW from r/%s: %s", subreddit_name, story_title)
                        return res
        except Exception as e:
            logger.warning("PRAW fetch failed, falling back to JSON API: %s", e)

    # JSON API Fallback
    category_list = list(SUBREDDITS.get(category.lower(), ["AskReddit"]))
    random.shuffle(category_list)

    for subreddit_name in category_list:
        url = f"https://www.reddit.com/r/{subreddit_name}/hot.json?limit=25"
        headers = {"User-Agent": random.choice(USER_AGENTS)}

        try:
            logger.info("Trying to fetch from r/%s (JSON API)...", subreddit_name)
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            posts = data.get("data", {}).get("children", [])
            random.shuffle(posts)

            for post_data in posts:
                post = post_data.get("data", {})
                post_id = post.get("id")

                # Skip stickied, NSFW, or already seen posts
                if post.get("stickied") or post.get("over_18") or post_id in seen_ids:
                    continue

                story_title = post.get("title", "")
                story_text = post.get("selftext", "")

                # If it's AskReddit and has no selftext, try fetching the top comment
                if not story_text.strip() and subreddit_name.lower() == "askreddit":
                    comment_url = f"https://www.reddit.com{post.get('permalink')}.json?limit=5"
                    try:
                        c_resp = requests.get(comment_url, headers={"User-Agent": random.choice(USER_AGENTS)}, timeout=5)
                        c_resp.raise_for_status()
                        c_data = c_resp.json()
                        if isinstance(c_data, list) and len(c_data) > 1:
                            comments = c_data[1].get("data", {}).get("children", [])
                            for c_child in comments:
                                comment = c_child.get("data", {})
                                if not comment.get("stickied") and comment.get("author") != "AutoModerator":
                                    story_text = comment.get("body", "")
                                    break
                    except Exception as ce:
                        logger.warning("Failed to fetch comments for post %s: %s", post_id, ce)

                res = _validate_and_format_story(post_id, story_title, story_text, post.get('permalink', ''), subreddit_name)
                if res:
                    logger.info("Fetched story from r/%s (JSON): %s", subreddit_name, story_title)
                    return res
        except Exception as e:
            logger.error("Failed to fetch from r/%s: %s", subreddit_name, e)

    return None

def _validate_and_format_story(post_id: str, title: str, text: str, permalink: str, subreddit: str):
    """Internal helper to filter and format the final story dict."""
    if not text.strip():
        return None

    # Check for forbidden keywords using word boundaries
    content_lower = (title + " " + text).lower()
    for kw in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", content_lower):
            return None

    # Length check for Shorts (approx 30-600 words)
    word_count = len(text.split())
    if word_count < 30 or word_count > 600:
        return None

    return {
        "id": post_id,
        "title": title,
        "text": text,
        "url": f"https://reddit.com{permalink}",
        "subreddit": subreddit
    }
