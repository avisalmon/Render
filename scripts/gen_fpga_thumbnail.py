"""
Generate the course thumbnail for fpga-processor-vga using OpenAI gpt-image-1
(direct API, no proxy). Output: static/course_thumbnails/fpga-processor-vga.png

Run:  ./env/Scripts/python.exe scripts/gen_fpga_thumbnail.py
"""
import base64
import os
import sys
from pathlib import Path

import django

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()
from django.conf import settings  # noqa: E402
from openai import OpenAI  # noqa: E402

SLUG = "fpga-processor-vga"
PROMPT = """
Professional tech course thumbnail, wide 16:9 landscape, no text anywhere.

- Deep near-black background (#0f1117), dark charcoal tones.
- Center-left: a realistic FPGA development board (Altera/Intel MAX10 DE10-Lite
  style) with a large square FPGA chip, rows of small LEDs and slide switches,
  and a green PCB. A subtle blue-purple gradient glow behind it like a halo.
- Right side: a clean monospace Verilog code snippet floating on the dark
  background (no box), styled like VS Code — keywords blue (#3b82f6), strings
  amber (#f59e0b), comments gray — showing lines like
  'module cpu(input clk, ...);' and 'always @(posedge clk)'.
- Background hint: a faint retro VGA arcade screen with simple pixel-art
  (a small paddle/ball and a tiny ghost sprite), glowing softly, far right.
- Overall aesthetic: dark developer tool, clean, professional, like a
  Frontend Masters / Egghead.io thumbnail. Hardware + code only, no people,
  no hands, no text.
"""


def main():
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    print("Generating thumbnail with gpt-image-1 (may take 30-60s)…")
    r = client.images.generate(
        model="gpt-image-1", prompt=PROMPT.strip(),
        size="1536x1024", quality="high", n=1,
    )
    img = base64.b64decode(r.data[0].b64_json)
    out_dir = Path(settings.BASE_DIR) / "static" / "course_thumbnails"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{SLUG}.png"
    out.write_bytes(img)
    print(f"Saved: {out} ({len(img)//1024} KB)")


if __name__ == "__main__":
    main()
