"""
video_engine.py — Merge audio + background video into a final 9:16 short.

Uses moviepy to composite the video, looping short clips to match
the audio duration, and exporting a ready-to-upload MP4.
"""

import logging
from pathlib import Path

from moviepy import (
    AudioFileClip,
    VideoFileClip,
    concatenate_videoclips,
    vfx,
)

from config import VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS, FINAL_DIR

logger = logging.getLogger(__name__)


import json
import time
from moviepy import TextClip, ColorClip, CompositeVideoClip

def render_final_video(
    audio_path: str | Path,
    video_source: str | Path | list[dict],
    output_path: str | Path | None = None,
    subtitles_path: str | Path | None = None,
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
        # method="chain" is much faster than "compose" if all clips are the same size
        final_video = concatenate_videoclips(video_clips, method="chain")
        
        # Ensure it matches audio duration exactly (trim/loop last bit if needed)
        if final_video.duration > audio_duration:
            final_video = final_video.subclipped(0, audio_duration)
        elif final_video.duration < audio_duration:
            # This shouldn't happen much with our math, but just in case
            final_video = final_video.with_effects([vfx.Loop(duration=audio_duration)])

        final_clip = final_video.with_audio(audio_clip)

        # ── Subtitles Overlay ─────────────────────────────────────────────
        if subtitles_path and Path(subtitles_path).exists():
            logger.info("Adding subtitles from %s", Path(subtitles_path).name)
            subtitle_clips = _generate_subtitle_clips(subtitles_path)
            if subtitle_clips:
                final_clip = CompositeVideoClip([final_clip] + subtitle_clips)
        
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

        # ── Cleanup Old Videos ────────────────────────────────────────────
        _cleanup_old_videos(FINAL_DIR, keep=3)

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


def _cleanup_old_videos(directory: Path, keep: int = 3) -> None:
    """Keep only the 'keep' most recent .mp4 files in a directory."""
    try:
        files = sorted(
            list(directory.glob("final_video_*.mp4")),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        if len(files) > keep:
            for f in files[keep:]:
                f.unlink()
                logger.debug("Deleted old video: %s", f.name)
    except Exception as e:
        logger.warning("Cleanup failed: %s", e)


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


def _generate_subtitle_clips(subtitles_path: str | Path) -> list:
    """
    Parse the timing JSON and create a list of TextClip overlays.
    Uses Pillow-based fallback if ImageMagick is not available.
    """
    try:
        with open(subtitles_path, "r", encoding="utf-8") as f:
            word_data = json.load(f)
    except Exception as e:
        logger.error("Failed to load subtitles JSON: %s", e)
        return []

    subtitle_clips = []

    # Try to see if TextClip works (needs ImageMagick)
    use_textclip = True
    try:
        # Dummy check
        tc = TextClip(text="test", font_size=20)
        tc.close()
    except Exception:
        logger.warning("TextClip (ImageMagick) not available. Subtitles will be skipped or need Pillow fallback.")
        use_textclip = False

    if not use_textclip:
        logger.info("Using Pillow fallback for subtitles...")
        return _generate_subtitle_clips_pillow(word_data)

    for item in word_data:
        start = item["start"]
        duration = item["duration"]
        text = item["text"].upper() # High-impact "Shorts" style

        if duration <= 0:
            continue

        # Create a stylized text clip
        # center of screen, slightly below middle
        txt = TextClip(
            text=text,
            font_size=80,
            color="yellow",
            stroke_color="black",
            stroke_width=2,
            method="caption", # Wraps if needed
            size=(int(VIDEO_WIDTH * 0.8), None)
        ).with_start(start).with_duration(duration).with_position(("center", int(VIDEO_HEIGHT * 0.6)))

        subtitle_clips.append(txt)

    return subtitle_clips


from PIL import Image, ImageDraw, ImageFont
from moviepy import ImageClip

def _generate_subtitle_clips_pillow(word_data: list) -> list:
    """
    Fallback for when ImageMagick is missing.
    Renders text to a transparent PNG using Pillow, then loads as ImageClip.
    """
    subtitle_clips = []

    # Try to find a font
    try:
        # Common linux paths
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
            "DejaVuSans-Bold"
        ]
        font = None
        for p in font_paths:
            try:
                font = ImageFont.truetype(p, 70)
                break
            except Exception:
                continue
        if not font:
            font = ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    for item in word_data:
        start = item["start"]
        duration = item["duration"]
        text = item["text"].upper()

        if duration <= 0:
            continue

        # Create a transparent image for the text
        # We'll make it the width of the video and enough height for the text
        img = Image.new("RGBA", (VIDEO_WIDTH, 200), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Get text size for centering
        # Use getbbox or textbbox in newer Pillow
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
        except AttributeError:
            # Fallback for old Pillow
            text_w, text_h = draw.textsize(text, font=font)

        # Draw text with outline (approximate stroke by drawing multiple times)
        x = (VIDEO_WIDTH - text_w) // 2
        y = (200 - text_h) // 2

        # Stroke
        for offset in [(-2,-2), (-2,2), (2,-2), (2,2)]:
            draw.text((x+offset[0], y+offset[1]), text, font=font, fill="black")

        # Main text
        draw.text((x, y), text, font=font, fill="yellow")

        # Convert PIL image to numpy array for MoviePy
        import numpy as np
        img_array = np.array(img)

        txt_clip = ImageClip(img_array).with_start(start).with_duration(duration).with_position(("center", int(VIDEO_HEIGHT * 0.6)))
        subtitle_clips.append(txt_clip)

    return subtitle_clips
