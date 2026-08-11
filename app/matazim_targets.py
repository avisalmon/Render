"""Chapter 10 §10.7 - the entrance-test target objects.

Three parametric templates, randomised per applicant, each buildable in
Tinkercad in about twenty minutes by someone who has done the tutorial. Every
dimension is a whole millimetre on a 2mm or 5mm grid, because a teenager types
these into a box rather than dragging them.

Why generated rather than a fixed set: because the target is what makes the
whole test un-cheatable. No model downloaded from the internet happens to be
52mm across with exactly two 8mm holes 30mm apart, so there is nothing to
detect - the only way to satisfy the spec is to build it (§10.7).

Generation is **offline**. A management command writes the STL, the parameters
and a dimensioned drawing, and those are committed; the web process only ever
reads them. It also means Avi and Litala can look at every target before an
applicant ever sees one.
"""

import math
import random

from .matazim_geometry import circle_ring, extrude, measure, write_stl

# ---------------------------------------------------------------------------
# Templates
#
# Each returns (outline, holes, height, facts) where `facts` is what the
# drawing labels and what the checker compares against - i.e. the ground truth,
# stated rather than re-derived from the mesh.
# ---------------------------------------------------------------------------


def cube_with_hole(rng):
    """The reference difficulty: a block with one through-hole down the middle.

    Two Tinkercad skills and no more - set a box's dimensions, and drop a
    cylinder in as a hole.
    """
    w = rng.choice([30, 35, 40, 45, 50])
    d = rng.choice([30, 35, 40])
    h = rng.choice([20, 25, 30, 35, 40])
    hole_d = rng.choice([8, 10, 12, 14])
    outline = [(0, 0), (w, 0), (w, d), (0, d)]
    holes = [circle_ring(w / 2, d / 2, hole_d / 2)]
    facts = {
        "shape": "cube_with_hole",
        "title": "תיבה עם חור",
        "width": w, "depth": d, "height": h,
        "holes": [{"diameter": hole_d, "x": w / 2, "y": d / 2}],
        "hole_count": 1,
    }
    return outline, holes, h, facts


def plate_two_holes(rng):
    """A plate with two through-holes: the same skills, plus placing something
    accurately rather than just centring it."""
    w = rng.choice([50, 60, 70, 80])
    d = rng.choice([25, 30, 35])
    t = rng.choice([6, 8, 10, 12])
    hole_d = rng.choice([6, 8, 10])
    inset = rng.choice([12, 15, 18])
    outline = [(0, 0), (w, 0), (w, d), (0, d)]
    centres = [(inset, d / 2), (w - inset, d / 2)]
    holes = [circle_ring(cx, cy, hole_d / 2) for cx, cy in centres]
    facts = {
        "shape": "plate_two_holes",
        "title": "לוח עם שני חורים",
        "width": w, "depth": d, "height": t,
        "holes": [{"diameter": hole_d, "x": cx, "y": cy} for cx, cy in centres],
        "hole_count": 2,
    }
    return outline, holes, t, facts


def stepped_block(rng):
    """An L-shaped step: no holes, but it forces them to combine two solids and
    group them, which is the third Tinkercad skill worth having."""
    w = rng.choice([40, 50, 60])
    d = rng.choice([30, 40, 50])
    h = rng.choice([15, 20, 25])
    step_w = rng.choice([15, 20, 25])
    step_d = rng.choice([15, 20])
    step_w = min(step_w, w - 10)
    step_d = min(step_d, d - 10)
    outline = [(0, 0), (w, 0), (w, step_d), (step_w, step_d), (step_w, d), (0, d)]
    facts = {
        "shape": "stepped_block",
        "title": "בלוק מדורג",
        "width": w, "depth": d, "height": h,
        "step_width": step_w, "step_depth": step_d,
        "holes": [],
        "hole_count": 0,
    }
    return outline, [], h, facts


TEMPLATES = [cube_with_hole, plate_two_holes, stepped_block]


# ---------------------------------------------------------------------------
# Building one target
# ---------------------------------------------------------------------------

