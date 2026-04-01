import asyncio
import sys
import argparse
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

    communicate = edge_tts.Communicate(text, args.voice)

    # Track word boundaries for dynamic subtitles
    words = []

    # Save audio while streaming
    with open(args.output, "wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                # chunk['offset'] is in 100ns units, chunk['duration'] is in 100ns units
                # We want seconds
                words.append({
                    "word": chunk["text"],
                    "start": chunk["offset"] / 10_000_000,
                    "end": (chunk["offset"] + chunk["duration"]) / 10_000_000
                })

    # Save word timings to a JSON file next to the audio
    import json
    timing_path = Path(args.output).with_suffix(".json")
    with open(timing_path, "w", encoding="utf-8") as f:
        json.dump(words, f, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
