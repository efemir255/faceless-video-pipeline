"""
reddit_fetcher.py — Automated story sourcing from Reddit with content filters.
"""

import logging
import random
import requests
import re

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
    "scary": ["shortscarystories", "nosleep", "creepy", "libraryofshadows", "letsnotmeet"],
    "funny": ["tifu", "funny", "humor", "comedy"],
    "interesting": ["AskReddit", "unpopularopinion", "todayilearned", "ExplainLikeImFive"],
    "drama": ["AmItheAsshole", "relationships", "relationship_advice", "confessions", "offmychest"],
    "tales": ["TalesFromTechSupport", "TalesFromRetail", "TalesFromYourServer"],
    "entitled": ["entitledparents", "entitledpeople", "choosingbeggars"],
    "revenge": ["ProRevenge", "MaliciousCompliance", "NuclearRevenge"]
}

SERIES_REGEX = re.compile(r"(?:part|pt|chapter|ch\.?)\s*(\d+)", re.IGNORECASE)

def detect_series(title: str):
    """Detect if a title indicates a multi-part series and return the part number."""
    match = SERIES_REGEX.search(title)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None

def fetch_series_parts(author: str, original_title: str):
    """
    Fetch other parts of a series by the same author.
    Matches posts with similar titles that have series markers.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    }
    url = f"https://www.reddit.com/user/{author}/submitted.json?limit=50"

    # Strip part info from title to find siblings
    base_title = SERIES_REGEX.sub("", original_title).strip()
    # Normalize: remove extra spaces and punctuation
    base_title_norm = re.sub(r"[^\w\s]", "", base_title).lower()

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        posts = data.get("data", {}).get("children", [])

        parts = []
        for post_data in posts:
            post = post_data.get("data", {})
            title = post.get("title", "")
            part_num = detect_series(title)

            if part_num is not None:
                title_norm = re.sub(r"[^\w\s]", "", SERIES_REGEX.sub("", title)).lower().strip()
                # Check if titles are sufficiently similar
                if base_title_norm in title_norm or title_norm in base_title_norm:
                    parts.append({
                        "id": post.get("id"),
                        "title": title,
                        "text": post.get("selftext", ""),
                        "part": part_num,
                        "url": f"https://reddit.com{post.get('permalink', '')}",
                        "subreddit": post.get("subreddit")
                    })

        # Sort by part number
        parts.sort(key=lambda x: x["part"])
        return parts
    except Exception as e:
        logger.error("Failed to fetch series parts for author %s: %s", author, e)
        return []

def get_reddit_story(category: str = "interesting", seen_ids: set | None = None):
    """
    Fetch a filtered story from the specified category using public JSON API.
    Bypasses the need for Reddit API credentials by using a browser-like User-Agent.
    Avoids stories in seen_ids.
    """
    if seen_ids is None:
        seen_ids = set()

    # Select a random subreddit from the list for the category
    category_list = SUBREDDITS.get(category.lower(), ["AskReddit"])
    subreddit_name = random.choice(category_list)
    
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
            post_id = post.get("id")
            
            # Skip stickied, NSFW, or already seen posts
            if post.get("stickied") or post.get("over_18") or post_id in seen_ids:
                continue

            # Filtering: Skip videos, galleries, and non-text-focused posts
            if post.get("is_video") or post.get("is_gallery"):
                continue

            post_hint = post.get("post_hint", "")
            if post_hint in ["image", "video", "rich:video", "hosted:video"]:
                continue

            url = post.get("url", "")
            if any(url.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif", ".gifv", ".mp4", ".webm"]):
                continue

            # Ensure it's a self-post (unless it's AskReddit where we might pull comments)
            if not post.get("is_self") and subreddit_name.lower() != "askreddit":
                continue

            story_title = post.get("title", "")
            story_text = post.get("selftext", "")

            # If it's AskReddit and has no selftext, try fetching the top comment
            if not story_text.strip() and subreddit_name.lower() == "askreddit":
                comment_url = f"https://www.reddit.com{post.get('permalink')}.json?limit=5"
                try:
                    c_resp = requests.get(comment_url, headers=headers, timeout=5)
                    c_resp.raise_for_status()
                    c_data = c_resp.json()
                    # The second item in the list is the comments
                    if isinstance(c_data, list) and len(c_data) > 1:
                        comments = c_data[1].get("data", {}).get("children", [])
                        for c_child in comments:
                            comment = c_child.get("data", {})
                            if not comment.get("stickied") and comment.get("author") != "AutoModerator":
                                story_text = comment.get("body", "")
                                break
                except Exception as ce:
                    logger.warning("Failed to fetch comments for AskReddit post %s: %s", post_id, ce)

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

            # Length check for Shorts (approx 30-600 words)
            word_count = len(story_text.split())
            if word_count < 30 or word_count > 600:
                continue

            series_part = detect_series(story_title)

            logger.info("Fetched story from r/%s: %s", subreddit_name, story_title)
            return {
                "id": post_id,
                "title": story_title,
                "text": story_text,
                "url": f"https://reddit.com{post.get('permalink', '')}",
                "subreddit": subreddit_name,
                "author": post.get("author"),
                "series_part": series_part
            }

    except Exception as e:
        logger.error("Failed to fetch from Reddit JSON API: %s", e)

    return None
