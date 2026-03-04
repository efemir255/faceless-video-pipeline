
import logging
import time
from pathlib import Path

FINAL_DIR = Path("assets/final")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_retention():
    # Cleanup old videos (keep 3 most recent)
    old_videos = sorted(list(FINAL_DIR.glob("final_video_*.mp4")), key=lambda x: x.stat().st_mtime, reverse=True)
    logger.info("Found %d videos", len(old_videos))

    # Logic: keep current (index 0) + 2 old ones (index 1, 2)
    for old_v in old_videos[2:]:
        try:
            logger.info("Unlinking: %s", old_v.name)
            old_v.unlink()
        except Exception as e:
            logger.error("Failed to unlink: %s", e)

if __name__ == "__main__":
    test_retention()
    print("Files remaining:")
    for f in FINAL_DIR.glob("final_video_*.mp4"):
        print(f.name)
