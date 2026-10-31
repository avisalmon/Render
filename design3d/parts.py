"""Designs with several parts (Chapter 7, REQ-D3.60 to D3.66).

The model writes one OpenSCAD file with one module per part, each drawn
where it sits in the assembly, and lists the parts in its JSON. The server
builds each part alone (`part = "<name>"`), then, in pure Python:

- turns each printed part flat for printing (`orient`): the model's hint,
  or, when the hint leaves too little on the bed, the best of the six flat
  sides;
- lays the printed parts out on one plate, 10 mm apart (`plate`);
- writes one 3MF with every printed copy as its own object (`to_3mf`);
- checks the fit between parts in the assembly (`fit`): parts that overlap,
  and fits tighter than a printer can make.

Pure Python like `printcheck`, so nothing heavy loads beside the site.
"""

import io
import math
import re
import struct
import zipfile
from collections import defaultdict

from . import printcheck
from .render import bounds, read_stl

MAX_PARTS = 8
NAME = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
NAMED = {"black": "#1a1a1a", "white": "#f2f2f2", "red": "#d62828", "orange": "#ff7a1a", "yellow": "#f7d046",
         "green": "#3fa34d", "blue": "#2f6fd6", "purple": "#8e5bd6", "pink": "#ff6b9a", "grey": "#8a8a8a",
         "gray": "#8a8a8a", "brown": "#8b5a2b", "silver": "#c0c0c0", "gold": "#d4a72c"}
GAP = 10.0  # mm between parts on the plate
PLATE_WIDTH = 220.0  # mm, a common bed
TIGHT = 0.15  # mm: closer than this (and not touching) is too tight to print as a fit
TOUCH = 0.01  # mm: closer than this is touching, which separate parts may do
COLORS = ["#ff7a1a", "#35d0ff", "#9be15d", "#f7d046", "#d38cff", "#ff6b8b", "#5ee0c1", "#c9a27a"]


def clean(declared):
    """The model's part list, checked: names that are OpenSCAD identifiers,
    unique, at most 8; a count from 1 to 20; printed or not; a print
    rotation of three numbers. Returns [] for a one-part design."""
    if not isinstance(declared, list) or len(declared) < 2:
        return []
    out, seen = [], set()
    for d in declared[:MAX_PARTS]:
        if not isinstance(d, dict):
            continue
        name = str(d.get("name") or "").strip().lower()
        if not NAME.match(name) or name in seen or name in ("all", "part"):
            continue
        seen.add(name)
        try:
            count = max(1, min(20, int(d.get("count") or 1)))
        except (TypeError, ValueError):
            count = 1
        rot = d.get("print")
        if not (isinstance(rot, list) and len(rot) == 3):
            rot = [0, 0, 0]
        try:
            rot = [float(r) for r in rot]
        except (TypeError, ValueError):
            rot = [0.0, 0.0, 0.0]
        color = str(d.get("color") or "").strip().lower()
        color = NAMED.get(color, color)
        out.append({"name": name, "label": str(d.get("label") or name.replace("_", " ").title())[:80],
                    "count": count, "printed": d.get("printed") is not False, "print": rot,
                    "color": color if HEX.match(color) else "", "together": d.get("together") is True})
    return out if len(out) >= 2 else []


# ---------- turning and moving triangles ----------

def _rotate(tris, rx, ry, rz):
    """Rotate about x, then y, then z (degrees), like OpenSCAD's rotate([x, y, z])."""
    cx, sx = math.cos(math.radians(rx)), math.sin(math.radians(rx))
    cy, sy = math.cos(math.radians(ry)), math.sin(math.radians(ry))
    cz, sz = math.cos(math.radians(rz)), math.sin(math.radians(rz))

    def r(p):
        x, y, z = p
        y, z = y * cx - z * sx, y * sx + z * cx
        x, z = x * cy + z * sy, -x * sy + z * cy
        x, y = x * cz - y * sz, x * sz + y * cz
        return (x, y, z)

    return [tuple(r(p) for p in t) for t in tris]


