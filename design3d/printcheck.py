"""Print-ready checks on a built part (spec, "planned right after the first
release"; sprint D3.7).

Pure Python on the STL's triangles, so nothing heavy loads beside the site
(the server is 512 MB and shared). Each finding is a dict:

    {"level": "warn" | "note", "code": "...", "text": "what is wrong, plainly",
     "fix": "what to ask the model, when the person taps Fix it"}

`warn` means the print will likely fail or come out wrong; `note` means it
will print but the person should know (supports). An empty list means
ready to print.

Thin walls are measured by rays: from a sample of faces that point along an
axis, a ray goes into the part to the opposite surface; the distance is the
wall there. Faces are put in a 2D grid per axis, so a ray tests only the few
faces in its cell.
"""

import math
from collections import defaultdict

from .render import read_stl

NOZZLE_WALL = 0.8  # mm: two lines of a 0.4 mm nozzle
BED = (220, 220, 250)  # mm: what most home printers take
ON_BED = 0.05  # mm
FUSE_GAP = 0.2  # mm
SLIVER = 0.15  # mm: thinner is a modelling sliver a slicer drops, not a wall
THIN_AREA = 1.0  # mm2 of thin wall before it is worth a note
THIN_WARN_AREA = 5.0  # mm2: a thin spot (a thread's feather edge) is a note, a thin wall a warning
BED_FILLET = 3.0  # mm: rounded bottom edges below this print fine
# Memory: about 1.1 KB per triangle measured (30k triangles, 32 MB), and the
# site shares a 512 MB server. Bodies and walls are checked up to 60k
# triangles; above 150k nothing is checked.
MAX_TRIANGLES = 60_000
TOO_DETAILED = 150_000
SAMPLES = 600


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _normal_area(t):
    u, v = _sub(t[1], t[0]), _sub(t[2], t[0])
    n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    length = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
    if length == 0:
        return (0.0, 0.0, 0.0), 0.0
    return (n[0] / length, n[1] / length, n[2] / length), length / 2


def _components(tris):
    """Bodies: groups of triangles that share vertices. Returns a list of
    lists of triangle indexes."""
    parent = {}

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    keys = []
    for t in tris:
        ks = [tuple(round(c, 4) for c in p) for p in t]
        for k in ks:
            parent.setdefault(k, k)
        a = find(ks[0])
        for k in ks[1:]:
            b = find(k)
            if a != b:
                parent[b] = a
        keys.append(ks[0])
    groups = defaultdict(list)
    for i, k in enumerate(keys):
        groups[find(k)].append(i)
    return list(groups.values())


def _axis_grid(tris, axis, cell):
    """Faces bucketed by their bounding box on the plane across `axis`."""
    i, j = [a for a in range(3) if a != axis]
    grid = defaultdict(list)
    for n, t in enumerate(tris):
        lo_i, hi_i = min(p[i] for p in t), max(p[i] for p in t)
        lo_j, hi_j = min(p[j] for p in t), max(p[j] for p in t)
        for gi in range(int(math.floor(lo_i / cell)), int(math.floor(hi_i / cell)) + 1):
            for gj in range(int(math.floor(lo_j / cell)), int(math.floor(hi_j / cell)) + 1):
                grid[(gi, gj)].append(n)
    return grid, i, j


def _hit(t, axis, i, j, pi, pj):
    """Where the line along `axis` through (pi, pj) crosses face t, or None."""
    (ai, aj), (bi, bj), (ci, cj) = (t[0][i], t[0][j]), (t[1][i], t[1][j]), (t[2][i], t[2][j])
    d = (bj - cj) * (ai - ci) + (ci - bi) * (aj - cj)
    if abs(d) < 1e-12:
        return None
    w0 = ((bj - cj) * (pi - ci) + (ci - bi) * (pj - cj)) / d
    w1 = ((cj - aj) * (pi - ci) + (ai - ci) * (pj - cj)) / d
    w2 = 1 - w0 - w1
    if min(w0, w1, w2) < -1e-9:
        return None
    return w0 * t[0][axis] + w1 * t[1][axis] + w2 * t[2][axis]