def build(seed, template=None):
    """Build one target deterministically from `seed`.

    Deterministic on purpose: the same seed always yields the same object, so a
    target can be regenerated from its parameters alone and a bug fix does not
    silently change what an applicant was already asked to make.
    """
    rng = random.Random(seed)
    fn = template or rng.choice(TEMPLATES)
    outline, holes, height, facts = fn(rng)
    tris = extrude(outline, holes, height)
    m = measure(tris)

    facts["seed"] = seed
    # The ground truth the checker compares against. Measured from the mesh
    # rather than computed from the ideal solid, so the tessellation deficit is
    # already baked in and cancels against the applicant's own faceted export.
    facts["reference"] = {
        "dims": list(m["dims"]),
        "volume": m["volume"],
        "area": m["area"],
        "cut_volume": m["cut_volume"],
        "genus": m["genus"],
        "shells": m["shells"],
        "bbox_volume": m["bbox_volume"],
    }
    if m["genus"] != facts["hole_count"]:
        raise ValueError(
            f"{facts['shape']}: built genus {m['genus']} but the brief says "
            f"{facts['hole_count']} holes")
    return tris, facts


def stl_bytes(tris, facts):
    return write_stl(tris, facts["shape"])


# ---------------------------------------------------------------------------
# The dimensioned drawing
#
# An SVG rather than a raster: it scales on a phone, it is a few KB, and it is
# readable in the repo. Reading a dimensioned drawing is a genuine skill and it
# is the half of the brief that actually tells them what to build - the 3D view
# only shows them what it looks like.
# ---------------------------------------------------------------------------

