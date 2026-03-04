
from PIL import Image, ImageDraw, ImageFont
import numpy as np

VIDEO_WIDTH = 1080

def test_wrapping():
    text = "THIS IS A VERY LONG SENTENCE THAT SHOULD BE WRAPPED INTO MULTIPLE LINES BY THE PILLOW RENDERING LOGIC TO ENSURE READABILITY"
    font_size = 70
    stroke_width = 2

    # Try to find a font
    font = None
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for path in font_paths:
        try:
            font = ImageFont.truetype(path, font_size)
            break
        except Exception:
            continue

    if font is None:
        font = ImageFont.load_default()

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
    print("Wrapped text:")
    print(wrapped_text)

    bbox = draw.multiline_textbbox((0, 0), wrapped_text, font=font, stroke_width=stroke_width, align="center")
    print(f"BBox: {bbox}")

if __name__ == "__main__":
    test_wrapping()
