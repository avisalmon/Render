"""
Generate course thumbnail for micropython-thonny using Azure gpt-image-2.
Output: static/course_thumbnails/micropython-thonny.png
"""
import os, base64, requests
from pathlib import Path

# --- load key ---
env = {}
for line in open(os.path.expanduser("~/.copilot/.env")):
    line = line.strip()
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k] = v.strip()
key = env["AZURE_API_KEY"]

URL = (
    "https://oai-modelon-eastus2.cognitiveservices.azure.com"
    "/openai/deployments/gpt-image-2/images/generations"
    "?api-version=2024-02-01"
)
HEADERS = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
PROXIES = {"https": "http://proxy-iil.intel.com:912"}

PROMPT = """
Professional tech course thumbnail. Wide landscape format, 16:9 ratio.

Visual composition:
- Deep near-black background (#0f1117), very dark charcoal tones
- Left side: a small green ESP32 microcontroller development board, 
  with colorful wires connecting to a small rectangular OLED display. 
  The OLED shows a tiny pixel-art arcade game in progress (simple paddle and ball).
- Right side: clean monospace code snippet floating in mid-air:
    from machine import Pin, I2C
    import ssd1306
    display.fill(0)
    display.show()
  Code is styled like VS Code — keywords in blue (#3b82f6), strings in amber 
  (#f59e0b), comments in gray (#9ca3af), white text — no background box, 
  just the glowing code on the dark background.
- Subtle blue-purple gradient glow behind the ESP32 board, like a halo.
- MicroPython snake logo (Python snake, small, green) in top-left corner.
- No people, no hands. Hardware + code only.
- Overall aesthetic: dark developer tool, clean, professional. 
  Like a Frontend Masters or Egghead.io course thumbnail.
- No text overlaid — image is purely visual.
"""

body = {
    "prompt": PROMPT.strip(),
    "n": 1,
    "size": "1792x1024",
    "quality": "high",
    "output_format": "png",
}

print("Generating thumbnail (may take 30-60s)...")
r = requests.post(URL, headers=HEADERS, json=body, proxies=PROXIES, timeout=180)

if r.status_code != 200:
    print(f"Error {r.status_code}: {r.text[:500]}")
    raise SystemExit(1)

img_bytes = base64.b64decode(r.json()["data"][0]["b64_json"])

out_dir = Path("static/course_thumbnails")
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / "micropython-thonny.png"
out_path.write_bytes(img_bytes)
print(f"Saved: {out_path} ({len(img_bytes)//1024} KB)")