def _thinnest(tris, normals, areas, size):
    """The thinnest real wall found (mm) and the height it is at, or (None,
    None). A wall counts when the ray leaves the part through the far face,
    is thicker than a sliver, and enough area of it is thin."""
    cell = max(max(size) / 60, 0.5)
    # Faces that point along an axis (within about 25 degrees), largest first,
    # spread over the whole part.
    candidates = [(areas[n], n, axis) for n in range(len(tris)) for axis in range(3)
                  if abs(normals[n][axis]) > 0.9 and areas[n] > 1e-4]
    if not candidates:
        return None, None, 0.0
    candidates.sort(reverse=True)
    step = max(1, len(candidates) // SAMPLES)
    picked = candidates[::step][:SAMPLES]
    grids = {}
    best, where, thin_area = None, None, 0.0
    for area, n, axis in picked:
        if axis not in grids:
            grids[axis] = _axis_grid(tris, axis, cell)
        grid, i, j = grids[axis]
        t = tris[n]
        p = [(t[0][k] + t[1][k] + t[2][k]) / 3 for k in range(3)]
        inward = -1 if normals[n][axis] > 0 else 1
        nearest = None
        for m in grid.get((int(math.floor(p[i] / cell)), int(math.floor(p[j] / cell))), ()):
            if m == n:
                continue
            h = _hit(tris[m], axis, i, j, p[i], p[j])
            if h is None:
                continue
            dist = (h - p[axis]) * inward
            if dist > 1e-3 and (nearest is None or dist < nearest[0]):
                nearest = (dist, m)
        if nearest is None:
            continue
        dist, m = nearest
        leaves = normals[m][axis] * inward > 0.5  # the far face looks out along the ray
        if leaves and SLIVER <= dist < NOZZLE_WALL:
            thin_area += area * step
            if best is None or dist < best:
                best, where = dist, p[2]
    if thin_area < THIN_AREA:
        return None, None, 0.0
    return best, where, thin_area


def _closest_gap(tris, groups, limit):
    """The smallest distance between vertices of different bodies, if under
    `limit` (mm)."""
    cell = max(limit, 0.05)
    grid = defaultdict(list)
    for g, idx in enumerate(groups):
        for n in idx:
            for p in tris[n]:
                grid[(int(p[0] // cell), int(p[1] // cell), int(p[2] // cell))].append((g, p))
    best = None
    for (x, y, z), pts in grid.items():
        near = [q for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)
                for q in grid.get((x + dx, y + dy, z + dz), ())]
        for g, p in pts:
            for h, q in near:
                if h == g:
                    continue
                d = math.dist(p, q)
                if d < limit and (best is None or d < best):
                    best = d
    return best


def check(stl):
    """The findings for one STL (bytes)."""
    if len(stl) > 84 and not stl[:5].lower() == b"solid" and int.from_bytes(stl[80:84], "little") > TOO_DETAILED:
        return [{"level": "note", "code": "too_detailed",
                 "text": "The part is too detailed to check here. Look at it in your slicer before printing.",
                 "fix": "Make the part less detailed: lower $fn."}]
    tris = read_stl(stl)
    if len(tris) > TOO_DETAILED:
        return [{"level": "note", "code": "too_detailed",
                 "text": "The part is too detailed to check here. Look at it in your slicer before printing.",
                 "fix": "Make the part less detailed: lower $fn."}]
    if not tris:
        return [{"level": "warn", "code": "empty", "text": "The part is empty.", "fix": "The part came out empty. Build it again."}]
    findings = []
    xs = [p[0] for t in tris for p in t]
    ys = [p[1] for t in tris for p in t]
    zs = [p[2] for t in tris for p in t]
    lo, hi = (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))
    size = tuple(hi[k] - lo[k] for k in range(3))
    normals, areas = zip(*(_normal_area(t) for t in tris))

    # The bed.
    if abs(lo[2]) > ON_BED:
        where = "below" if lo[2] < 0 else "above"
        findings.append({"level": "note", "code": "not_on_bed",
                         "text": f"The part starts {abs(lo[2]):.1f} mm {where} the bed. Most slicers drop it onto the bed for you.",
                         "fix": "Move the part so its lowest point is exactly at z = 0."})
    contact = sum(areas[n] for n, t in enumerate(tris)
                  if normals[n][2] < -0.99 and all(abs(p[2] - lo[2]) < ON_BED for p in t))
    footprint = max(size[0] * size[1], 1e-9)
    if contact < min(25.0, 0.05 * footprint):
        findings.append({"level": "warn", "code": "small_contact",
                         "text": f"Only {contact:.0f} mm² of the part touches the bed. It may tip over or come loose while printing.",
                         "fix": "Give the part a flat face on the bed (z = 0), or turn it so a flat side lies down."})

    # Bodies: a piece in the air, or two pieces that will fuse.
    groups = _components(tris) if len(tris) <= MAX_TRIANGLES else [list(range(len(tris)))]
    floating = [g for g in groups if min(p[2] for n in g for p in tris[n]) > lo[2] + ON_BED]
    if floating:
        height = min(min(p[2] for n in g for p in tris[n]) for g in floating) - lo[2]
        findings.append({"level": "warn", "code": "floating",
                         "text": f"{len(floating)} piece{'s' if len(floating) > 1 else ''} float{'' if len(floating) > 1 else 's'} "
                                 f"in the air ({height:.1f} mm above the bed) and cannot be printed like that.",
                         "fix": "Some pieces float above the bed. Put every separate piece flat on z = 0, side by side, 10 mm apart."})
    if 1 < len(groups) <= 20:
        gap = _closest_gap(tris, groups, FUSE_GAP)
        if gap is not None:
            findings.append({"level": "warn", "code": "fuse",
                             "text": f"Two separate pieces are only {gap:.2f} mm apart. They will probably fuse when printed.",
                             "fix": f"Two separate pieces are {gap:.2f} mm apart and will fuse. Leave at least 0.3 mm between parts that must move, or join them."})

    # Walls.
    if len(tris) <= MAX_TRIANGLES:
        thinnest, at, thin_area = _thinnest(tris, normals, areas, size)
        if thinnest is not None and thin_area >= THIN_WARN_AREA:
            findings.append({"level": "warn", "code": "thin_wall",
                             "text": f"A wall is only {thinnest:.2f} mm thick (at {at - lo[2]:.0f} mm height). "
                                     f"Most printers need at least {NOZZLE_WALL} mm.",
                             "fix": f"A wall is {thinnest:.2f} mm thick. Make every wall at least 1.2 mm thick."})
        elif thinnest is not None:
            findings.append({"level": "note", "code": "thin_spot",
                             "text": f"A small spot is only {thinnest:.2f} mm thick (at {at - lo[2]:.0f} mm height). "
                                     "It may print rough or not at all.",
                             "fix": f"A small spot is {thinnest:.2f} mm thick. Thicken it to at least 1 mm or remove it."})

    # Size.
    if size[0] > BED[0] or size[1] > BED[1] or size[2] > BED[2]:
        findings.append({"level": "warn", "code": "too_big",
                         "text": f"The part is {size[0]:.0f} x {size[1]:.0f} x {size[2]:.0f} mm, bigger than most printers "
                                 f"({BED[0]} x {BED[1]} x {BED[2]} mm).",
                         "fix": f"Make the part fit inside {BED[0]} x {BED[1]} x {BED[2]} mm, or split it into pieces that do."})

    # Overhangs: faces that look down at more than 45 degrees, above the
    # rounded bottom edges.
    over = sum(areas[n] for n, t in enumerate(tris)
               if normals[n][2] < -0.71 and max(p[2] for p in t) > lo[2] + BED_FILLET)
    if over > 100:
        findings.append({"level": "note", "code": "overhang",
                         "text": f"About {over / 100:.0f} cm² hangs over air. It will need supports, or a turn of the part.",
                         "fix": "Change the part so it needs no supports: turn it, or replace overhangs with 45 degree slopes or chamfers."})
    return findings