def _move(tris, dx, dy, dz):
    return [tuple((p[0] + dx, p[1] + dy, p[2] + dz) for p in t) for t in tris]


def _to_bed(tris):
    """Moved so its lowest point is on z = 0 and its corner at x = y = 0."""
    lo, _ = bounds(tris)
    return _move(tris, -lo[0], -lo[1], -lo[2])


def _bed_score(tris):
    """How well it sits: area flat on the bed, less what hangs over air."""
    flat = _to_bed(tris)
    contact = over = 0.0
    for t in flat:
        n, a = printcheck._normal_area(t)
        if n[2] < -0.99 and all(abs(p[2]) < printcheck.ON_BED for p in t):
            contact += a
        elif n[2] < -0.71 and max(p[2] for p in t) > printcheck.BED_FILLET:
            over += a
    return contact - 0.5 * over, contact


SIDES = {"as drawn": (0, 0, 0), "upside down": (180, 0, 0), "on its front": (90, 0, 0),
         "on its back": (-90, 0, 0), "on its left side": (0, 90, 0), "on its right side": (0, -90, 0)}


def orient(tris, hint):
    """(triangles flat on the bed, a word on how). The model's hint is kept
    unless one of the six flat sides is clearly better (more on the bed, less
    over air): a lid drawn on its plug, as it sits in the box, prints upside
    down."""
    hint_score, _ = _bed_score(_rotate(tris, *hint))
    side, rot = max(SIDES.items(), key=lambda kv: _bed_score(_rotate(tris, *kv[1]))[0])
    best_score, _ = _bed_score(_rotate(tris, *rot))
    if best_score <= hint_score + max(25.0, 0.2 * abs(hint_score)):
        return _to_bed(_rotate(tris, *hint)), ",".join(f"{r:g}" for r in hint)
    return _to_bed(_rotate(tris, *rot)), ",".join(f"{r:g}" for r in rot) + " auto"


def plate(pieces):
    """Lay flat pieces out in rows on a 220 mm bed, 10 mm apart.
    `pieces` is [(label, triangles, colour)] or a list of those (a group
    printed together: colour regions of one object, moved as one), each
    already on the bed at 0, 0. Returns [(label, placed triangles, colour)]."""
    units = [u if isinstance(u, list) else [u] for u in pieces]
    placed, x, y, row = [], 0.0, 0.0, 0.0
    for unit in sorted(units, key=lambda u: -bounds([t for m in u for t in m[1]])[1][1]):
        _, hi = bounds([t for m in unit for t in m[1]])
        if x > 0 and x + hi[0] > PLATE_WIDTH:
            x, y, row = 0.0, y + row + GAP, 0.0
        for label, tris, *rest in unit:
            placed.append((label, _move(tris, x, y, 0), rest[0] if rest else ""))
        x += hi[0] + GAP
        row = max(row, hi[1])
    return placed


# ---------- files ----------

def to_stl(tris, name=b"design3d"):
    out = io.BytesIO()
    out.write(name[:80].ljust(80, b" "))
    out.write(struct.pack("<I", len(tris)))
    for t in tris:
        n, _ = printcheck._normal_area(t)
        out.write(struct.pack("<12fH", *n, *t[0], *t[1], *t[2], 0))
    return out.getvalue()


