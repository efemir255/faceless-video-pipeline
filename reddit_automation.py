"""
reddit_automation.py — Fully automated end-to-end video generation and upload.
"""

import argparse
import logging
import sys
from pathlib import Path

from reddit_fetcher import get_reddit_story
from tts_engine import generate_audio
from video_fetcher import get_clips_for_script
from video_engine import render_final_video
from uploader import upload_video
from config import FINAL_DIR

logger = logging.getLogger(__name__)

def run_auto_pipeline(category: str, platforms: list[str]):
    """
    Fetch -> TTS -> Clips -> Render -> Upload
    """
    logger.info("🚀 Starting automated pipeline for category: %s", category)

    from config import PEXELS_API_KEY
    if not PEXELS_API_KEY:
        logger.error("❌ PEXELS_API_KEY is not set. Cannot continue.")
        return

    # 1. Fetch from Reddit
    story = get_reddit_story(category)
    if not story:
        logger.error("Could not fetch a suitable story.")
        return

    script = f"{story['title']}. {story['text']}"
    title = story['title']
    subreddit = story.get('subreddit', category)
    description = f"Story from r/{subreddit}\n\n#reddit #story #shorts"

    try:
        # 2. TTS
        logger.info("Generating TTS...")
        audio_path, duration = generate_audio(script)

        # 3. Clips
        logger.info("Fetching clips...")
        # Use a generic keyword related to the category
        base_kw = "scary" if category == "scary" else "nature"
        clips_metadata = get_clips_for_script(script, duration, base_keyword=base_kw)

        # 4. Render
        logger.info("Rendering video...")
        final_video_path = render_final_video(audio_path, clips_metadata)

        # 5. Upload
        if platforms:
            logger.info("Uploading to %s...", ", ".join(platforms))
            results = upload_video(final_video_path, title, description, platforms=platforms)
            for p, ok in results.items():
                if ok:
                    logger.info("✅ Uploaded to %s", p)
                else:
                    logger.error("❌ Failed to upload to %s", p)
        else:
            logger.info("No upload platforms specified. Final video: %s", final_video_path)

    except Exception as e:
        logger.exception("Automated pipeline failed: %s", e)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automated Reddit Video Pipeline")
    parser.add_argument("--category", choices=["interesting", "funny", "scary"], default="interesting")
    parser.add_argument("--upload", nargs="+", choices=["youtube", "tiktok"], help="Platforms to upload to")

    args = parser.parse_args()

    # Configure logging to console for CLI use
    logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

    run_auto_pipeline(args.category, args.upload)
