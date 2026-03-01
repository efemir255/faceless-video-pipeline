"""
config.py — Central configuration for the Faceless Video Pipeline.

Stores API keys, default paths, video resolution, TTS voice settings,
and Playwright browser context paths. Values can be overridden via
environment variables where noted.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# BUG FIX: Set the event loop policy to Proactor on Windows as early as possible.
# This is required for Playwright to manage subprocesses correctly.
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

# ─── Load .env file (if present) ────────────────────────────────────────
# BUG FIX: Explicitly resolve .env relative to this file's directory,
# not the current working directory (which varies depending on how the
# app is launched: `streamlit run app.py` vs `python app.py` vs IDE).
_THIS_DIR = Path(__file__).resolve().parent
load_dotenv(_THIS_DIR / ".env")

# ─── Logging ─────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s  %(levelname)-8s  [%(name)s]  %(message)s",
    datefmt="%H:%M:%S",
)

# ─── Project Root ────────────────────────────────────────────────────────
PROJECT_ROOT = _THIS_DIR

# ─── Output Directories ─────────────────────────────────────────────────
OUTPUT_DIR = PROJECT_ROOT / "output"
AUDIO_DIR = OUTPUT_DIR / "audio"
VIDEO_DIR = OUTPUT_DIR / "video"
FINAL_DIR = OUTPUT_DIR / "final"
ASSETS_DIR = PROJECT_ROOT / "assets"
BACKGROUNDS_DIR = ASSETS_DIR / "backgrounds"

# Create directories on import so other modules never hit FileNotFoundError
for _dir in (AUDIO_DIR, VIDEO_DIR, FINAL_DIR, BACKGROUNDS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# ─── Video Categories (Local Assets) ────────────────────────────────────
# Mapping of user-friendly names to keywords for Pexels or local subdirectories
VIDEO_CATEGORIES = {
    "Minecraft Parkour": "minecraft",
    "GTA 5 Gameplay": "gta5",
    "Subway Surfers": "subway_surfers",
    "Soap Cutting": "soap_cutting",
    "Satisfying": "satisfying",
    "Nature": "nature",
}

# ─── Pexels API ──────────────────────────────────────────────────────────
# Get a free key at https://www.pexels.com/api/
# Set as env var PEXELS_API_KEY in your .env file.
PEXELS_API_KEY: str = os.getenv("PEXELS_API_KEY", "")

# BUG FIX: Warn at import time if the key is missing — better than a
# confusing 401 error from the Pexels API at runtime.
if not PEXELS_API_KEY:
    logging.getLogger(__name__).warning(
        "PEXELS_API_KEY is not set. Video fetching will fail. "
        "Create a .env file with your key (see .env.example)."
    )

# ─── Video Settings ──────────────────────────────────────────────────────
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30

# ─── TTS (edge-tts) ─────────────────────────────────────────────────────
# Full list of voices:  edge-tts --list-voices
DEFAULT_TTS_VOICE = "en-US-ChristopherNeural"

# ─── Playwright / Browser Automation ────────────────────────────────────
# Persistent browser profile so you only log in once.
BROWSER_USER_DATA_DIR = str(PROJECT_ROOT / ".browser_profile")

# Timeout (ms) for Playwright actions (navigation, clicks, uploads, etc.)
PLAYWRIGHT_TIMEOUT_MS = 120_000  # 2 minutes

# ─── Reddit API ──────────────────────────────────────────────────────────
# Get a key at https://www.reddit.com/prefs/apps
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "FacelessVideoPipeline/0.1.0")

# Run Playwright in headless mode? (True/False)
# HEADLESS_BROWSER=true/false in .env
HEADLESS_BROWSER = os.getenv("HEADLESS_BROWSER", "false").lower() == "true"

# ─── Platform URLs ───────────────────────────────────────────────────────
YOUTUBE_STUDIO_UPLOAD_URL = "https://studio.youtube.com"
TIKTOK_UPLOAD_URL = "https://www.tiktok.com/creator#/upload?scene=creator_center"
