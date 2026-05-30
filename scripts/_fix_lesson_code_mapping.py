"""
One-time script to fix lesson code mappings:
- L06: copy code from L05 (both use 020 move the line.py)
- L14: clear wrong code (lesson is about Python functions in Jupyter, not ESP32)
- L15: move 110 pong part 3 colision.py from L14 to L15
"""
import json
from pathlib import Path

base = Path("data/course_materials/micropython-thonny")

def load(n):
    return json.loads((base / f"lesson_{n:02d}.json").read_text(encoding="utf-8"))

def save(n, data):
    (base / f"lesson_{n:02d}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

# --- Fix L06: same code file as L05 ---
l05 = load(5)
l06 = load(6)
l06["github_file"] = l05["github_file"]
l06["github_code"] = l05["github_code"]
save(6, l06)
print(f"L06: set github_file = {l06['github_file']}")

# --- Fix L14/L15 swap ---
# L14 (youtube: "110 functions") teaches Python functions in Jupyter — no ESP32 code
# L15 (youtube: "111 pong colision") IS the pong collision demo — should have 110 pong part 3 colision.py
import urllib.request
from urllib.parse import quote

l14 = load(14)
l15 = load(15)

COLLISION_FILE = "110 pong part 3 colision.py"
GITHUB_RAW = "https://raw.githubusercontent.com/avisalmon/single_button/main/{}"

# Fetch collision code if L15 doesn't have it
if not l15.get("github_file"):
    try:
        import requests as _req
        url = GITHUB_RAW.format(quote(COLLISION_FILE))
        proxies = {"http": "http://proxy-iil.intel.com:912", "https": "http://proxy-iil.intel.com:912"}
        r = _req.get(url, proxies=proxies, timeout=15)
        if r.status_code == 200:
            l15["github_file"] = COLLISION_FILE
            l15["github_code"] = r.text
        else:
            print(f"  WARNING: could not fetch {COLLISION_FILE} (HTTP {r.status_code})")
    except Exception as e:
        print(f"  WARNING: fetch failed: {e}")

# L14 has no ESP32 code — clear it
l14["github_file"] = None
l14["github_code"] = None

save(14, l14)
save(15, l15)
print(f"L14: cleared code (Python functions tutorial, Jupyter only)")
print(f"L15: set github_file = {l15['github_file']}")

print("\nDone.")
