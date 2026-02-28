import asyncio
import sys
import argparse
from pathlib import Path
import edge_tts

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True)
    parser.add_argument("--voice", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    # On Windows, use ProactorEventLoop for subprocesses
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    communicate = edge_tts.Communicate(args.text, args.voice)
    await communicate.save(args.output)

if __name__ == "__main__":
    asyncio.run(main())
