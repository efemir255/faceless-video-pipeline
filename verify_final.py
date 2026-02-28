import sys
import os
import importlib
from pathlib import Path

print("Python executable:", sys.executable)
print("Current working directory:", os.getcwd())

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
    "uploader"
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
