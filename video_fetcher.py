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
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from urllib3.util import Retry
from requests.adapters import HTTPAdapter

from config import PEXELS_API_KEY, VIDEO_DIR

logger = logging.getLogger(__name__)

_PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"

# Shared requests session with automatic retries for stability
_session = requests.Session()
_retries = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
_session.mount("https://", HTTPAdapter(max_retries=_retries))


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


def split_script_into_sentences(script: str) -> list[str]:
    """Split script into a list of sentences/segments for video processing."""
    raw_segments = re.split(r'(?<=[.!?])\s+', script.replace("\n", " "))
    sentences = [s.strip() for s in raw_segments if len(s.strip()) > 5]

    if not sentences:
        sentences = [script.strip()]
    return sentences


def get_clips_for_script(
    script: str,
    total_duration: float,
    base_keyword: str = "nature",
) -> list[dict]:
    """
    Split script into segments, fetch relevant clips in parallel,
    and return a list of (path, duration) dicts.
    """
    # ── 1. Split script into segments ──
    sentences = split_script_into_sentences(script)

    # Recalculate word counts based only on sentences we actually use
    all_sentence_words = [len(s.split()) for s in sentences]
    total_sentence_words = sum(all_sentence_words)
    if total_sentence_words == 0:
        total_sentence_words = 1  # Avoid ZeroDivisionError

    # List of (keyword, duration, output_path) tasks
    tasks = []
    # Common words to filter out for cleaner keywords
    stop_words = {"the", "and", "a", "an", "is", "are", "of", "to", "in", "it", "that", "this", "for", "with", "as", "at"}

    for i, sentence in enumerate(sentences):
        sent_words = all_sentence_words[i]
        # Percentage of total duration this sentence takes
        sent_duration = (sent_words / total_sentence_words) * total_duration
        
        # Refine keyword: remove punctuation and filter stop words
        clean_words = [w.lower() for w in re.findall(r'\b\w+\b', sentence) if w.lower() not in stop_words]
        snippet = " ".join(clean_words[:3])

        keyword = f"{base_keyword} {snippet}".strip()
        path = VIDEO_DIR / f"clip_{i:03d}.mp4"
        
        tasks.append((keyword, sent_duration, path, i))

    clips_metadata = [None] * len(tasks)

    def _fetch_task(task):
        kw, dur, path, idx = task
        logger.info("Fetching clip %d: '%s' (%.1fs)", idx+1, kw, dur)
        try:
            p = get_background_video(kw, dur, output_path=path)
            return {"path": p, "duration": dur, "idx": idx}
        except Exception as exc:
            logger.warning("Failed to fetch '%s': %s. Using fallback.", kw, exc)
            try:
                p = get_background_video("nature", dur, output_path=path)
                return {"path": p, "duration": dur, "idx": idx}
            except Exception:
                return None

    # Run downloads in parallel
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(_fetch_task, tasks))

    # Fill in the metadata, handling failures
    for res in results:
        if res:
            clips_metadata[res["idx"]] = {"path": res["path"], "duration": res["duration"]}

    # Final pass: fill any gaps with neighboring clips
    for i in range(len(clips_metadata)):
        if clips_metadata[i] is None:
            # Try to find the nearest non-None neighbor to copy
            neighbor = None
            # Look backwards first
            for j in range(i - 1, -1, -1):
                if clips_metadata[j] is not None:
                    neighbor = clips_metadata[j]
                    break

            # If not found, look forwards
            if neighbor is None:
                for j in range(i + 1, len(clips_metadata)):
                    if clips_metadata[j] is not None:
                        neighbor = clips_metadata[j]
                        break

            if neighbor:
                clips_metadata[i] = neighbor.copy()
            else:
                # This is a dire failure case, should rarely happen
                raise RuntimeError(f"Could not fetch ANY clips for script.")

    return clips_metadata


import time

def _download_file(url: str, output_path: Path) -> None:
    """Helper to download a file with temp-rename protection and retries."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            dl_resp = _session.get(url, stream=True, timeout=120)
            dl_resp.raise_for_status()

            tmp_path = output_path.with_suffix(".tmp")
            with open(tmp_path, "wb") as fh:
                for chunk in dl_resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        fh.write(chunk)

            tmp_path.replace(output_path)
            return
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error("Failed to download %s after %d attempts: %s", url, max_retries, e)
                raise
            logger.warning("Download attempt %d failed for %s: %s. Retrying...", attempt + 1, url, e)
            time.sleep(2 ** attempt)
