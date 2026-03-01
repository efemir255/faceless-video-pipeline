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
    final_video = None
    final_clip = None
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
        # method="chain" is faster and more stable for identical-size clips
        final_video = concatenate_videoclips(video_clips, method="chain")
        
        # Ensure it matches audio duration exactly (trim/loop last bit if needed)
        if final_video.duration > audio_duration:
            final_video = final_video.subclipped(0, audio_duration)
        elif final_video.duration < audio_duration:
            # This shouldn't happen much with our math, but just in case
            final_video = final_video.with_effects([vfx.Loop(duration=audio_duration)])

        final_clip = final_video.with_audio(audio_clip)
        
        logger.info("Rendering final video → %s", output_path.name)

        # Write to a temp file first, then atomically move into place. This
        # avoids producing a truncated/uncorrupted final file if the write
        # is interrupted. Also request the moov atom to be moved to the
        # start of the file (faststart) for better streaming compatibility.
        temp_path = output_path.with_suffix(".part.mp4")

        # Pass ffmpeg params to ensure faststart
        ffmpeg_params = ["-movflags", "+faststart"]

        final_clip.write_videofile(
            str(temp_path),
            fps=VIDEO_FPS,
            codec="libx264",
            audio_codec="aac",
            preset="ultrafast",
            threads=4,
            ffmpeg_params=ffmpeg_params,
            logger=None,
        )

        # Post-write verification: use ffmpeg (bundled via imageio-ffmpeg)
        # if available to validate the container. If validation fails,
        # attempt a remux to recover the container; if that fails, raise
        # an exception so the caller can retry or re-render.
        try:
            import imageio_ffmpeg as iioff
            ffmpeg_exe = iioff.get_ffmpeg_exe()
        except Exception:
            ffmpeg_exe = None

        def _verify(path):
            if ffmpeg_exe:
                import subprocess
                res = subprocess.run([ffmpeg_exe, "-v", "error", "-i", str(path), "-f", "null", "-"], capture_output=True, text=True)
                return res.returncode == 0 and not res.stderr
            else:
                # Fallback: try loading with moviepy
                try:
                    from moviepy.video.io.VideoFileClip import VideoFileClip as _V
                    c = _V(str(path))
                    c.close()
                    return True
                except Exception:
                    return False

        ok = _verify(temp_path)
        if not ok and ffmpeg_exe:
            # Try remuxing to recover the moov atom
            remuxed = output_path.with_name(output_path.stem + "_remux.mp4")
            import subprocess
            try:
                subprocess.run([ffmpeg_exe, "-y", "-i", str(temp_path), "-c", "copy", "-movflags", "+faststart", str(remuxed)], check=True)
                # replace temp with remuxed final
                temp_path.unlink(missing_ok=True)
                remuxed.replace(output_path)
                logger.info("Remux recovered output to %s", output_path.name)
                return str(output_path.resolve())
            except Exception as exc:
                logger.error("Remux failed: %s", exc)
                # fall through to raising an error below

        if not ok:
            # Cleanup temp file and raise
            try:
                temp_path.unlink()
            except Exception:
                pass
            raise RuntimeError("Rendered file failed verification (corrupt or incomplete)")

        # Atomic replace
        try:
            temp_path.replace(output_path)
        except Exception:
            # Fallback to rename
            import shutil
            shutil.move(str(temp_path), str(output_path))

        return str(output_path.resolve())

    except Exception as exc:
        logger.error("Video rendering failed: %s", exc)
        raise
    finally:
        if final_clip:
            try:
                final_clip.close()
            except Exception:
                pass
        if final_video:
            try:
                final_video.close()
            except Exception:
                pass
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


def _prepare_clip(path: str | Path, target_duration: float) -> VideoFileClip:
    """Load, resize, and loop/trim a clip to match target duration."""
    # Load without audio to save RAM and avoid crash
    clip = VideoFileClip(str(path), audio=False).with_fps(VIDEO_FPS)
    
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