def drawing_svg(facts, px=520):
    w, d, h = facts["width"], facts["depth"], facts["height"]
    pad = 46
    scale = (px - 2 * pad) / max(w, d + h + 18)
    ox, oy = pad, pad

    def X(v):   # SVG x, with the plan drawn left-to-right
        return ox + v * scale

    def Y(v):   # SVG y, flipped so +y is up in the plan
        return oy + (d - v) * scale

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {px} {px}" '
        f'width="{px}" height="{px}" font-family="Heebo, Arial, sans-serif">',
        f'<rect width="{px}" height="{px}" fill="#ffffff"/>',
    ]
    ink, dim = "#1c1b18", "#585ba8"

    def hdim(x1, x2, y, label):
        """A horizontal dimension with end ticks."""
        return (f'<line x1="{x1:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" '
                f'stroke="{dim}" stroke-width="1.4"/>'
                f'<line x1="{x1:.1f}" y1="{y - 4:.1f}" x2="{x1:.1f}" y2="{y + 4:.1f}" '
                f'stroke="{dim}" stroke-width="1.4"/>'
                f'<line x1="{x2:.1f}" y1="{y - 4:.1f}" x2="{x2:.1f}" y2="{y + 4:.1f}" '
                f'stroke="{dim}" stroke-width="1.4"/>'
                f'<text x="{(x1 + x2) / 2:.1f}" y="{y + 15:.1f}" fill="{dim}" '
                f'font-size="14" text-anchor="middle">{label}</text>')

    def vdim(y1, y2, x, label):
        return (f'<line x1="{x:.1f}" y1="{y1:.1f}" x2="{x:.1f}" y2="{y2:.1f}" '
                f'stroke="{dim}" stroke-width="1.4"/>'
                f'<line x1="{x - 4:.1f}" y1="{y1:.1f}" x2="{x + 4:.1f}" y2="{y1:.1f}" '
                f'stroke="{dim}" stroke-width="1.4"/>'
                f'<line x1="{x - 4:.1f}" y1="{y2:.1f}" x2="{x + 4:.1f}" y2="{y2:.1f}" '
                f'stroke="{dim}" stroke-width="1.4"/>'
                f'<text x="{x + 6:.1f}" y="{(y1 + y2) / 2:.1f}" fill="{dim}" '
                f'font-size="14">{label}</text>')

    # --- plan view -------------------------------------------------------
    if facts["shape"] == "stepped_block":
        sw, sd = facts["step_width"], facts["step_depth"]
        pts = [(0, 0), (w, 0), (w, sd), (sw, sd), (sw, d), (0, d)]
    else:
        pts = [(0, 0), (w, 0), (w, d), (0, d)]
    path = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in pts)
    parts.append(f'<polygon points="{path}" fill="#e6e7f6" stroke="{ink}" '
                 f'stroke-width="2"/>')

    for hole in facts["holes"]:
        parts.append(
            f'<circle cx="{X(hole["x"]):.1f}" cy="{Y(hole["y"]):.1f}" '
            f'r="{hole["diameter"] / 2 * scale:.1f}" fill="#ffffff" '
            f'stroke="{ink}" stroke-width="2"/>')
        parts.append(
            f'<text x="{X(hole["x"]):.1f}" y="{Y(hole["y"]) - hole["diameter"] / 2 * scale - 5:.1f}" '
            f'fill="{dim}" font-size="13" text-anchor="middle">'
            f'⌀{hole["diameter"]:g}</text>')

    # --- dimensions on the plan -----------------------------------------
    parts.append(hdim(X(0), X(w), Y(0) + 22, f"{w:g}"))
    parts.append(vdim(Y(0), Y(d), X(w) + 22, f"{d:g}"))

    if facts["holes"] and facts["hole_count"] == 2:
        # Centre-to-centre, placed below the width so it cannot collide with
        # the view caption at the top of the sheet.
        hx = [hole["x"] for hole in facts["holes"]]
        parts.append(hdim(X(hx[0]), X(hx[1]), Y(0) + 46, f"{abs(hx[1] - hx[0]):g}"))

    if facts["shape"] == "stepped_block":
        parts.append(f'<text x="{X(facts["step_width"] / 2):.1f}" y="{Y(facts["step_depth"]) - 8:.1f}" '
                     f'fill="{dim}" font-size="13" text-anchor="middle">'
                     f'{facts["step_width"]:g}</text>')
        parts.append(f'<text x="{X(facts["step_width"]) + 6:.1f}" y="{Y(facts["step_depth"] / 2):.1f}" '
                     f'fill="{dim}" font-size="13">{facts["step_depth"]:g}</text>')

    # --- elevation, so the height is not left to guesswork ---------------
    ey = Y(0) + (86 if facts["hole_count"] == 2 else 62)
    parts.append(f'<rect x="{X(0):.1f}" y="{ey:.1f}" width="{w * scale:.1f}" '
                 f'height="{h * scale:.1f}" fill="#e6e7f6" stroke="{ink}" stroke-width="2"/>')
    parts.append(vdim(ey, ey + h * scale, X(w) + 22, f"{h:g}"))
    parts.append(f'<text x="{X(0):.1f}" y="{ey + h * scale + 20:.1f}" fill="#6b675f" '
                 f'font-size="12">מבט צד · '
                 f'גובה {h:g} מ"מ</text>')
    parts.append(f'<text x="{X(0):.1f}" y="{oy - 16}" fill="#6b675f" font-size="12">'
                 f'מבט על · כל המידות '
                 f'במ"מ</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def brief_lines(facts):
    """The spec in words, for anyone who cannot read the drawing (and for the
    screen-reader path)."""
    lines = [f'מידות חיצוניות: {facts["width"]:g} × {facts["depth"]:g} × {facts["height"]:g} מ"מ']
    if facts["hole_count"] == 1:
        lines.append(f'חור עובר אחד בקוטר {facts["holes"][0]["diameter"]:g} מ"מ, במרכז')
    elif facts["hole_count"] == 2:
        gap = abs(facts["holes"][1]["x"] - facts["holes"][0]["x"])
        lines.append(f'שני חורים עוברים בקוטר {facts["holes"][0]["diameter"]:g} מ"מ, '
                     f'במרחק {gap:g} מ"מ זה מזה')
    if facts["shape"] == "stepped_block":
        lines.append(f'מדרגה בפינה: {facts["step_width"]:g} × {facts["step_depth"]:g} מ"מ')
    lines.append("הכל גוף אחד סגור")
    return lines


def sanity_check_all(count=60):
    """Build a spread of targets and assert every one is a sane, buildable
    solid. Run by the generator command and by the tests, because a target that
    is subtly broken would fail applicants who did nothing wrong."""
    problems = []
    for seed in range(count):
        try:
            tris, facts = build(seed)
            m = measure(tris)
            if not m["watertight"]:
                problems.append(f"seed {seed}: not watertight")
            if m["shells"] != 1:
                problems.append(f"seed {seed}: {m['shells']} shells")
            if m["genus"] != facts["hole_count"]:
                problems.append(f"seed {seed}: genus {m['genus']}")
            if m["volume"] <= 0:
                problems.append(f"seed {seed}: volume {m['volume']}")
            # Buildable in twenty minutes means small numbers on a coarse grid.
            for v in (facts["width"], facts["depth"], facts["height"]):
                if not (5 <= v <= 90) or abs(v - round(v)) > 1e-9:
                    problems.append(f"seed {seed}: awkward dimension {v}")
            for hole in facts["holes"]:
                if hole["diameter"] < 5:
                    problems.append(f"seed {seed}: hole too small to drill cleanly")
                if math.isclose(hole["diameter"], 0):
                    problems.append(f"seed {seed}: zero hole")
        except Exception as exc:                       # noqa: BLE001 - reported
            problems.append(f"seed {seed}: {exc}")
    return problems
