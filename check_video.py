"""Helper script for inspecting the generated MP4 file.

MoviePy 2.x no longer exposes ``moviepy.editor``; clips are imported
directly from the top-level package.  The earlier import was failing
with ``ModuleNotFoundError`` when run in the current environment.
"""

from moviepy import VideoFileClip
import sys
path='output/final/final_video.mp4'
try:
    clip=VideoFileClip(path)
    print('duration',clip.duration,'size',clip.size,'fps',clip.fps)
    clip.reader.close()
    clip.audio.reader.close_proc()
except Exception as e:
    print('error',e)
