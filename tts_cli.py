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
    await communicate.save(args.output)

if __name__ == "__main__":
    asyncio.run(main())
