
import logging
import sys
from pathlib import Path
from reddit_fetcher import capture_post_screenshot

logging.basicConfig(level=logging.INFO)

def test_screenshot():
    output = Path("test_screenshot.png")
    if output.exists():
        output.unlink()

    # Using a simple URL to test playwright functionality
    url = "https://example.com"
    try:
        path = capture_post_screenshot(url, output)
        print(f"Screenshot saved to {path}")
        if output.exists():
            print("Success: File exists")
        else:
            print("Failure: File does not exist")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_screenshot()
