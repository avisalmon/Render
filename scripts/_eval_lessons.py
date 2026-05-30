import json
from pathlib import Path

base = Path("data/course_materials/micropython-thonny")

for i in range(1, 16):
    d = json.loads((base / f"lesson_{i:02d}.json").read_text(encoding="utf-8"))
    a = d.get("analysis") or {}
    t = d.get("transcript_he", "")
    code = d.get("github_code", "") or ""
    title_en = a.get("title_en", "?")
    print(f"--- L{i:02d} [{title_en}] ---")
    print(f"  transcript : {len(t)} chars")
    print(f"  code       : {len(code)} chars | {d.get('github_file','none')}")
    print(f"  objectives : {len(a.get('objectives',[]))}")
    print(f"  notes_md   : {len(a.get('notes_markdown',''))} chars")
    print(f"  summary_he : {len(a.get('summary_he',''))} chars")
    print()
