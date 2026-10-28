"""Sketch -> chat -> STL trial. One model per run:

    cadenv/Scripts/python.exe cad/trial.py gpt-6.1-sol

The model never writes an STL. It writes CadQuery code; this script runs it,
exports the STL, renders three views, and shows them back to the model, the
way an app would. Every call's tokens are counted.
"""

import base64
import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODEL = sys.argv[1]
OUT = HERE / "runs_scad" / MODEL
OUT.mkdir(parents=True, exist_ok=True)
PY = sys.executable

PRICES = {  # $ per 1M tokens: input, cached input, output (developers.openai.com/api/docs/pricing, 2026-10-28)
    "gpt-6.1-sol": (2.00, 0.10, 10.00), "gpt-6.1-terra": (1.00, 0.05, 5.00), "gpt-6-luna": (0.10, 0.01, 0.50),
    "gpt-5.5": (5.00, 0.50, 30.00), "gpt-5.4-mini": (0.75, 0.075, 4.50),
}


def key():
    sys.path.insert(0, r"C:\Projects\Render")
    from mysite import settings_local  # the key is read, never printed

    return getattr(settings_local, "OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")


from openai import OpenAI  # noqa: E402

client = OpenAI(api_key=key())

SYSTEM = textwrap.dedent("""
    You are a friendly CAD partner inside a website. The person shows you a hand sketch
    of a 3D part and talks with you until it is right; then they keep asking for changes.
    You build every part in OpenSCAD (version 2021.01, no external libraries). Units are millimetres.

    Always answer with JSON only, no fences:
      {"message": "what you tell the person, short and plain",
       "assumptions": ["each thing you assumed that the sketch did not say"],
       "code": "a complete OpenSCAD file that draws the whole part (all bodies), or null if you must ask first"}

    Rules: read every dimension written on the sketch. If something important is missing,
    make a sensible assumption and say so rather than stopping, unless it is impossible to guess.
    Keep the whole part in one script, parametric, with the key sizes as named variables at the top.
    Never use import(), include or use. Keep $fn reasonable (64 at most).
""").strip()

RUNNER = textwrap.dedent("""
    import sys, json
    import cadquery as cq
    ns = {}
    exec(open(sys.argv[1], encoding="utf-8").read(), ns)
    r = ns["result"]
    shape = r.val() if hasattr(r, "val") else r
    cq.exporters.export(r, sys.argv[2])
    bb = shape.BoundingBox()
    print(json.dumps({"size": [round(bb.xlen, 2), round(bb.ylen, 2), round(bb.zlen, 2)],
                      "volume": round(shape.Volume(), 1), "solids": len(r.solids().vals())}))
""")


OSCAD = r"C:/Users/avisa/AppData/Local/Temp/claude/c--Projects-Render/8fb6fe9d-2db0-4b61-9cef-9eeb01a441c5/scratchpad/openscad/openscad-2021.01/openscad.com"
PEAKS = []


