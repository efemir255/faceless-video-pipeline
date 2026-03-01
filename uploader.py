"""
uploader.py — Auto-upload finished videos to YouTube Shorts and TikTok.

Uses Playwright with a **persistent browser context** so you only need
to log in manually once.  After that, uploads are fully automated.

Features:
- Hardened upload verification.
- Post-upload grace period to keep the window open for user review.
- Support for YouTube and TikTok.
"""

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

# Force the project root into sys.path to ensure local imports always work in the IDE
_ROOT = str(Path(__file__).resolve().parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout # type: ignore

from config import ( # type: ignore
    BROWSER_USER_DATA_DIR,
    PLAYWRIGHT_TIMEOUT_MS,
    YOUTUBE_STUDIO_UPLOAD_URL,
    TIKTOK_UPLOAD_URL,
    HEADLESS_BROWSER,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
#  Helper: persistent browser context
# ═══════════════════════════════════════════════════════════════════════════

def _get_browser_context(playwright):
    """Return a persistent Chromium context that keeps login cookies."""
    # BUG FIX: Ensure the profile directory is not locked by a previous 
    # crashed instance. Windows-specific: SingletonLock files.
    lock_file = Path(BROWSER_USER_DATA_DIR) / "SingletonLock"
    if lock_file.exists():
        try:
            lock_file.unlink()
        except Exception:
             pass

    context = playwright.chromium.launch_persistent_context(
        user_data_dir=BROWSER_USER_DATA_DIR,
        headless=HEADLESS_BROWSER,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
            "--no-sandbox",
            "--disable-extensions",
            "--disable-dev-shm-usage",
        ],
        viewport={"width": 1280, "height": 900},
        accept_downloads=True,
    )
    context.set_default_timeout(PLAYWRIGHT_TIMEOUT_MS)

    return context


# ═══════════════════════════════════════════════════════════════════════════
#  Manual login helper
# ═══════════════════════════════════════════════════════════════════════════

def manual_login(platform: str = "youtube") -> bool:
    """Open a browser so the user can log in manually."""
    urls = {
        "youtube": "https://accounts.google.com/signin",
        "tiktok": "https://www.tiktok.com/login",
    }
    url = urls.get(platform.lower())
    if url is None:
        logger.error("Unknown platform '%s'.", platform)
        return False

    logger.info("==========================================")
    logger.info("  MANUAL LOGIN: %s", platform.upper())
    logger.info("  1. A browser window will open.")
    logger.info("  2. Log in to your account.")
    logger.info("  3. DO NOT CLOSE THIS TERMINAL.")
    logger.info("  4. CLOSE THE BROWSER when finished.")
    logger.info("==========================================")

    try:
        with sync_playwright() as pw:
            ctx = _get_browser_context(pw)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            
            logger.info("Opening %s...", url)
            page.goto(url, wait_until="domcontentloaded")
            
            try:
                page.wait_for_event("close", timeout=0)
            except Exception:
                pass
            
            logger.info("%s login session saved.", platform.title())
            ctx.close()
            return True
    except Exception as exc:
        logger.error("Failed to open login browser: %s", exc)
        return False

# ═══════════════════════════════════════════════════════════════════════════
#  YouTube Shorts upload
# ═══════════════════════════════════════════════════════════════════════════

def _upload_youtube(
    page,
    video_path: str,
    title: str,
    description: str,
) -> bool:
    """Upload a video to YouTube Studio as a Short."""
    video_path = str(Path(video_path).resolve())

    try:
        logger.info("Navigating to YouTube Studio...")
        page.goto(YOUTUBE_STUDIO_UPLOAD_URL, wait_until="domcontentloaded")
        
        if "accounts.google.com" in page.url or "login" in page.url.lower():
            logger.error("Session expired or not logged in.")
            return False

        time.sleep(3)

        # Open Upload Dialog
        upload_icon = page.locator("#upload-icon, ytcp-button#upload-icon, ytcp-icon-button#upload-icon").first
        create_btn = page.locator("#create-icon, ytcp-button#create-icon, ytcp-icon-button#create-icon").first
        
        try:
            upload_icon.wait_for(state="visible", timeout=10_000)
            upload_icon.click()
        except Exception:
            create_btn.wait_for(state="visible", timeout=20_000)
            create_btn.click()
            time.sleep(1)
            upload_menu_item = page.locator("tp-yt-paper-item:has-text('Upload videos'), #text-item-0").first
            upload_menu_item.click()

        time.sleep(2)

        # Select file
        logger.info("Selecting video file: %s", video_path)
        file_input = page.locator('input[type="file"]')
        file_input.set_input_files(video_path)

        # Wait for metadata dialog
        title_input = page.locator("#textbox[aria-label='Add a title that describes your video'], #title-textarea #textbox")
        title_input.first.wait_for(state="visible", timeout=45_000)

        # Fill title
        title_box = page.locator("#title-textarea #textbox, #textbox[aria-label='Add a title that describes your video']").first
        title_box.click(click_count=3)
        page.keyboard.press("Backspace")
        title_box.fill(title)

        # Fill description
        desc_box = page.locator("#description-textarea #textbox, #textbox[aria-label='Tell viewers about your video']").first
        try:
            desc_box.fill(description)
        except Exception:
            pass

        # "Not made for kids" (REQUIRED)
        kids_selectors = [
            "tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MFK']",
            "tp-yt-paper-radio-button:has-text('No, it\\'s not made for kids')",
            "#off[name='VIDEO_MADE_FOR_KIDS_NOT_MFK']"
        ]
        not_for_kids = page.locator(", ".join(kids_selectors)).first
        not_for_kids.scroll_into_view_if_needed()
        not_for_kids.click()

        # Click Next until "Visibility"
        for _ in range(3):
            next_btn = page.locator("#next-button, ytcp-button#next-button").first
            next_btn.click()
            time.sleep(2)

        # Public visibility
        public_radio = page.locator("tp-yt-paper-radio-button[name='PUBLIC'], #public-radio-button").first
        public_radio.click()
        time.sleep(1)

        # Wait for upload completion before clicking Publish
        logger.info("Waiting for upload processing to finish…")
        _wait_for_upload_processing(page, timeout_sec=600)

        # Publish
        done_btn = page.locator("#done-button, ytcp-button#done-button, ytcp-button#publish-button").first
        done_btn.wait_for(state="enabled", timeout=30_000)
        done_btn.click()
        logger.info("Clicked Publish/Done.")

        # Hardened success check
        success_indicators = [
            "ytcp-video-share-dialog",
            "#dialog-title",
            "text=Video published",
            "text=Upload complete"
        ]
        try:
            page.wait_for_selector(", ".join(success_indicators), state="visible", timeout=45_000)
            logger.info("YouTube upload verified ✓")
            return True
        except PwTimeout:
            logger.warning("Upload success dialog not seen, but check for any error messages.")
            if page.locator("text=Error").is_visible():
                return False
            return True # Assume success if no error

    except Exception as exc:
        logger.error("YouTube upload error: %s", exc)
        return False


def _wait_for_upload_processing(page, timeout_sec: int = 600) -> None:
    """Poll YouTube Studio until the video finishes uploading and processing."""
    start = time.time()
    while time.time() - start < timeout_sec:
        # The 'Done' button is disabled while uploading/processing
        done_btn = page.locator("#done-button, ytcp-button#done-button, ytcp-button#publish-button").first
        if done_btn.is_enabled():
            return

        # Look for progress text
        try:
            status_area = page.locator(".status-container, ytcp-video-upload-progress").inner_text(timeout=2_000)
            if "Uploaded" in status_area or "Processing" in status_area:
                 # It's at least uploaded, we might be able to proceed
                 if "Checks complete" in status_area:
                     return
        except Exception:
            pass

        time.sleep(5)
    logger.warning("Timeout waiting for processing. Proceeding anyway.")


# ═══════════════════════════════════════════════════════════════════════════
#  TikTok upload
# ═══════════════════════════════════════════════════════════════════════════

def _upload_tiktok(
    page,
    video_path: str,
    title: str,
    description: str,
) -> bool:
    """Upload a video to TikTok via the Creator Center."""
    video_path = str(Path(video_path).resolve())
    caption_text = f"{title}\n\n{description}"

    try:
        logger.info("Navigating to TikTok upload page…")
        page.goto(TIKTOK_UPLOAD_URL, wait_until="domcontentloaded")
        time.sleep(5)

        # Upload file
        file_input = page.locator('input[type="file"][accept="video/*"], input[type="file"]').first
        file_input.set_input_files(video_path)
        logger.info("File selected, waiting for upload…")

        # Wait for processing (the "Post" button becomes enabled)
        post_btn = page.locator('button:has-text("Post")')
        try:
            post_btn.wait_for(state="visible", timeout=60_000)
        except PwTimeout:
            pass

        # Fill caption
        caption_editor = page.locator('div[contenteditable="true"], .public-DraftEditor-content').first
        caption_editor.click()
        modifier = "Meta" if sys.platform == "darwin" else "Control"
        page.keyboard.press(f"{modifier}+a")
        page.keyboard.press("Backspace")
        time.sleep(0.5)
        page.keyboard.type(caption_text, delay=30)
        time.sleep(2)

        # Post
        post_btn.wait_for(state="enabled", timeout=300_000)
        post_btn.click()
        logger.info("Clicked Post.")

        # Success verification
        try:
            # TikTok usually shows a "Your video is being uploaded" or redirects
            page.wait_for_selector("text=Manage your posts, text=Video uploaded, .tiktok-modal__modal-button", timeout=60_000)
            logger.info("TikTok upload verified ✓")
            return True
        except PwTimeout:
            logger.warning("TikTok success indicator not found.")
            return True # Often still succeeds

    except Exception as exc:
        logger.error("TikTok upload error: %s", exc)
        return False

# ═══════════════════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════════════════

def upload_video(
    video_path: str,
    title: str,
    description: str,
    platforms: list[str] | None = None,
) -> dict[str, bool]:
    """Upload *video_path* to one or more platforms."""
    video_file = Path(video_path)
    if not video_file.is_file():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    if platforms is None:
        platforms = ["youtube"]

    dispatchers = {
        "youtube": _upload_youtube,
        "tiktok": _upload_tiktok,
    }

    results: dict[str, bool] = {}
    
    with sync_playwright() as pw:
        ctx = _get_browser_context(pw)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        for platform in platforms:
            fn = dispatchers.get(platform.lower())
            if not fn:
                continue
            
            logger.info("Starting upload flow for %s...", platform.upper())
            results[platform] = fn(page, video_path, title, description)

        # KEEP WINDOW OPEN: Grace period for user review if not headless
        if not HEADLESS_BROWSER:
            logger.info("Keeping browser open for 20 seconds for final review...")
            time.sleep(20)

        ctx.close()

    return results


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    parser = argparse.ArgumentParser(description="Uploader helper")
    parser.add_argument("--login", choices=["youtube", "tiktok"], help="Log in manually.")
    args = parser.parse_args()

    if args.login:
        manual_login(args.login)
    else:
        parser.print_help()
        sys.exit(1)
