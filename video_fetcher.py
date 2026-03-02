"""
video_fetcher.py — Download portrait stock videos from the Pexels API.

Searches for vertical (9:16) videos matching a keyword and downloads
the best-quality MP4 available. If no single video is long enough for
the audio, the shortest acceptable match (or the longest available) is
returned — ``video_engine.py`` will loop it to fit.
"""

import logging
import random
import re
from pathlib import Path

import requests

from config import PEXELS_API_KEY, VIDEO_DIR

logger = logging.getLogger(__name__)

_PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"

# Shared requests session for performance and connection pooling
_session = requests.Session()


def get_background_video(
    keyword: str,
    duration: float,
    output_path: str | Path | None = None,
) -> str:
    """
    Fetch a single portrait-orientation stock video from Pexels.
    (Legacy function for single background mode)
    """
    if not PEXELS_API_KEY:
        raise RuntimeError("PEXELS_API_KEY is not set.")

    if output_path is None:
        output_path = VIDEO_DIR / "background.mp4"
    output_path = Path(output_path)

    # Search and pick
    headers = {"Authorization": PEXELS_API_KEY}
    params = {
        "query": keyword,
        "orientation": "portrait",
        "per_page": 10,
        "size": "large",
    }
    resp = _session.get(_PEXELS_SEARCH_URL, headers=headers, params=params, timeout=15)
    resp.raise_for_status()
    videos = resp.json().get("videos", [])
    if not videos:
        raise RuntimeError(f"No videos found for keyword='{keyword}'")

    # Filter for videos that have mp4 files
    valid_videos = []
    for v in videos:
        mp4_files = [f for f in v.get("video_files", []) if f.get("file_type", "").startswith("video/mp4")]
        if mp4_files:
            v["mp4_files"] = mp4_files
            valid_videos.append(v)

    if not valid_videos:
        raise RuntimeError(f"No MP4 files found for keyword='{keyword}' among {len(videos)} videos.")

    chosen = max(valid_videos, key=lambda v: v.get("duration", 0))
    video_files = chosen["mp4_files"]
    video_files.sort(key=lambda f: f.get("height", 0), reverse=True)
    download_url = video_files[0].get("link")

    _download_file(download_url, output_path)
    return str(output_path.resolve())


def get_clips_for_script(
    script: str,
    total_duration: float,
    base_keyword: str = "nature",
) -> list[dict]:
    """
    Split script into segments, fetch a relevant clip for each,
    and return a list of (path, duration) dicts.
    """
    # ── 1. Split script into segments ──
    # Split by period, exclamation, or question mark using regex
    # Handle common abbreviations to avoid splitting prematurely
    raw_segments = re.split(r'(?<=[.!?])\s+', script.replace("\n", " "))
    sentences = [s.strip() for s in raw_segments if len(s.strip()) > 5]

    if not sentences:
        sentences = [script.strip()]

    # Estimate duration per sentence (simple word count ratio)
    words = script.split()
    total_words = len(words)
    clips_metadata = []

    for i, sentence in enumerate(sentences):
        sent_words = len(sentence.split())
        # Percentage of total duration this sentence takes
        # BUG FIX: Protect against ZeroDivisionError
        safe_total_words = total_words if total_words > 0 else 1
        sent_duration = (sent_words / safe_total_words) * total_duration
        
        # Combine base keyword with a snippet of the sentence
        snippet = " ".join(sentence.split()[:3])
        keyword = f"{base_keyword} {snippet}".strip()
        
        logger.info("Fetching clip for segment %d: '%s' (%.1fs)", i+1, keyword, sent_duration)
        
        try:
            filename = f"clip_{i:03d}.mp4"
            path = VIDEO_DIR / filename
            clip_path = get_background_video(keyword, sent_duration, output_path=path)
            clips_metadata.append({
                "path": clip_path,
                "duration": sent_duration
            })
        except Exception as exc:
            logger.warning("Failed to fetch clip for '%s': %s. Using fallback.", keyword, exc)
            # Fallback to a generic keyword if specific one fails
            if i > 0 and clips_metadata:
                # Reuse previous clip metadata if possible (it will be looped in engine)
                clips_metadata.append(clips_metadata[-1])
            else:
                # Absolute fallback
                path = VIDEO_DIR / f"clip_{i:03d}.mp4"
                clip_path = get_background_video("nature", sent_duration, output_path=path)
                clips_metadata.append({"path": clip_path, "duration": sent_duration})

    return clips_metadata


def _download_file(url: str, output_path: Path) -> None:
    """Helper to download a file with temp-rename protection."""
    dl_resp = _session.get(url, stream=True, timeout=120)
    dl_resp.raise_for_status()

    tmp_path = output_path.with_suffix(".tmp")
    with open(tmp_path, "wb") as fh:
        for chunk in dl_resp.iter_content(chunk_size=1024 * 1024):
            if chunk:
                fh.write(chunk)
    
    tmp_path.replace(output_path)
