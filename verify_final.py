import sys
import os
import importlib
import subprocess
from pathlib import Path

print("Python executable:", sys.executable)
print("Current working directory:", os.getcwd())

# Check for FFmpeg (required by MoviePy)
try:
    res = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
    if res.returncode == 0:
        print("SUCCESS: FFmpeg is installed and accessible.")
    else:
        print("WARNING: FFmpeg found but returned non-zero exit code.")
except FileNotFoundError:
    print("ERROR: FFmpeg is NOT installed or NOT in system PATH. Video rendering will fail.")

# Add root to sys.path for this script
root = str(Path(__file__).resolve().parent)
if root not in sys.path:
    sys.path.insert(0, root)

modules = [
    "streamlit",
    "playwright",
    "edge_tts",
    "requests",
    "config",
    "tts_engine",
    "video_fetcher",
    "video_engine",
    "uploader",
    "reddit_fetcher",
    "praw"
]

failed = []
for m in modules:
    try:
        importlib.import_module(m)
        print(f"SUCCESS: Imported {m}")
    except ImportError as e:
        print(f"FAILURE: Failed to import {m}: {e}")
        failed.append(m)

if failed:
    print(f"\nTotal failures: {len(failed)}")
    sys.exit(1)
else:
    print("\nAll imports internal and external are working correctly.")
    sys.exit(0)
