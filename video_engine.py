"""
video_engine.py — Merge audio + background video into a final 9:16 short.

Uses moviepy to composite the video, looping short clips to match
the audio duration, and exporting a ready-to-upload MP4.
"""

import logging
import json
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from moviepy import (
    AudioFileClip,
    VideoFileClip,
    TextClip,
    ImageClip,
    CompositeVideoClip,
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
    """
    audio_path = Path(audio_path)
    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    subtitles_path = audio_path.with_suffix(".json")

    if output_path is None:
        import time
        output_path = FINAL_DIR / f"final_video_{int(time.time())}.mp4"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    audio_clip = None
    final_clip = None
    final_video = None
    clips_to_close = []

    try:
        logger.info("Loading audio: %s", audio_path.name)
        audio_clip = AudioFileClip(str(audio_path))
        audio_duration = audio_clip.duration

        if isinstance(video_source, (str, Path)):
            video_clips = [_prepare_clip(video_source, audio_duration)]
        else:
            video_clips = []
            for item in video_source:
                clip = _prepare_clip(item["path"], item["duration"])
                video_clips.append(clip)
        
        clips_to_close.extend(video_clips)

        logger.info("Stitching %d clips...", len(video_clips))
        final_video = concatenate_videoclips(video_clips, method="compose")
        
        if final_video.duration > audio_duration:
            final_video = final_video.subclipped(0, audio_duration)
        elif final_video.duration < audio_duration:
            final_video = final_video.with_effects([vfx.Loop(duration=audio_duration)])

        final_clip = final_video.with_audio(audio_clip)

        # ── Add Subtitles ─────────────────────────────────────────────────
        if subtitles_path.exists():
            logger.info("Adding subtitles from %s", subtitles_path.name)
            subtitle_clips = _generate_subtitle_clips(subtitles_path)
            if subtitle_clips:
                final_clip = CompositeVideoClip([final_clip] + subtitle_clips)
                clips_to_close.extend(subtitle_clips)
        
        logger.info("Rendering final video → %s", output_path.name)

        # GPU acceleration attempt (RTX 2060 is GPU 1)
        # Fallback to CPU if NVENC fails
        try:
            logger.info("Attempting GPU accelerated rendering (NVENC)...")
            # We must use 'codec' instead of h264_nvenc directly if we want to pass ffmpeg_params correctly
            # Actually moviepy expects the encoder name in 'codec'
            final_clip.write_videofile(
                str(output_path),
                fps=VIDEO_FPS,
                codec="h264_nvenc",
                audio_codec="aac",
                threads=4,
                ffmpeg_params=["-gpu", "1", "-preset", "p4", "-tune", "hq"],
                logger=None,
            )
        except Exception as e:
            logger.warning("GPU rendering failed: %s. Falling back to CPU.", e)
            # Ensure the output file is not partially written
            if output_path.exists():
                try:
                    output_path.unlink()
                except Exception:
                    pass
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
        return final_path

    except Exception as exc:
        logger.error("Video rendering failed: %s", exc)
        raise
    finally:
        if final_clip:
            final_clip.close()
        if final_video:
            final_video.close()
        if audio_clip:
            audio_clip.close()
        for clip in clips_to_close:
            try:
                clip.close()
            except Exception:
                pass


def _prepare_clip(path: str | Path, target_duration: float) -> VideoFileClip:
    """Load, resize, and loop/trim a clip to match target duration."""
    clip = VideoFileClip(str(path), audio=False)
    
    if clip.duration < target_duration:
        clip = clip.with_effects([vfx.Loop(duration=target_duration)])
    
    clip = clip.subclipped(0, target_duration)
    
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


def _generate_subtitle_clips(subtitles_path: Path) -> list:
    """Parse timing JSON and create Pillow-based subtitle overlays."""
    try:
        with open(subtitles_path, "r", encoding="utf-8") as f:
            word_data = json.load(f)
    except Exception as e:
        logger.error("Failed to load subtitles JSON: %s", e)
        return []

    # Common font paths
    font_paths = [
        "C:\\Windows\\Fonts\\arialbd.ttf",  # Windows
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", # Linux
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf", # macOS
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

    subtitle_clips = []

    # We group words into short phrases or show one by one for high impact
    for item in word_data:
        start = item["start"]
        duration = item["duration"]
        text = item["text"].upper()

        if duration <= 0:
            continue

        # Create transparent canvas for the text
        # Width: 80% of video width, Height: enough for 2 lines
        canvas_w = int(VIDEO_WIDTH * 0.9)
        canvas_h = 300
        img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Get text size and wrap if needed
        def get_text_dims(t, f):
            try:
                bbox = draw.textbbox((0, 0), t, font=f)
                return bbox[2] - bbox[0], bbox[3] - bbox[1]
            except AttributeError:
                return draw.textsize(t, font=f)

        tw, th = get_text_dims(text, font)

        # Center position on canvas
        x = (canvas_w - tw) // 2
        y = (canvas_h - th) // 2

        # Draw stroke (outline)
        stroke_width = 4
        for ox in range(-stroke_width, stroke_width + 1):
            for oy in range(-stroke_width, stroke_width + 1):
                if ox == 0 and oy == 0: continue
                draw.text((x + ox, y + oy), text, font=font, fill="black")

        # Draw main text
        draw.text((x, y), text, font=font, fill="yellow")

        # Convert to MoviePy ImageClip
        img_array = np.array(img)
        txt_clip = ImageClip(img_array).with_start(start).with_duration(duration).with_position(("center", int(VIDEO_HEIGHT * 0.7)))

        subtitle_clips.append(txt_clip)

    return subtitle_clips
