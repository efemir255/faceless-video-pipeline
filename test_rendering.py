import logging
import sys
from pathlib import Path
from tts_engine import generate_audio
from video_engine import render_final_video
from config import VIDEO_DIR, FINAL_DIR

# Set up logging to see GPU/CPU logs
logging.basicConfig(level=logging.INFO)

def test_rendering():
    text = "Hello, this is a test of the GPU accelerated rendering and high-impact subtitles."
    audio_path, duration = generate_audio(text)

    # Check if subtitle JSON was created
    sub_path = Path(audio_path).with_suffix(".json")
    if sub_path.exists():
        print(f"SUCCESS: Subtitles generated at {sub_path}")
    else:
        print("FAILURE: Subtitles JSON missing")
        return

    # Create a dummy video list or use an existing one if available
    # For testing, we'll try to find any mp4 in VIDEO_DIR
    existing_videos = list(VIDEO_DIR.glob("*.mp4"))
    if not existing_videos:
        print("No background videos found in output/video/. Fetching one...")
        from video_fetcher import get_background_video
        v_path = get_background_video("nature", duration)
    else:
        v_path = str(existing_videos[0])

    print(f"Using background: {v_path}")

    try:
        final_path = render_final_video(audio_path, v_path)
        print(f"SUCCESS: Final video rendered at {final_path}")
    except Exception as e:
        print(f"FAILURE: Rendering failed: {e}")

if __name__ == "__main__":
    test_rendering()
