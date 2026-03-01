"""
video_engine.py — Merge audio + background video + subtitles into a final 9:16 short.

Uses moviepy to composite the video, looping short clips to match
the audio duration, and overlaying word-level subtitles.
"""

import logging
import json
from pathlib import Path

from moviepy import (
    AudioFileClip,
    VideoFileClip,
    TextClip,
    CompositeVideoClip,
    concatenate_videoclips,
    vfx,
)

from config import VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS, FINAL_DIR

logger = logging.getLogger(__name__)


def render_final_video(
    audio_path: str | Path,
    video_source: str | Path | list[dict],
    subtitle_path: str | Path | None = None,
    output_path: str | Path | None = None,
) -> str:
    """
    Composite *audio_path* over *video_source* into a final 1080x1920 MP4.
    If *subtitle_path* is provided, overlays word-level subtitles.
    """
    audio_path = Path(audio_path)
    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    if output_path is None:
        import time
        timestamp = int(time.time())
        output_path = FINAL_DIR / f"final_video_{timestamp}.mp4"
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
                clip = _prepare_clip(item["path"], item["duration"])
                video_clips.append(clip)
        
        clips_to_close.extend(video_clips)

        # Stitch clips together
        logger.info("Stitching %d clips...", len(video_clips))
        background_video = concatenate_videoclips(video_clips, method="compose")
        
        # Ensure it matches audio duration exactly
        if background_video.duration > audio_duration:
            background_video = background_video.subclipped(0, audio_duration)
        elif background_video.duration < audio_duration:
            background_video = background_video.with_effects([vfx.Loop(duration=audio_duration)])

        # Subtitles
        final_video = background_video
        if subtitle_path and Path(subtitle_path).exists():
            logger.info("Rendering subtitles from %s", Path(subtitle_path).name)
            subtitle_clips = _generate_subtitle_clips(subtitle_path)
            if subtitle_clips:
                final_video = CompositeVideoClip([background_video] + subtitle_clips)
                clips_to_close.append(final_video)

        final_clip = final_video.with_audio(audio_clip)
        
        logger.info("Rendering final video → %s", output_path.name)
        final_clip.write_videofile(
            str(output_path),
            fps=VIDEO_FPS,
            codec="libx264",
            audio_codec="aac",
            preset="ultrafast",  # Faster rendering
            threads=4,
            logger=None,
        )

        # Cleanup old videos (keep only 3)
        _cleanup_old_videos(FINAL_DIR)

        final_path = str(output_path.resolve())
        # Close explicitly before returning
        final_clip.close()
        if final_video != background_video:
             final_video.close()
        background_video.close()

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
            
    return ""


def _prepare_clip(path: str | Path, target_duration: float) -> VideoFileClip:
    """Load, resize, and loop/trim a clip to match target duration."""
    clip = VideoFileClip(str(path))
    
    # 1. Loop if shorter than target
    if clip.duration < target_duration:
        clip = clip.with_effects([vfx.Loop(duration=target_duration)])
    
    # 2. Trim to target
    clip = clip.subclipped(0, target_duration)
    
    # 3. Resize and crop (Cover strategy: ensure 1080x1920 is fully filled)
    w, h = clip.w, clip.h
    target_ratio = VIDEO_WIDTH / VIDEO_HEIGHT
    current_ratio = w / h

    if current_ratio > target_ratio:
        clip = clip.resized(height=VIDEO_HEIGHT)
    else:
        clip = clip.resized(width=VIDEO_WIDTH)

    w, h = clip.w, clip.h
    x_center = w / 2
    y_center = h / 2

    clip = clip.cropped(
        x1=x_center - VIDEO_WIDTH/2,
        y1=y_center - VIDEO_HEIGHT/2,
        x2=x_center + VIDEO_WIDTH/2,
        y2=y_center + VIDEO_HEIGHT/2
    )
    
    return clip


def _generate_subtitle_clips(subtitle_path: str | Path) -> list[TextClip]:
    """Create a list of TextClip objects for each word."""
    with open(subtitle_path, "r", encoding="utf-8") as f:
        subs = json.load(f)

    clips = []
    # Use a common font that's likely present
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    if not Path(font_path).exists():
        font_path = "Arial" # Fallback

    for item in subs:
        word = item["text"].upper()
        start = item["start"]
        duration = item["duration"]

        if duration <= 0:
            duration = 0.1

        try:
            txt_clip = (
                TextClip(
                    text=word,
                    font=font_path,
                    font_size=90,
                    color="yellow",
                    stroke_color="black",
                    stroke_width=2,
                    method="label",
                )
                .with_start(start)
                .with_duration(duration)
                .with_position(("center", 1400)) # Position in lower third
            )
            clips.append(txt_clip)
        except Exception as e:
            logger.warning("Could not create TextClip for word '%s': %s", word, e)

    return clips


def _cleanup_old_videos(directory: Path, keep: int = 3):
    """Keep only the most recent N videos in the final directory."""
    files = sorted(directory.glob("final_video_*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True)
    for old_file in files[keep:]:
        try:
            old_file.unlink()
        except Exception:
            pass