def build(code, tag):
    import psutil
    import trimesh

    src = OUT / f"{tag}.scad"
    src.write_text(code, encoding="utf-8")
    stl = OUT / f"{tag}.stl"
    t = time.time()
    p = subprocess.Popen([OSCAD, "-o", str(stl), str(src)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    proc, peak = psutil.Process(p.pid), 0
    while p.poll() is None:
        try:
            peak = max(peak, proc.memory_info().rss + sum(c.memory_info().rss for c in proc.children(recursive=True)))
        except psutil.Error:
            pass
        time.sleep(0.02)
    out, err = p.communicate()
    took = time.time() - t
    PEAKS.append((tag, round(peak / 1048576), round(took, 1)))
    if p.returncode != 0 or not stl.exists() or "ERROR" in err:
        return None, err.strip()[-1500:], took
    mesh = trimesh.load(stl)
    lo, hi = mesh.bounds
    return ({"size": [round(float(x), 2) for x in (hi - lo)], "volume": round(float(mesh.volume), 1),
             "parts": len(mesh.split(only_watertight=False)), "watertight": bool(mesh.is_watertight),
             "peak_mb": round(peak / 1048576), "seconds": round(took, 1)}, stl, took)


def render(stl, tag):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import trimesh
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    mesh = trimesh.load(stl)
    fig = plt.figure(figsize=(12, 4), dpi=90)
    for i, (elev, azim, title) in enumerate([(30, -60, "iso"), (90, -90, "top"), (0, -90, "front")]):
        ax = fig.add_subplot(1, 3, i + 1, projection="3d")
        tris = mesh.vertices[mesh.faces]
        shade = 0.35 + 0.65 * abs(mesh.face_normals @ [0.3, -0.5, 0.8])
        coll = Poly3DCollection(tris, facecolors=[(0.1, 0.35 * s + 0.2, 0.75 * s + 0.2) for s in shade], edgecolor="none")
        ax.add_collection3d(coll)
        lo, hi = mesh.bounds
        c, r = (lo + hi) / 2, (hi - lo).max() / 2
        ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
        ax.view_init(elev=elev, azim=azim); ax.set_title(title); ax.set_axis_off()
    png = OUT / f"{tag}.png"
    fig.tight_layout(); fig.savefig(png); plt.close(fig)
    return png


def b64(path):
    return base64.b64encode(Path(path).read_bytes()).decode()


history = [{"role": "system", "content": SYSTEM}]
ledger = []


def ask(content, label):
    history.append({"role": "user", "content": content})
    t = time.time()
    r = client.responses.create(model=MODEL, input=history)
    took = time.time() - t
    text = r.output_text
    history.append({"role": "assistant", "content": text})
    u = r.usage
    cached = getattr(getattr(u, "input_tokens_details", None), "cached_tokens", 0) or 0
    reasoning = getattr(getattr(u, "output_tokens_details", None), "reasoning_tokens", 0) or 0
    pin, pcache, pout = PRICES[MODEL]
    cost = ((u.input_tokens - cached) * pin + cached * pcache + u.output_tokens * pout) / 1e6
    ledger.append({"step": label, "in": u.input_tokens, "cached": cached, "out": u.output_tokens,
                   "reasoning": reasoning, "seconds": round(took, 1), "usd": round(cost, 4)})
    try:
        return json.loads(text[text.index("{"): text.rindex("}") + 1])
    except ValueError:
        return {"message": text, "code": None, "assumptions": []}


def turn(content, label, tag, max_fix=3):
    """One person turn: ask, run, repair on error (up to 3), then show the
    render once and let the model correct itself."""
    reply = ask(content, label)
    print(f"\n[{label}] {reply.get('message')}\n  assumptions: {reply.get('assumptions')}")
    for attempt in range(max_fix + 1):
        if not reply.get("code"):
            return reply, None
        info, stl_or_err, took = build(reply["code"], f"{tag}_{attempt}")
        if info:
            print(f"  built in {took:.1f}s: {info}")
            png = render(stl_or_err, f"{tag}_{attempt}")
            return reply, (info, stl_or_err, png)
        print(f"  build error, asking for a fix: {stl_or_err.splitlines()[-1][:160]}")
        reply = ask(f"The code failed:\n{stl_or_err}\nFix it and answer in the same JSON.", f"{label} fix {attempt + 1}")
    return reply, None


sketch = HERE / "sketch.jpg"
reply, built = turn([
    {"type": "input_text", "text": "Here is my sketch. Can you make it into a 3D part I can print?"},
    {"type": "input_image", "image_url": f"data:image/jpeg;base64,{b64(sketch)}"},
], "1 sketch", "t1")

if built:
    info, stl, png = built
    reply, built2 = turn([
        {"type": "input_text", "text": f"This is what your code built (bounding box {info['size']} mm, volume {info['volume']} mm3). "
                                       "Compare it with my sketch. If anything is wrong, fix it; if it matches, say so and repeat the same code."},
        {"type": "input_image", "image_url": f"data:image/png;base64,{b64(png)}"},
    ], "2 self-check", "t2")
    built = built2 or built

reply, built = turn([{"type": "input_text", "text": "Nice. Make the walls 3 mm, round the vertical outside edges with a 5 mm radius, "
                                                    "and add a matching lid that sits on top with a 1 mm lip inside. Put the lid next to the box."}],
                    "3 change: walls, fillets, lid", "t3")
reply, built = turn([{"type": "input_text", "text": "Add a 12 x 6 mm slot with rounded ends on one of the long sides, 8 mm above the floor, for a USB cable."}],
                    "4 change: USB slot", "t4")

total = round(sum(x["usd"] for x in ledger), 4)
(OUT / "ledger.json").write_text(json.dumps({"model": MODEL, "steps": ledger, "total_usd": total}, indent=2))
print("\nLEDGER", MODEL)
for x in ledger:
    print(f"  {x['step']:<32} in={x['in']:>6} cached={x['cached']:>6} out={x['out']:>6} (reasoning {x['reasoning']:>5})  {x['seconds']:>5}s  ${x['usd']}")
print(f"  TOTAL ${total}")
print("BUILDS", PEAKS)
