"""
bgm_fetcher.py — Simple BGM management.
"""

import random
import logging
from pathlib import Path
from config import BGM_DIR

logger = logging.getLogger(__name__)

def get_random_bgm() -> Path | None:
    """Returns a path to a random BGM file in the BGM directory."""
    bgm_files = list(BGM_DIR.glob("*.mp3")) + list(BGM_DIR.glob("*.wav"))
    if not bgm_files:
        logger.warning("No BGM files found in %s", BGM_DIR)
        return None
    return random.choice(bgm_files)
