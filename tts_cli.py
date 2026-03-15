import asyncio
import sys
import argparse
import json
from pathlib import Path
import edge_tts

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=False)
    parser.add_argument("--voice", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    # On Windows, use ProactorEventLoop for subprocesses
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    text = args.text
    if not text:
        # Read from stdin if --text is not provided
        text = sys.stdin.read().strip()

    if not text:
        print("Error: No text provided via --text or stdin.")
        sys.exit(1)

    output_path = Path(args.output)
    timing_path = output_path.with_suffix(".json")

    # BUG FIX: Edge-TTS might not send WordBoundary events if we don't
    # use SubMaker or explicitly request them. Actually, Communicate
    # should send them in stream(). Let's try to wrap it in a way that
    # definitely gets them.
    communicate = edge_tts.Communicate(text, args.voice)

    # Capture events for subtitles
    # Fallback timing if WordBoundary events are missing
    audio_data = bytearray()
    word_boundaries = []

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data.extend(chunk["data"])
        elif chunk["type"] == "WordBoundary":
            word_boundaries.append({
                "start": chunk["offset"] / 10_000_000, # Convert to seconds
                "duration": chunk["duration"] / 10_000_000,
                "text": chunk["text"]
            })

    with open(output_path, "wb") as f:
        f.write(audio_data)

    # BUG FIX: If no WordBoundary events were received (often the case with certain
    # environments/versions), generate proportional fallback timings.
    if not word_boundaries:
        # We'll use a simple heuristic: split text into words and
        # distribute the total duration proportionally to word length.
        # First, we need the total duration.
        from mutagen.mp3 import MP3
        audio_info = MP3(output_path)
        total_duration = audio_info.info.length

        words = text.split()
        total_chars = sum(len(w) for w in words)

        current_time = 0.0
        for w in words:
            # Proportional duration
            w_dur = (len(w) / total_chars) * total_duration if total_chars > 0 else 0
            word_boundaries.append({
                "start": current_time,
                "duration": w_dur,
                "text": w
            })
            current_time += w_dur

    # Save timing data to JSON
    with open(timing_path, "w", encoding="utf-8") as f:
        json.dump(word_boundaries, f, indent=2)

    print(f"Subtitles saved to {timing_path}")

if __name__ == "__main__":
    asyncio.run(main())