def to_3mf(objects):
    """A 3MF (a zip of XML) with each (name, triangles[, colour]) as its own
    object, in place. Every modern slicer opens it with the parts kept apart;
    a colour goes in as the object's base material (3MF core), which Bambu
    Studio, PrusaSlicer and Cura show on load and map to a filament."""
    from xml.sax.saxutils import quoteattr

    colors = []
    for o in objects:
        c = o[2] if len(o) > 2 else ""
        if c and c not in colors:
            colors.append(c)
    body = []
    if colors:
        body.append('<basematerials id="1">')
        body.extend(f'<base name="{c}" displaycolor="{c.upper()}FF"/>' for c in colors)
        body.append("</basematerials>")
    for i, o in enumerate(objects, 2):
        name, tris = o[0], o[1]
        c = o[2] if len(o) > 2 else ""
        index, verts, faces = {}, [], []
        for t in tris:
            ids = []
            for p in t:
                key = (round(p[0], 4), round(p[1], 4), round(p[2], 4))
                if key not in index:
                    index[key] = len(verts)
                    verts.append(key)
                ids.append(index[key])
            if len(set(ids)) == 3:
                faces.append(ids)
        paint = f' pid="1" pindex="{colors.index(c)}"' if c else ""
        body.append(f'<object id="{i}" type="model" name={quoteattr(name)}{paint}><mesh><vertices>')
        body.extend(f'<vertex x="{x:g}" y="{y:g}" z="{z:g}"/>' for x, y, z in verts)
        body.append("</vertices><triangles>")
        body.extend(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in faces)
        body.append("</triangles></mesh></object>")
    items = "".join(f'<item objectid="{i}"/>' for i in range(2, len(objects) + 2))
    model = ('<?xml version="1.0" encoding="UTF-8"?>'
             '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
             '<metadata name="Application">design3d</metadata><resources>' + "".join(body)
             + f"</resources><build>{items}</build></model>")
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
                   'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
        z.writestr("3D/3dmodel.model", model)
    return out.getvalue()


# ---------- the fit between parts ----------

NUDGE = (0.0137, 0.0071)  # mm: the ray is moved off exact edges and faces


def _inside(point, grid, i, j, cell, tris):
    """Ray parity along +z: is the point inside the closed mesh? The ray
    starts a hair beside the point, so a vertex that lies exactly on a
    vertical face of the other part (two posts with the same outline) does
    not graze that face and read as inside (found on 2026-10-30)."""
    crossings = set()
    pi, pj = point[i] + NUDGE[0], point[j] + NUDGE[1]
    for m in grid.get((int(math.floor(pi / cell)), int(math.floor(pj / cell))), ()):
        h = printcheck._hit(tris[m], 2, i, j, pi, pj)
        if h is not None and h > point[2] + 1e-6:
            crossings.add(round(h, 5))  # a ray through a shared edge counts once
    return len(crossings) % 2 == 1


def _point_triangle(p, t):
    """The distance from a point to a triangle (Ericson, Real-Time Collision Detection 5.1.5)."""
    a, b, c = t
    ab = [b[k] - a[k] for k in range(3)]
    ac = [c[k] - a[k] for k in range(3)]
    ap = [p[k] - a[k] for k in range(3)]

    def dot(u, v):
        return u[0] * v[0] + u[1] * v[1] + u[2] * v[2]

    def at(s, u, v):
        return [s[k] + u * ab[k] + v * ac[k] for k in range(3)]

    d1, d2 = dot(ab, ap), dot(ac, ap)
    if d1 <= 0 and d2 <= 0:
        q = a
    else:
        bp = [p[k] - b[k] for k in range(3)]
        d3, d4 = dot(ab, bp), dot(ac, bp)
        cp = [p[k] - c[k] for k in range(3)]
        d5, d6 = dot(ab, cp), dot(ac, cp)
        vc, vb, va = d1 * d4 - d3 * d2, d5 * d2 - d1 * d6, d3 * d6 - d5 * d4
        if d3 >= 0 and d4 <= d3:
            q = b
        elif vc <= 0 and d1 >= 0 and d3 <= 0:
            q = at(a, d1 / (d1 - d3), 0)
        elif d6 >= 0 and d5 <= d6:
            q = c
        elif vb <= 0 and d2 >= 0 and d6 <= 0:
            q = at(a, 0, d2 / (d2 - d6))
        elif va <= 0 and (d4 - d3) >= 0 and (d5 - d6) >= 0:
            w = (d4 - d3) / ((d4 - d3) + (d5 - d6))
            q = [b[k] + w * (c[k] - b[k]) for k in range(3)]
        else:
            denom = 1 / (va + vb + vc)
            q = at(a, vb * denom, vc * denom)
    return math.dist(p, q)


