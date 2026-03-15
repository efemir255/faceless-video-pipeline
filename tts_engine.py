"""
tts_engine.py — Text-to-Speech generation via subprocess isolation.
"""

import logging
import sys
import subprocess
from pathlib import Path

# Force the project root into sys.path to ensure local imports always work in the IDE
_ROOT = str(Path(__file__).resolve().parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from mutagen.mp3 import MP3 # type: ignore
from config import DEFAULT_TTS_VOICE, AUDIO_DIR # type: ignore

logger = logging.getLogger(__name__)

def _generate_sync(text: str, output_path: Path, voice: str) -> None:
    """
    Run TTS in a standalone subprocess to guarantee event loop isolation.
    Uses stdin for the text to avoid command-line length limitations.
    """
    python_exe = sys.executable
    cli_script = Path(__file__).parent / "tts_cli.py"
    
    try:
        # Run the standalone script, passing the text through stdin
        result = subprocess.run(
            [python_exe, str(cli_script), "--voice", voice, "--output", str(output_path)],
            input=text,
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        logger.error("TTS CLI failed: %s", e.stderr or e.stdout)
        raise RuntimeError(f"TTS subprocess failed: {e.stderr or e.stdout}") from e

def generate_audio(
    text: str,
    output_path: str | Path | None = None,
    voice: str = DEFAULT_TTS_VOICE,
) -> tuple[str, float, str]:
    """
    Generate TTS audio from *text* and save it as an MP3 file.
    Returns (audio_path, duration, subtitle_path).
    """
    if not text or not text.strip():
        raise ValueError("Cannot generate audio from empty text.")

    if output_path is None:
        output_path = AUDIO_DIR / "tts_output.mp3"
    output_path = Path(output_path)
    subtitle_path = output_path.with_suffix(".json")

    try:
        logger.info("Generating TTS audio (isolated process) ...")

        # Run via subprocess
        _generate_sync(text, output_path, voice)

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError("edge-tts produced an empty or missing audio file.")

        if not subtitle_path.exists():
            raise RuntimeError("edge-tts did not produce a subtitle JSON file.")

        # Read duration with mutagen
        audio_info = MP3(str(output_path))
        duration: float = audio_info.info.length  # seconds

        if duration <= 0:
            raise RuntimeError(f"Audio file has invalid duration ({duration}s).")

        logger.info("TTS audio saved -> %s  (%.1f s)", output_path.name, duration)
        return str(output_path.resolve()), duration, str(subtitle_path.resolve())

    except Exception as exc:
        logger.error("TTS generation failed: %s", exc)
        snippet = text[0:60] + "..." if len(text) > 60 else text # type: ignore
        raise RuntimeError(f"TTS generation failed: {exc}") from exc
