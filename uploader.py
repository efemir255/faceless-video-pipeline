"""
uploader.py — Auto-upload finished videos to YouTube Shorts and TikTok.

Uses Playwright with a **persistent browser context** so you only need
to log in manually once.  After that, uploads are fully automated.

First-time setup
----------------
1. Run ``python uploader.py --login youtube`` (or ``tiktok``).
2. A Chromium window opens — log into your account manually.
3. Close the browser.  Your session cookies are now saved.
4. All future uploads reuse those cookies automatically.

DOM selectors are clearly labelled so you can adjust them when
platforms update their UIs.
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

import shutil

def _get_browser_context(playwright):
    """Return a persistent Chromium context that keeps login cookies."""
    # BUG FIX: Ensure the profile directory is not locked by a previous 
    # crashed instance. Handles multiple types of lock files across OSs.
    profile_path = Path(BROWSER_USER_DATA_DIR)
    if profile_path.exists():
        for lock_name in ["SingletonLock", "SingletonCookie", "SingletonSocket"]:
            lock_file = profile_path / lock_name
            if lock_file.exists():
                try:
                    if lock_file.is_symlink():
                        lock_file.unlink()
                    else:
                        shutil.rmtree(lock_file) if lock_file.is_dir() else lock_file.unlink()
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
            "--disable-dev-shm-usage",  # Added for stability
        ],
        viewport={"width": 1280, "height": 900},
        accept_downloads=True,
    )
    context.set_default_timeout(PLAYWRIGHT_TIMEOUT_MS)

    # Note: launch_persistent_context opens one page by default.
    return context


# ═══════════════════════════════════════════════════════════════════════════
#  Manual login helper
# ═══════════════════════════════════════════════════════════════════════════

def manual_login(platform: str = "youtube") -> bool:
    """
    Open a browser so the user can log in manually.
    Returns True if the browser was opened and closed, False on error.
    """
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
            # We use a non-persistent context for the initial login check 
            # if we wanted to be super safe, but using the persistent one 
            # is correct to SAVE the state.
            ctx = _get_browser_context(pw)
            # Use the first page created by launch_persistent_context
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            
            logger.info("Opening %s...", url)
            page.goto(url, wait_until="domcontentloaded")
            
            # Keep the browser open until the user closes it.
            # We set a very long timeout (10 mins) just in case, but usually 0 is fine.
            try:
                page.wait_for_event("close", timeout=0)
            except Exception:
                # If wait_for_event fails or is interrupted, we still want to close.
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
    """
    Upload a video to YouTube Studio as a Short.
    Accepts an existing 'page' object to avoid navigation/session issues.
    """
    video_path = str(Path(video_path).resolve())

    try:
        # 1 — Navigate to YouTube Studio
        logger.info("Navigating to YouTube Studio...")
        page.goto(YOUTUBE_STUDIO_UPLOAD_URL, wait_until="domcontentloaded")
        
        # Check if we got redirected to a login page
        if "accounts.google.com" in page.url or "login" in page.url.lower():
            logger.error("Session expired or not logged in. Redirected to: %s", page.url)
            return False

        # Give it a bit more time to settle
        try:
            page.wait_for_load_state("load", timeout=10_000)
        except Exception:
            logger.warning("Page did not reach 'load' state in 10s, proceeding anyway.")
        time.sleep(3)

        # 2 & 3 — Open Upload Dialog
        logger.debug("Looking for Upload/Create button...")
        
        upload_icon = page.locator("#upload-icon, ytcp-button#upload-icon, ytcp-icon-button#upload-icon").first
        create_btn = page.locator("#create-icon, ytcp-button#create-icon, ytcp-icon-button#create-icon").first
        
        try:
            # 1. Try clicking the direct "Upload" icon (arrow up)
            upload_icon.wait_for(state="visible", timeout=10_000)
            upload_icon.click()
            logger.debug("Clicked direct '#upload-icon'.")
        except Exception:
            logger.debug("'#upload-icon' not visible, trying '#create-icon' dropdown...")
            try:
                # 2. Fallback to "Create" button -> "Upload videos"
                create_btn.wait_for(state="visible", timeout=20_000)
                create_btn.click()
                logger.debug("Clicked 'Create' button.")
                time.sleep(1)
                
                upload_menu_item = page.locator("tp-yt-paper-item:has-text('Upload videos'), #text-item-0").first
                upload_menu_item.wait_for(state="visible", timeout=10_000)
                upload_menu_item.click()
                logger.debug("Clicked 'Upload videos' menu item.")
            except Exception as e:
                logger.error("Failed to open upload dialog: %s", e)
                raise

        time.sleep(2)

        # 4 — Select file via the hidden <input type="file">
        logger.info("Selecting video file: %s", video_path)
        file_input = page.locator('input[type="file"]')
        file_input.set_input_files(video_path)

        # BUG FIX: Wait for the upload dialog to actually appear
        logger.info("Uploading file, waiting for metadata dialog…")
        # Selector for the title box which appears after upload starts
        title_input = page.locator("#textbox[aria-label='Add a title that describes your video'], #title-textarea #textbox")
        try:
            title_input.first.wait_for(state="visible", timeout=45_000)
            logger.info("Metadata dialog detected.")
        except Exception as e:
            logger.error("Metadata dialog did not appear after upload: %s", e)
            # Sometimes the upload fails silently or takes too long
            return False

        # 5 — Fill in title
        # BUG FIX: Use more robust title selectors
        title_box = page.locator("#title-textarea #textbox, #textbox[aria-label='Add a title that describes your video']").first
        title_box.wait_for(state="visible", timeout=20_000)
        title_box.click(click_count=3)
        page.keyboard.press("Backspace")
        title_box.fill(title)
        logger.debug("Filled title: %s", title)

        # 6 — Fill in description
        # BUG FIX: Handle the description box more reliably
        desc_box = page.locator("#description-textarea #textbox, #textbox[aria-label='Tell viewers about your video']").first
        try:
            desc_box.wait_for(state="visible", timeout=15_000)
            desc_box.click()
            desc_box.fill(description)
            logger.debug("Filled description.")
        except Exception as e:
            logger.warning("Could not fill description: %s", e)

        # 7 — Set "Not made for kids" (REQUIRED)
        # BUG FIX: This is critical. Use text-based and name-based selectors.
        logger.debug("Setting 'Not made for kids'...")
        kids_selectors = [
            "tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MFK']",
            "tp-yt-paper-radio-button:has-text('No, it\\'s not made for kids')",
            "#made-for-kids-group #off",
            "ytkc-made-for-kids-select #off"
        ]
        not_for_kids = page.locator(", ".join(kids_selectors)).first
        try:
            not_for_kids.scroll_into_view_if_needed()
            not_for_kids.wait_for(state="visible", timeout=15_000)
            not_for_kids.click()
            logger.debug("Selected 'Not made for kids'.")
        except Exception as e:
            logger.error("MANDATORY STEP FAILED: Could not click 'Not made for kids': %s", e)
            raise RuntimeError(f"Could not select 'Not made for kids': {e}")

        # 8 — Click through Next until "Visibility" step
        logger.debug("Clicking Next buttons...")
        for step in range(3):
            next_btn = page.locator("#next-button, ytcp-button#next-button").first
            next_btn.wait_for(state="visible", timeout=15_000)
            next_btn.click()
            logger.debug("Clicked Next (%d/3)", step + 1)
            time.sleep(2)

        # 9 — Select "Public" (Visibility)
        logger.debug("Setting visibility to Public...")
        visibility_selectors = [
            "tp-yt-paper-radio-button[name='PUBLIC']",
            "tp-yt-paper-radio-button:has-text('Public')",
            "#privacy-group #public-radio-button",
            "[name='privacy_group'] [value='PUBLIC']"
        ]
        public_radio = page.locator(", ".join(visibility_selectors)).first
        try:
            public_radio.wait_for(state="visible", timeout=15_000)
            public_radio.click()
            logger.debug("Selected 'Public' visibility.")
        except Exception as e:
            logger.error("Could not select Public: %s", e)

        time.sleep(1)

        # Wait until YouTube finishes processing
        logger.info("Waiting for upload processing to finish…")
        _wait_for_upload_processing(page, timeout_sec=300)

        # 10 — Publish (Re-locate the button to avoid stale element issues)
        done_btn = page.locator("#done-button, ytcp-button#done-button, ytcp-button#publish-button").first
        done_btn.wait_for(state="visible", timeout=15_000)
        done_btn.click()

        # BUG FIX: Wait for the success dialog
        try:
            page.wait_for_selector(
                "ytcp-video-share-dialog, #dialog-title",
                state="visible",
                timeout=30_000,
            )
            logger.info("YouTube upload complete ✓")
        except PwTimeout:
            logger.warning("Success dialog not detected, but upload may have completed.")

        return True

    except PwTimeout as exc:
        logger.error("YouTube upload timed out: %s", exc)
        return False
    except Exception as exc:
        logger.error("YouTube upload error: %s", exc)
        return False

    return False


def _wait_for_upload_processing(page, timeout_sec: int = 300) -> None:
    """
    Poll YouTube Studio until the video finishes processing.

    YouTube shows a progress text like "Uploading 45%…" or "Processing…"
    and the Done button stays disabled until it's ready. We watch for the
    progress text to disappear or the button to become enabled.
    """
    start = time.time()
    last_log_time = start
    poll_interval = 3  # seconds

    while time.time() - start < timeout_sec:
        # Check if Done button is enabled (no "disabled" attribute)
        done_btn = page.locator("#done-button")
        is_disabled = done_btn.get_attribute("disabled")
        if is_disabled is None:
            # Button is enabled — processing is done
            return

        now = time.time()
        elapsed = int(now - start)
        if now - last_log_time >= 15:
            # Check for progress text periodically to log status
            try:
                progress = page.locator(".progress-label").inner_text(timeout=2_000)
                logger.info("Upload progress: %s (%ds elapsed)", progress, elapsed)
            except Exception:
                logger.info("Waiting for processing… (%ds elapsed)", elapsed)
            last_log_time = now

        time.sleep(poll_interval)

    logger.warning("Upload processing timed out after %ds — clicking Done anyway.", timeout_sec)


# ═══════════════════════════════════════════════════════════════════════════
#  TikTok upload
# ═══════════════════════════════════════════════════════════════════════════

def _upload_tiktok(
    page,
    video_path: str,
    title: str,
    description: str,
) -> bool:
    """
    Upload a video to TikTok via the Creator Center web uploader.
    Accepts an existing 'page' object.
    """
    video_path = str(Path(video_path).resolve())
    caption_text = f"{title}\n\n{description}"

    try:
        # 1 — Navigate to TikTok upload page
        logger.info("Navigating to TikTok upload page…")
        page.goto(TIKTOK_UPLOAD_URL, wait_until="domcontentloaded")
        time.sleep(5)

        # 2 — Upload file
        file_input = page.locator('input[type="file"][accept="video/*"]')
        try:
            file_input.wait_for(state="attached", timeout=10_000)
        except PwTimeout:
            file_input = page.locator('input[type="file"]').first

        file_input.set_input_files(video_path)
        logger.info("File selected, waiting for processing…")
        time.sleep(8)

        # 3 — Fill caption
        caption_editor = page.locator('div[contenteditable="true"]').first
        caption_editor.wait_for(state="visible", timeout=15_000)
        caption_editor.click()

        modifier = "Meta" if sys.platform == "darwin" else "Control"
        page.keyboard.press(f"{modifier}+a")
        page.keyboard.press("Backspace")
        time.sleep(0.5)

        page.keyboard.type(caption_text, delay=30)
        time.sleep(2)

        # 4 — Post
        post_btn = page.locator('button:has-text("Post")')
        post_btn.wait_for(state="visible", timeout=15_000)
        post_btn.click()

        try:
            page.wait_for_url("**/manage**", timeout=30_000)
            logger.info("TikTok upload complete ✓")
        except PwTimeout:
            logger.warning("Post-upload redirect not detected.")

        return True

    except PwTimeout as exc:
        logger.error("TikTok upload timed out: %s", exc)
        return False
    except Exception as exc:
        logger.error("TikTok upload error: %s", exc)
        return False

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
    """
    Upload *video_path* to one or more platforms.

    Parameters
    ----------
    video_path : str
        Absolute path to the final MP4.
    title : str
        Video title / caption.
    description : str
        Video description.
    platforms : list[str] | None
        List of platform names to upload to.
        Supported: ``"youtube"``, ``"tiktok"``.
        Defaults to ``["youtube"]``.

    Returns
    -------
    dict[str, bool]
        Mapping of platform → success status.

    Raises
    ------
    FileNotFoundError
        If *video_path* does not exist.
    """
    # BUG FIX: Validate that the video file actually exists before
    # launching a browser and attempting an upload.
    video_file = Path(video_path)
    if not video_file.is_file():
        raise FileNotFoundError(
            f"Video file not found: {video_path}"
        )

    if platforms is None:
        platforms = ["youtube"]

    dispatchers = {
        "youtube": _upload_youtube,
        "tiktok": _upload_tiktok,
    }

    results: dict[str, bool] = {}
    
    with sync_playwright() as pw:
        ctx = _get_browser_context(pw)
        # Persistent context opens one page by default. Reuse it.
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        for platform in platforms:
            fn = dispatchers.get(platform.lower())
            if fn is None:
                logger.warning("Unknown platform '%s', skipping.", platform)
                results[platform] = False
                continue
            
            logger.info("Starting upload flow for %s...", platform.upper())
            try:
                # We pass the shared page instance so we don't crash 
                # opening/closing targets on Windows.
                results[platform] = fn(page, video_path, title, description)
            except Exception as exc:
                logger.error("%s dispatcher failed: %s", platform.upper(), exc)
                results[platform] = False

        ctx.close()

    return results


# ═══════════════════════════════════════════════════════════════════════════
#  CLI entry point  (python uploader.py --login youtube)
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    parser = argparse.ArgumentParser(description="Uploader helper")
    parser.add_argument(
        "--login",
        choices=["youtube", "tiktok"],
        help="Open a browser to log in manually and save cookies.",
    )
    args = parser.parse_args()

    if args.login:
        manual_login(args.login)
    else:
        parser.print_help()
        sys.exit(1)
