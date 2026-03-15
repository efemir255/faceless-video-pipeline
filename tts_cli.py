import asyncio
import sys
import argparse
import json
import re
from pathlib import Path
import edge_tts

def split_text_to_words(text):
    """Split text into words while keeping punctuation with the preceding word."""
    return re.findall(r'\S+', text)

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
    json_path = output_path.with_suffix(".json")

    communicate = edge_tts.Communicate(text, args.voice)

    subs = []
    sentence_boundaries = []

    with open(output_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                subs.append({
                    "text": chunk["text"],
                    "start": chunk["offset"] / 10_000_000.0,
                    "duration": chunk["duration"] / 10_000_000.0
                })
            elif chunk["type"] == "SentenceBoundary":
                sentence_boundaries.append({
                    "text": chunk["text"],
                    "start": chunk["offset"] / 10_000_000.0,
                    "duration": chunk["duration"] / 10_000_000.0
                })

    # Fallback: if WordBoundary is missing but we have SentenceBoundary
    if not subs and sentence_boundaries:
        for sb in sentence_boundaries:
            words = split_text_to_words(sb["text"])
            if words:
                avg_duration = sb["duration"] / len(words)
                for i, word in enumerate(words):
                    subs.append({
                        "text": word,
                        "start": sb["start"] + (i * avg_duration),
                        "duration": avg_duration
                    })

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(subs, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    asyncio.run(main())
