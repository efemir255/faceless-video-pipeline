#!/usr/bin/env python
"""Quick script to recover corrupted final_video.mp4 using ffmpeg remux."""
import subprocess
from pathlib import Path

try:
    import imageio_ffmpeg as iioff
    ffmpeg = iioff.get_ffmpeg_exe()
except Exception as e:
    print(f"Error getting ffmpeg: {e}")
    ffmpeg = None

if not ffmpeg:
    print("ffmpeg not available")
    exit(1)

src = Path("output/final/final_video.mp4")
dest = Path("output/final/final_video_recovered.mp4")

if not src.exists():
    print(f"{src} not found")
    exit(1)

print(f"Attempting to remux {src} -> {dest}")
try:
    result = subprocess.run(
        [ffmpeg, "-y", "-i", str(src), "-c", "copy", "-movflags", "+faststart", str(dest)],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print("✓ Remux succeeded")
        # Verify the recovered file
        ver = subprocess.run([ffmpeg, "-v", "error", "-i", str(dest), "-f", "null", "-"], capture_output=True, text=True)
        if ver.returncode == 0:
            print("✓ Recovered file verified OK")
            # Replace original with recovered
            src.unlink()
            dest.rename(src)
            print(f"✓ Replaced {src}")
        else:
            print(f"✗ Recovered file failed verification: {ver.stderr}")
    else:
        print(f"✗ Remux failed:\n{result.stderr}")
except Exception as e:
    print(f"✗ Error: {e}")
    exit(1)