def _sample(tris, limit=4000):
    pts = list({p for t in tris for p in t})
    step = max(1, len(pts) // limit)
    return pts[::step]


def _pair(a_tris, b_tris):
    """(overlapping points of a inside b, the smallest gap from a to b under
    TIGHT that is not touching, or None)."""
    lo, hi = bounds(b_tris)
    span = max(hi[k] - lo[k] for k in range(3)) or 1
    cell = max(span / 40, 0.5)
    grid, i, j = printcheck._axis_grid(b_tris, 2, cell)
    near = defaultdict(list)
    for n, t in enumerate(b_tris):
        tlo = [min(p[k] for p in t) - TIGHT for k in range(3)]
        thi = [max(p[k] for p in t) + TIGHT for k in range(3)]
        for gx in range(int(tlo[0] // cell), int(thi[0] // cell) + 1):
            for gy in range(int(tlo[1] // cell), int(thi[1] // cell) + 1):
                for gz in range(int(tlo[2] // cell), int(thi[2] // cell) + 1):
                    near[(gx, gy, gz)].append(n)
    inside, tight = 0, None
    for p in _sample(a_tris):
        if not all(lo[k] - TIGHT <= p[k] <= hi[k] + TIGHT for k in range(3)):
            continue
        d = min((_point_triangle(p, b_tris[n]) for n in near.get((int(p[0] // cell), int(p[1] // cell), int(p[2] // cell)), ())),
                default=None)
        if d is not None and d < TOUCH:
            continue  # on b's surface: touching, which separate parts may do
        if _inside(p, grid, i, j, cell, b_tris):
            inside += 1
        elif d is not None and d < TIGHT and (tight is None or d < tight):
            tight = d
    return inside, tight


def fit(parts):
    """Findings between parts in their assembled places, in the shape of the
    print checks. `parts` is [(name, label, printed, triangles[, together])].
    Two colour regions printed together are one object: they touch with no
    gap by design, so only an overlap is a finding between them."""
    findings = []
    for x in range(len(parts)):
        for y in range(x + 1, len(parts)):
            na, la, pa, ta, *ga = parts[x]
            nb, lb, pb, tb, *gb = parts[y]
            fused = bool(ga and ga[0] and gb and gb[0])
            (alo, ahi), (blo, bhi) = bounds(ta), bounds(tb)
            if any(ahi[k] < blo[k] - TIGHT or bhi[k] < alo[k] - TIGHT for k in range(3)):
                continue  # far apart
            in_ab, tight_ab = _pair(ta, tb)
            in_ba, tight_ba = _pair(tb, ta)
            hardware = not (pa and pb)
            if in_ab + in_ba >= 3:
                text = (f"{la} and {lb} overlap in the assembly: "
                        + ("the hole for it is too small or in the wrong place." if hardware
                           else "they cannot both be where they are drawn."))
                findings.append({"level": "warn", "code": "overlap", "parts": [na, nb], "text": text,
                                 "fix": f"{la} and {lb} overlap. Make room between them: about 0.3 mm for a sliding fit, "
                                        "0.2 mm for a snug one" + (", and size the hole for the hardware." if hardware else ".")})
                continue
            tight = min([g for g in (tight_ab, tight_ba) if g is not None], default=None)
            if tight is not None and pa and pb and not fused:
                findings.append({"level": "warn", "code": "too_tight", "parts": [na, nb],
                                 "text": f"{la} and {lb} are only {tight:.2f} mm apart where they meet. Printed parts need "
                                         "about 0.2 mm to fit together.",
                                 "fix": f"{la} and {lb} are {tight:.2f} mm apart. Leave 0.2 to 0.3 mm between them where they fit together."})
    return findings


def assembled(stls):
    """One STL of every part in its place, for previews and the self-check."""
    return to_stl([t for data in stls for t in read_stl(data)])
