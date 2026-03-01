"""
video_engine.py — Merge audio + background video into a final 9:16 short.

Uses moviepy to composite the video, looping short clips to match
the audio duration, and exporting a ready-to-upload MP4.
"""

import logging
import random
from pathlib import Path

from moviepy import (
    AudioFileClip,
    VideoFileClip,
    concatenate_videoclips,
    vfx,
)

from config import VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS, FINAL_DIR

logger = logging.getLogger(__name__)


def render_final_video(
    audio_path: str | Path,
    video_source: str | Path | list[dict],
    output_path: str | Path | None = None,
) -> str:
    """
    Composite *audio_path* over *video_source* into a final 1080x1920 MP4.
    
    *video_source* can be:
    - A single path to an MP4 (legacy).
    - A list of dicts like [{"path": "...", "duration": 5.0}, ...].
    """
    audio_path = Path(audio_path)
    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    if output_path is None:
        output_path = FINAL_DIR / "final_video.mp4"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    audio_clip = None
    clips_to_close = []

    try:
        logger.info("Loading audio: %s", audio_path.name)
        audio_clip = AudioFileClip(str(audio_path))
        audio_duration = audio_clip.duration

        if isinstance(video_source, (str, Path)):
            # Single video mode
            video_clips = [_prepare_clip(video_source, audio_duration)]
        else:
            # Multi-clip mode
            video_clips = []
            for item in video_source:
                # Add support for random start offset for longer built-in videos
                random_start = item.get("random_start", False)
                clip = _prepare_clip(item["path"], item["duration"], random_start=random_start)
                video_clips.append(clip)
        
        clips_to_close.extend(video_clips)

        # Stitch clips together
        logger.info("Stitching %d clips...", len(video_clips))
        final_video = concatenate_videoclips(video_clips, method="compose")
        
        # Ensure it matches audio duration exactly (trim/loop last bit if needed)
        if final_video.duration > audio_duration:
            final_video = final_video.subclipped(0, audio_duration)
        elif final_video.duration < audio_duration:
            # This shouldn't happen much with our math, but just in case
            final_video = final_video.with_effects([vfx.Loop(duration=audio_duration)])

        final_clip = final_video.with_audio(audio_clip)
        
        logger.info("Rendering final video → %s", output_path.name)
        final_clip.write_videofile(
            str(output_path),
            fps=VIDEO_FPS,
            codec="libx264",
            audio_codec="aac",
            preset="medium",
            threads=4,
            logger=None,
        )

        final_path = str(output_path.resolve())
        # Close explicitly before returning
        final_clip.close()
        final_video.close()

        return final_path

    except Exception as exc:
        logger.error("Video rendering failed: %s", exc)
        raise
    finally:
        if audio_clip:
            try:
                audio_clip.close()
            except Exception:
                pass
        for clip in clips_to_close:
            try:
                clip.close()
            except Exception:
                pass
            
    return ""  # Should not be reached due to raise in except


def _prepare_clip(path: str | Path, target_duration: float, random_start: bool = False) -> VideoFileClip:
    """Load, resize, and loop/trim a clip to match target duration."""
    clip = VideoFileClip(str(path))
    
    # 1. Pick a random start if requested and video is long enough
    start_time = 0
    if random_start and clip.duration > target_duration:
        start_time = random.uniform(0, clip.duration - target_duration)

    # 2. Loop if shorter than target
    if clip.duration < target_duration:
        clip = clip.with_effects([vfx.Loop(duration=target_duration)])
    
    # 3. Trim to target
    clip = clip.subclipped(start_time, start_time + target_duration)
    
    # 3. Resize and crop (Cover strategy: ensure 1080x1920 is fully filled)
    w, h = clip.w, clip.h
    target_ratio = VIDEO_WIDTH / VIDEO_HEIGHT
    current_ratio = w / h

    if current_ratio > target_ratio:
        # Video is wider than target: scale based on height
        clip = clip.resized(height=VIDEO_HEIGHT)
    else:
        # Video is taller than target: scale based on width
        clip = clip.resized(width=VIDEO_WIDTH)

    # Recalculate dimensions after resize
    w, h = clip.w, clip.h

    # Center crop to exactly 1080x1920
    x_center = w / 2
    y_center = h / 2

    clip = clip.cropped(
        x1=x_center - VIDEO_WIDTH/2,
        y1=y_center - VIDEO_HEIGHT/2,
        x2=x_center + VIDEO_WIDTH/2,
        y2=y_center + VIDEO_HEIGHT/2
    )
    
    return clip
