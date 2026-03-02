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
from concurrent.futures import ThreadPoolExecutor

import requests

from config import PEXELS_API_KEY, VIDEO_DIR, BACKGROUNDS_DIR

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
    # Prefer height closest to 1920 for vertical video quality/performance balance
    video_files.sort(key=lambda f: abs(f.get("height", 1920) - 1920))
    download_url = video_files[0].get("link")

    logger.info("Downloading Pexels video: %s (height: %s)", download_url, video_files[0].get("height"))
    _download_file(download_url, output_path)
    return str(output_path.resolve())


def get_clips_for_script(
    script: str,
    total_duration: float,
    base_keyword: str = "nature",
    use_local_backgrounds: bool = False,
    local_category: str = None,
) -> list[dict]:
    """
    Split script into segments, fetch a relevant clip for each,
    and return a list of (path, duration) dicts.
    """
    if use_local_backgrounds:
        return _get_local_clips(total_duration, local_category)
    # ── 1. Split script into segments ──
    script_clean = script.replace("\n", " ").strip()
    raw_sentences = re.split(r'(?<=[.!?])\s+', script_clean)
    sentences = [s.strip() for s in raw_sentences if len(s.strip()) > 2]

    if not sentences:
        sentences = [script_clean] if script_clean else ["..."]

    # Group sentences into segments of ~8-10 seconds to avoid excessive downloads
    total_words = max(len(script.split()), 1)
    words_per_sec = total_words / total_duration if total_duration > 0 else 3
    target_segment_words = words_per_sec * 8  # Target 8 seconds per clip

    segments = []
    curr_seg = []
    curr_words = 0
    for s in sentences:
        s_words = len(s.split())
        curr_seg.append(s)
        curr_words += s_words
        if curr_words >= target_segment_words:
            segments.append(" ".join(curr_seg))
            curr_seg = []
            curr_words = 0
    if curr_seg:
        if segments:
            segments[-1] += " " + " ".join(curr_seg)
        else:
            segments.append(" ".join(curr_seg))

    clips_metadata = []

    def fetch_clip(i, text):
        sent_words = len(text.split())
        sent_duration = (sent_words / total_words) * total_duration
        # Use first 2 words of the segment + base keyword for search
        snippet = " ".join(text.split()[:2])
        keyword = f"{base_keyword} {snippet}".strip()
        
        try:
            filename = f"clip_{i:03d}.mp4"
            path = VIDEO_DIR / filename
            logger.info("Fetching clip %d/%d for: %s", i+1, len(segments), keyword)
            clip_path = get_background_video(keyword, sent_duration, output_path=path)
            return {"path": clip_path, "duration": sent_duration, "index": i}
        except Exception as exc:
            logger.warning("Failed to fetch clip for '%s': %s", keyword, exc)
            return {"path": None, "duration": sent_duration, "index": i}

    # Parallel fetch using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(lambda p: fetch_clip(*p), enumerate(segments)))

    # Sort by index to maintain original order
    results.sort(key=lambda r: r["index"])

    # Fill in fallbacks for failed downloads
    for i, res in enumerate(results):
        if res["path"] is None:
            if i > 0 and results[i-1]["path"]:
                res["path"] = results[i-1]["path"]
            else:
                # Absolute fallback to nature
                path = VIDEO_DIR / f"clip_{i:03d}.mp4"
                res["path"] = get_background_video("nature", res["duration"], output_path=path)
        clips_metadata.append({"path": res["path"], "duration": res["duration"]})

    return clips_metadata


def _download_file(url: str, output_path: Path) -> None:
    """Helper to download a file with temp-rename protection."""
    logger.info("Starting download to %s...", output_path.name)
    dl_resp = _session.get(url, stream=True, timeout=120)
    dl_resp.raise_for_status()

    total_size = int(dl_resp.headers.get('content-length', 0))
    downloaded = 0

    tmp_path = output_path.with_suffix(".tmp")
    with open(tmp_path, "wb") as fh:
        for chunk in dl_resp.iter_content(chunk_size=512 * 1024):
            if chunk:
                fh.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    done = int(50 * downloaded / total_size)
                    # Use stderr for progress to keep stdout clean for potential piping
                    print(f"\r[{'=' * done}{' ' * (50-done)}] {downloaded/1024/1024:.1f}MB / {total_size/1024/1024:.1f}MB", end="", flush=True)

    print() # New line after progress bar
    tmp_path.replace(output_path)
    logger.info("Download complete: %s", output_path.name)


def _get_local_clips(total_duration: float, category: str = None) -> list[dict]:
    """
    Search assets/backgrounds/{category} for MP4 files. If category is not provided,
    search in the root BACKGROUNDS_DIR.
    """
    search_dir = BACKGROUNDS_DIR
    if category:
        search_dir = BACKGROUNDS_DIR / category
        if not search_dir.exists():
            logger.warning("Category subdirectory %s does not exist. Using root.", search_dir)
            search_dir = BACKGROUNDS_DIR

    local_files = list(search_dir.glob("*.mp4"))
    if not local_files:
        # Check subdirectories if root is empty and no category was specified
        if search_dir == BACKGROUNDS_DIR:
            local_files = list(BACKGROUNDS_DIR.glob("**/*.mp4"))

    if not local_files:
        logger.warning("No local backgrounds found in %s.", search_dir)
        raise FileNotFoundError(f"No local background videos found in {search_dir}")

    chosen = random.choice(local_files)
    logger.info("Using local background: %s", chosen.name)

    # For local backgrounds, we usually just use one long clip and let the engine
    # handle it, but to match the multi-clip pipeline we return one segment.
    # The engine will loop it if needed.
    return [{"path": str(chosen.resolve()), "duration": total_duration}]
