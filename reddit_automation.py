"""
reddit_automation.py — Fully automated end-to-end video generation and upload.
"""

import argparse
import logging
import sys
from pathlib import Path

from reddit_fetcher import get_reddit_story, capture_post_screenshot
from tts_engine import generate_audio
from video_fetcher import get_clips_for_script
from video_engine import render_final_video
from uploader import upload_video
from config import FINAL_DIR

logger = logging.getLogger(__name__)

def run_auto_pipeline(
    category: str,
    platforms: list[str],
    source: str = "pexels",
    video_category: str | None = None,
    use_screenshot: bool = False,
    split_screen: bool = False,
    progress_bar: bool = False,
    cta: str | None = None
):
    """
    Fetch -> TTS -> Clips -> Render -> Upload
    """
    logger.info("🚀 Starting automated pipeline for category: %s", category)

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
        audio_path, duration, timing_path = generate_audio(script)

        # 2.5 Screenshot (Optional)
        screenshot_path = None
        if use_screenshot and story.get("full_url"):
            logger.info("Capturing Reddit screenshot...")
            ss_path = Path(FINAL_DIR).parent / "backgrounds" / f"screenshot_{story['id']}.png"
            try:
                screenshot_path = capture_post_screenshot(story["full_url"], ss_path)
            except Exception as e:
                logger.warning("Screenshot capture failed: %s", e)

        # 3. Clips
        logger.info("Fetching clips (source: %s, category: %s)...", source, video_category)
        # Use a generic keyword related to the category
        base_kw = "scary" if category == "scary" else "nature"
        clips_metadata = get_clips_for_script(
            script,
            duration,
            base_keyword=base_kw,
            source_type=source,
            category=video_category
        )

        # 4. Render
        logger.info("Rendering video...")
        final_video_path = render_final_video(
            audio_path,
            clips_metadata,
            timing_path=timing_path,
            screenshot_path=screenshot_path,
            split_screen=split_screen,
            progress_bar=progress_bar,
            cta_text=cta
        )

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
    parser.add_argument("--source", choices=["pexels", "builtin"], default="pexels", help="Background source")
    parser.add_argument("--video-category", help="Built-in category name (if source is builtin)")
    parser.add_argument("--upload", nargs="+", choices=["youtube", "tiktok"], help="Platforms to upload to")
    parser.add_argument("--screenshot", action="store_true", help="Capture Reddit screenshot hook")
    parser.add_argument("--split-screen", action="store_true", help="Enable split-screen mode")
    parser.add_argument("--progress-bar", action="store_true", help="Enable progress bar")
    parser.add_argument("--cta", help="Call to Action text")

    args = parser.parse_args()

    # Configure logging to console for CLI use
    logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

    run_auto_pipeline(
        args.category,
        args.upload,
        source=args.source,
        video_category=args.video_category,
        use_screenshot=args.screenshot,
        split_screen=args.split_screen,
        progress_bar=args.progress_bar,
        cta=args.cta
    )
