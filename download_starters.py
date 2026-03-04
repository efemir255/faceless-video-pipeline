"""
download_starters.py — CLI tool to download starter background videos for local categories.
"""

import sys
import logging
from config import VIDEO_CATEGORIES
from video_fetcher import download_category_starters

# Configure simple logging for console feedback
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

def main():
    print("🚀 Downloading starter videos for local background categories...")
    print("This will populate your 'assets/backgrounds/' subfolders.")
    print("-" * 50)

    for display_name, category in VIDEO_CATEGORIES.items():
        # Skip 'nature' if it's considered just a Pexels keyword,
        # but in this case we'll treat all as local candidates.
        print(f"📁 Processing '{display_name}' ({category})...")
        count = download_category_starters(category, count=3)
        if count > 0:
            print(f"✅ Successfully added {count} videos to assets/backgrounds/{category}/")
        else:
            print(f"❌ Failed to download starters for {category}. (Check PexELS_API_KEY)")
        print("-" * 50)

    print("\n✅ All set! You can now use these categories in the app.")

if __name__ == "__main__":
    main()
