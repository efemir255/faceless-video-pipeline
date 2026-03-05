"""
video_engine.py — Merge audio + background video into a final 9:16 short.

Uses moviepy to composite the video, looping short clips to match
the audio duration, and exporting a ready-to-upload MP4.
"""

import json
import logging
import random
from pathlib import Path

from moviepy import (
    AudioFileClip,
    VideoFileClip,
    ColorClip,
    TextClip,
    ImageClip,
    CompositeVideoClip,
    concatenate_videoclips,
    vfx,
)
from PIL import Image, ImageDraw, ImageFont
import numpy as np

from config import VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS, FINAL_DIR

logger = logging.getLogger(__name__)


def render_final_video(
    audio_path: str | Path,
    video_source: str | Path | list[dict],
    timing_path: str | Path | None = None,
    screenshot_path: str | Path | None = None,
    split_screen: bool = False,
    bgm_path: str | Path | None = None,
    bgm_volume: float = 0.1,
    progress_bar: bool = False,
    cta_text: str | None = None,
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

        # ─── Split-Screen ──────────────────────────────────────────────────
        if split_screen:
            logger.info("Applying split-screen mode...")
            try:
                # Top half: original video (already 1080x1920)
                # We crop the middle portion (1080x960) to fill the top half
                top_half = final_video.cropped(y1=VIDEO_HEIGHT//4, y2=3*VIDEO_HEIGHT//4)
                top_half = top_half.with_position(("center", "top"))

                # Bottom half: use a default satisfying video
                from config import BUILTIN_VIDEO_DIR
                satisfying_videos = list(BUILTIN_VIDEO_DIR.glob("*.mp4"))
                if satisfying_videos:
                    bottom_path = satisfying_videos[0]
                    bottom_clip_full = _prepare_clip(bottom_path, audio_duration)
                    clips_to_close.append(bottom_clip_full)

                    bottom_half = bottom_clip_full.cropped(y1=VIDEO_HEIGHT//4, y2=3*VIDEO_HEIGHT//4)
                    bottom_half = bottom_half.with_position(("center", "bottom"))

                    final_video = CompositeVideoClip([top_half, bottom_half], size=(VIDEO_WIDTH, VIDEO_HEIGHT))
                    clips_to_close.append(final_video)
            except Exception as e:
                logger.warning("Failed to apply split-screen: %s", e)
        
        # Ensure it matches audio duration exactly (trim/loop last bit if needed)
        if final_video.duration > audio_duration:
            final_video = final_video.subclipped(0, audio_duration)
        elif final_video.duration < audio_duration:
            # This shouldn't happen much with our math, but just in case
            final_video = final_video.with_effects([vfx.Loop(duration=audio_duration)])

        # ─── Dynamic Subtitles ─────────────────────────────────────────────
        final_composite = [final_video]

        # ─── Progress Bar ──────────────────────────────────────────────────
        if progress_bar:
            logger.info("Adding progress bar...")
            try:
                # Progress bar height
                bar_h = 10

                # Function to create the bar at time t
                def make_bar(t):
                    progress = t / audio_duration
                    w = int(VIDEO_WIDTH * progress)
                    # Constant width image to satisfy FFMPEG requirements
                    img = Image.new("RGBA", (VIDEO_WIDTH, bar_h), (0, 0, 0, 0))
                    if w > 0:
                        draw = ImageDraw.Draw(img)
                        draw.rectangle([0, 0, w, bar_h], fill=(255, 0, 0, 255))
                    return np.array(img)

                from moviepy import VideoClip
                bar_clip = VideoClip(make_bar, duration=audio_duration)
                bar_clip = bar_clip.with_position(("left", "bottom"))
                final_composite.append(bar_clip)
                clips_to_close.append(bar_clip)
            except Exception as e:
                logger.warning("Failed to add progress bar: %s", e)

        # ─── Screenshot Overlay ─────────────────────────────────────────────
        if screenshot_path and Path(screenshot_path).exists():
            logger.info("Adding screenshot overlay...")
            try:
                ss_clip = ImageClip(str(screenshot_path)).with_duration(min(5, audio_duration))

                # Resize to fit width with padding
                target_w = VIDEO_WIDTH * 0.9
                ss_clip = ss_clip.resized(width=target_w)

                # Center it
                ss_clip = ss_clip.with_position(("center", "center"))

                final_composite.append(ss_clip)
            except Exception as e:
                logger.warning("Failed to add screenshot: %s", e)

        # ─── CTA Overlay ───────────────────────────────────────────────────
        if cta_text:
            logger.info("Adding CTA overlay: %s", cta_text)
            try:
                cta_duration = min(3, audio_duration)
                cta_start = max(0, audio_duration - cta_duration)

                # Using Pillow fallback as it's safer
                cta_clip = _create_text_clip_pillow(
                    cta_text.upper(),
                    font_size=80,
                    color="white",
                    stroke_color="red",
                    stroke_width=3
                ).with_start(cta_start).with_duration(cta_duration).with_position(("center", VIDEO_HEIGHT * 0.2))

                final_composite.append(cta_clip)
            except Exception as e:
                logger.warning("Failed to add CTA: %s", e)

        if timing_path and Path(timing_path).exists():
            logger.info("Adding dynamic subtitles...")
            try:
                with open(timing_path, "r", encoding="utf-8") as f:
                    words_metadata = json.load(f)

                subtitle_clips = _create_dynamic_subtitles(words_metadata)
                final_composite.extend(subtitle_clips)
            except Exception as e:
                logger.warning("Failed to add subtitles: %s", e)

        final_video = CompositeVideoClip(final_composite)

        # ─── Audio Mixing (Speech + BGM) ───────────────────────────────────
        final_audio = audio_clip
        if bgm_path and Path(bgm_path).exists():
            logger.info("Adding BGM: %s (vol=%s)", Path(bgm_path).name, bgm_volume)
            try:
                bgm_clip = AudioFileClip(str(bgm_path))
                # Loop BGM to match audio duration
                if bgm_clip.duration < audio_duration:
                    bgm_clip = bgm_clip.with_effects([vfx.Loop(duration=audio_duration)])
                else:
                    bgm_clip = bgm_clip.subclipped(0, audio_duration)

                # Adjust volume
                bgm_clip = bgm_clip.with_volume_scaled(bgm_volume)

                # Combine
                from moviepy import CompositeAudioClip
                final_audio = CompositeAudioClip([audio_clip, bgm_clip])
                clips_to_close.append(bgm_clip)
            except Exception as e:
                logger.warning("Failed to add BGM: %s", e)

        final_clip = final_video.with_audio(final_audio)
        
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


def _create_dynamic_subtitles(words: list[dict]) -> list[TextClip]:
    """Create a list of TextClips for each word with highlighting."""
    clips = []

    # Configuration for text
    font_size = 70
    color = "white"
    stroke_color = "black"
    stroke_width = 2

    for item in words:
        word = item["word"]
        start = item["start"]
        end = item["end"]
        duration = end - start

        if duration <= 0:
            continue

        # Create a single word clip
        try:
            # We use a yellow highlight for every word when it's spoken
            # In a more advanced version, we could show the whole sentence
            # and only highlight the active word.
            txt_clip = TextClip(
                text=word.upper(),
                font_size=font_size,
                color="yellow",
                stroke_color=stroke_color,
                stroke_width=stroke_width,
                method="caption",
                size=(VIDEO_WIDTH * 0.8, None)
            ).with_start(start).with_duration(duration).with_position(("center", VIDEO_HEIGHT * 0.75))

            clips.append(txt_clip)
        except Exception as e:
            # Fallback for when ImageMagick/TextClip is not working
            logger.debug("TextClip failed, using Pillow fallback for word '%s': %s", word, e)
            try:
                txt_clip = _create_text_clip_pillow(
                    word.upper(),
                    font_size=font_size,
                    color="yellow",
                    stroke_color=stroke_color,
                    stroke_width=stroke_width
                ).with_start(start).with_duration(duration).with_position(("center", VIDEO_HEIGHT * 0.75))
                clips.append(txt_clip)
            except Exception as e2:
                logger.error("Pillow fallback also failed for word '%s': %s", word, e2)
                continue

    return clips


def _create_text_clip_pillow(text, font_size=70, color="yellow", stroke_color="black", stroke_width=2):
    """Fallback text clip creator using Pillow instead of ImageMagick."""
    # Try to find a font
    font = None
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "Arial Bold.ttf",
        "arialbd.ttf"
    ]
    for path in font_paths:
        try:
            font = ImageFont.truetype(path, font_size)
            break
        except Exception:
            continue

    if font is None:
        font = ImageFont.load_default()

    # Implement text wrapping
    max_w = int(VIDEO_WIDTH * 0.8)
    words = text.split()
    lines = []
    current_line = []

    dummy_img = Image.new("RGBA", (VIDEO_WIDTH, font_size * 2))
    draw = ImageDraw.Draw(dummy_img)

    for word in words:
        test_line = " ".join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font, stroke_width=stroke_width)
        w = bbox[2] - bbox[0]
        if w < max_w:
            current_line.append(word)
        else:
            lines.append(" ".join(current_line))
            current_line = [word]
    lines.append(" ".join(current_line))

    wrapped_text = "\n".join(lines)

    # Determine final image size
    bbox = draw.multiline_textbbox((0, 0), wrapped_text, font=font, stroke_width=stroke_width, align="center")
    final_w = int(bbox[2] - bbox[0] + 40)
    final_h = int(bbox[3] - bbox[1] + 40)

    # Create the actual image
    img = Image.new("RGBA", (final_w, final_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw text with stroke centered
    draw.multiline_text(
        (final_w // 2, final_h // 2),
        wrapped_text,
        font=font,
        fill=color,
        stroke_width=stroke_width,
        stroke_fill=stroke_color,
        anchor="mm",
        align="center"
    )

    # Convert to moviepy clip
    return ImageClip(np.array(img))
