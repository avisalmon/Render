"""Chapter 10 §10.7 - geometry for the מט״צים entrance test.

Everything the replication test needs to build a target solid and to measure how
close somebody's Tinkercad export came to it.

**Pure Python, no new dependencies.** That is a deliberate choice and it is worth
recording why, because the spec originally proposed `trimesh` or `numpy-stl`:

  * STL is a trivial format. Reading and writing it is about forty lines.
  * Every measurement below is a single pass over the triangle list: bounding
    box, volume, surface area, centroid, and the Euler number. Milliseconds.
  * The one measurement that genuinely needs numpy is a point-to-surface
    distance sweep, which is O(samples x triangles) and takes ~10s in pure
    Python. It was only ever the belt-and-braces check, and the exact measures
    below already catch every realistic way of getting the task wrong:
      - no hole, or the wrong number of holes  -> genus
      - the wrong outer size                   -> bounding box
      - the hole too big or too small          -> cut volume
      - the hole in the wrong place            -> centroid offset
      - the right numbers but the wrong shape  -> surface area
    So the project adds no dependency, which matters on a small Render
    instance. If a real submission ever slips through all six, revisit.

Coordinates are millimetres throughout, matching what a kid types into
Tinkercad.
"""

import math
import struct

# Facet count for a full circle. Tinkercad's own exports are in this range, and
# the reference is generated with the same tessellation so the ~1.6% polygon
# deficit cancels instead of showing up as a systematic error (§10.7).
CIRCLE_SEGMENTS = 24


# ---------------------------------------------------------------------------
# STL
# ---------------------------------------------------------------------------

def read_stl(data):
    """Parse binary or ASCII STL into a list of ((x,y,z), (x,y,z), (x,y,z)).

    Accepts bytes. Tinkercad exports binary; some tools emit ASCII, so both are
    handled rather than failing a kid over their export settings.
    """
    if isinstance(data, str):
        data = data.encode("utf-8", "replace")
    stripped = data.lstrip()
    # An ASCII STL starts with "solid", but so can a binary one whose header
    # happens to begin that way - so also check the length arithmetic.
    if stripped[:5].lower() == b"solid":
        looks_binary = False
        if len(data) >= 84:
            (n,) = struct.unpack_from("<I", data, 80)
            looks_binary = len(data) == 84 + n * 50
        if not looks_binary:
            return _read_ascii_stl(stripped.decode("utf-8", "replace"))
    return _read_binary_stl(data)


def _read_binary_stl(data):
    if len(data) < 84:
        raise ValueError("STL too short to be valid")
    (count,) = struct.unpack_from("<I", data, 80)
    expected = 84 + count * 50
    if len(data) < expected:
        raise ValueError("STL truncated: header claims more triangles than present")
    tris = []
    off = 84
    for _ in range(count):
        vals = struct.unpack_from("<12fH", data, off)
        tris.append((vals[3:6], vals[6:9], vals[9:12]))
        off += 50
    return tris


def _read_ascii_stl(text):
    tris, verts = [], []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 4 and parts[0] == "vertex":
            verts.append((float(parts[1]), float(parts[2]), float(parts[3])))
            if len(verts) == 3:
                tris.append(tuple(verts))
                verts = []
    if not tris:
        raise ValueError("no triangles found in ASCII STL")
    return tris


def write_stl(tris, name="matazim"):
    """Binary STL bytes. Normals are written as zero, which every slicer and
    viewer recomputes from winding order anyway."""
    out = bytearray(name.encode("ascii", "replace")[:80].ljust(80, b"\0"))
    out += struct.pack("<I", len(tris))
    for a, b, c in tris:
        out += struct.pack("<12fH", 0.0, 0.0, 0.0, *a, *b, *c, 0)
    return bytes(out)


# ---------------------------------------------------------------------------
# Polygon triangulation (ear clipping, with holes bridged in)
# ---------------------------------------------------------------------------

def _area2(ring):
    """Twice the signed area. Positive = counter-clockwise."""
    s = 0.0
    for i in range(len(ring)):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % len(ring)]
        s += x1 * y2 - x2 * y1
    return s


def _ccw(ring):
    return ring if _area2(ring) > 0 else ring[::-1]


def _strictly_inside(p, a, b, c, eps=1e-9):
    """Is `p` strictly inside the counter-clockwise triangle abc?

    Strictly, and that matters. Bridging a hole deliberately duplicates two
    vertices and threads a zero-width channel between them, so several points
    lie exactly *on* the edges of candidate ears. A boundary-inclusive test
    treats those as blocking and no ear is ever clippable, which is what makes a
    naive ear-clipper stall the moment you give it a hole.
    """
    def side(u, v, w):
        return (v[0] - u[0]) * (w[1] - u[1]) - (v[1] - u[1]) * (w[0] - u[0])
    return (side(a, b, p) > eps and side(b, c, p) > eps and side(c, a, p) > eps)


def _visible_vertex(poly, m):
    """Index of a vertex of `poly` that is mutually visible from point `m`.

    The standard construction (Eberly): cast a ray from `m` in +x, take the
    nearest boundary crossing `I`, and bridge to the endpoint of that edge with
    the larger x. If any reflex vertex of the polygon falls inside the triangle
    (m, I, p), one of *those* is the visible one instead - pick the one at the
    smallest angle to the ray.

    A "nearest vertex" heuristic looks like it works and then fails on roughly
    one polygon in five, because with two holes the nearest vertex is often on
    the far side of a channel that was cut for the previous hole. The bridge
    then crosses an existing edge and the ear clipper stalls.
    """
    best_x, best_edge = None, None
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        if (a[1] > m[1]) == (b[1] > m[1]):
            continue                                    # edge does not span m.y
        t = (m[1] - a[1]) / (b[1] - a[1])
        x = a[0] + t * (b[0] - a[0])
        if x < m[0] - 1e-12:
            continue                                    # crossing is behind us
        if best_x is None or x < best_x:
            best_x, best_edge = x, i
    if best_edge is None:
        # Degenerate: fall back to the rightmost vertex, which is always on the
        # hull and therefore reachable.
        return max(range(len(poly)), key=lambda i: poly[i][0])

    a_i, b_i = best_edge, (best_edge + 1) % len(poly)
    p_i = a_i if poly[a_i][0] > poly[b_i][0] else b_i
    inter = (best_x, m[1])

    # Any reflex vertex inside (m, inter, p) blocks the direct bridge.
    best_i, best_angle = p_i, None
    for i in range(len(poly)):
        if i == p_i:
            continue
        prev_p, cur, nxt = poly[i - 1], poly[i], poly[(i + 1) % len(poly)]
        cross = ((cur[0] - prev_p[0]) * (nxt[1] - cur[1])
                 - (cur[1] - prev_p[1]) * (nxt[0] - cur[0]))
        if cross >= 0:
            continue                                    # convex, cannot block
        if not _strictly_inside(cur, m, inter, poly[p_i]) and \
           not _strictly_inside(cur, m, poly[p_i], inter):
            continue
        dx, dy = cur[0] - m[0], cur[1] - m[1]
        angle = abs(math.atan2(dy, dx))
        if best_angle is None or angle < best_angle:
            best_angle, best_i = angle, i
    return best_i


def _bridge_holes(outer, holes):
    """Turn a polygon-with-holes into one simple polygon.

    The keyhole trick: from each hole's rightmost vertex, cut a zero-width
    channel out to a mutually visible vertex of the ring. Holes are processed
    rightmost-first so that each channel is cut into a boundary that already
    contains the ones before it.
    """
    poly = list(outer)
    for hole in sorted(holes, key=lambda h: -max(p[0] for p in h)):
        hole = list(hole)[::-1] if _area2(hole) > 0 else list(hole)  # holes run CW
        hi = max(range(len(hole)), key=lambda i: hole[i][0])
        m = hole[hi]
        oi = _visible_vertex(poly, m)
        channel = [poly[oi]] + hole[hi:] + hole[:hi] + [hole[hi]]
        poly = poly[:oi] + channel + poly[oi:]
    return poly


def triangulate(outer, holes=()):
    """Ear-clip a polygon (with optional holes) into 2D triangles.

    Correctness is not taken on trust: `extrude` checks the resulting solid is
    watertight and that its volume matches the analytic area x height, so a bad
    triangulation fails loudly at generation time rather than silently shipping
    a broken target.
    """
    poly = _ccw(list(outer))
    if holes:
        poly = _bridge_holes(poly, [list(h) for h in holes])
        poly = _ccw(poly)

    idx = list(range(len(poly)))
    tris = []
    guard = 0
    while len(idx) > 3:
        guard += 1
        if guard > 5 * len(poly) ** 2:
            raise ValueError("ear clipping failed to converge")
        clipped = False
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = poly[i0], poly[i1], poly[i2]
            # Convex corner?
            cross = ((b[0] - a[0]) * (c[1] - a[1])
                     - (b[1] - a[1]) * (c[0] - a[0]))
            if cross <= 1e-9:            # reflex, or a degenerate bridge corner
                continue
            # No other vertex strictly inside the candidate ear?
            if any(j not in (i0, i1, i2) and _strictly_inside(poly[j], a, b, c)
                   for j in idx):
                continue
            tris.append((a, b, c))
            idx.pop(k)
            clipped = True
            break
        if not clipped:
            raise ValueError("ear clipping stuck: polygon is self-intersecting?")
    if len(idx) == 3:
        tris.append(tuple(poly[i] for i in idx))
    return tris


def circle_ring(cx, cy, radius, segments=CIRCLE_SEGMENTS):
    """A regular polygon inscribed in the circle, matching how a CAD tool
    tessellates a hole."""
    return [(cx + radius * math.cos(2 * math.pi * i / segments),
             cy + radius * math.sin(2 * math.pi * i / segments))
            for i in range(segments)]


def extrude(outer, holes, height):
    """Extrude a 2D outline (with holes) along +Z into a closed solid.

    Raises if the result is not watertight or if its volume disagrees with
    area x height, so a broken triangulation can never reach an applicant.
    """
    outer = _ccw(list(outer))
    holes = [list(h) for h in holes]
    holes = [h if _area2(h) < 0 else h[::-1] for h in holes]  # holes clockwise

    caps = triangulate(outer, holes)
    tris = []
    # Bottom cap, wound so its normal points down (-Z).
    for a, b, c in caps:
        tris.append(((a[0], a[1], 0.0), (c[0], c[1], 0.0), (b[0], b[1], 0.0)))
    # Top cap.
    for a, b, c in caps:
        tris.append(((a[0], a[1], height), (b[0], b[1], height), (c[0], c[1], height)))
    # Side walls, one quad per edge of every ring.
    for ring in [outer] + holes:
        n = len(ring)
        for i in range(n):
            x1, y1 = ring[i]
            x2, y2 = ring[(i + 1) % n]
            p1 = (x1, y1, 0.0)
            p2 = (x2, y2, 0.0)
            p3 = (x2, y2, height)
            p4 = (x1, y1, height)
            tris.append((p1, p2, p3))
            tris.append((p1, p3, p4))

    m = measure(tris)
    if not m["watertight"]:
        raise ValueError("extrusion produced a non-watertight solid")
    expected = abs(_area2(outer) / 2) - sum(abs(_area2(h) / 2) for h in holes)
    expected *= height
    if expected and abs(m["volume"] - expected) / expected > 1e-6:
        raise ValueError(
            f"extrusion volume {m['volume']:.3f} != analytic {expected:.3f}")
    return tris


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------

def _key(p, places=4):
    """Weld vertices that are the same point written slightly differently.
    Without this the edge bookkeeping - and therefore the genus - is nonsense."""
    return (round(p[0], places), round(p[1], places), round(p[2], places))


def measure(tris):
    """Every figure the entrance test compares, in one pass.

    Returns bbox / dims (sorted, so orientation is irrelevant), volume, area,
    centroid, the bounding-box-minus-solid "cut volume", watertightness, the
    Euler number and the genus (= number of through-holes), and how many
    separate shells the file contains.
    """
    if not tris:
        raise ValueError("empty mesh")

    xs = [v[0] for t in tris for v in t]
    ys = [v[1] for t in tris for v in t]
    zs = [v[2] for t in tris for v in t]
    bbox = ((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs)))
    dims = tuple(sorted(hi - lo for lo, hi in zip(bbox[0], bbox[1])))

    volume = 0.0
    area = 0.0
    cx = cy = cz = 0.0
    for a, b, c in tris:
        # Signed tetrahedron volume against the origin.
        v = (a[0] * (b[1] * c[2] - b[2] * c[1])
             - a[1] * (b[0] * c[2] - b[2] * c[0])
             + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6.0
        volume += v
        cx += v * (a[0] + b[0] + c[0]) / 4.0
        cy += v * (a[1] + b[1] + c[1]) / 4.0
        cz += v * (a[2] + b[2] + c[2]) / 4.0
        # NOTE: `volume` stays *signed* until the centroid is divided out below.
        # A mirrored export - or one whose triangles are simply wound the other
        # way - has negative signed volume, and dividing the moments by the
        # absolute value there negates the centroid. That put the centre of mass
        # on the far side of the part and failed honest submissions on "the hole
        # is in the wrong place".
        ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        wx, wy, wz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
        nx, ny, nz = uy * wz - uz * wy, uz * wx - ux * wz, ux * wy - uy * wx
        area += math.sqrt(nx * nx + ny * ny + nz * nz) / 2.0
    centroid = ((cx / volume, cy / volume, cz / volume) if volume
                else (0.0, 0.0, 0.0))
    volume = abs(volume)

    # Topology, from welded vertices.
    verts, edges, edge_uses = set(), set(), {}
    for tri in tris:
        ks = [_key(v) for v in tri]
        verts.update(ks)
        for i in range(3):
            e = tuple(sorted((ks[i], ks[(i + 1) % 3])))
            edges.add(e)
            edge_uses[e] = edge_uses.get(e, 0) + 1
    # A closed surface uses every edge exactly twice.
    watertight = bool(edge_uses) and all(n == 2 for n in edge_uses.values())
    euler = len(verts) - len(edges) + len(tris)
    genus = int(round((2 - euler) / 2)) if watertight else None

    bbox_volume = (bbox[1][0] - bbox[0][0]) * (bbox[1][1] - bbox[0][1]) \
        * (bbox[1][2] - bbox[0][2])

    return {
        "triangles": len(tris),
        "bbox": bbox,
        "dims": dims,
        "volume": volume,
        "area": area,
        "centroid": centroid,
        "bbox_volume": bbox_volume,
        # What was carved out of the blank: the hole volume, without ever
        # having to find the hole (§10.7).
        "cut_volume": bbox_volume - volume,
        "watertight": watertight,
        "euler": euler,
        "genus": genus,
        "shells": count_shells(tris),
    }


def count_shells(tris):
    """How many separate connected solids the file contains. A pile of loose
    shapes that was never grouped in Tinkercad shows up here as more than one."""
    parent = {}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for tri in tris:
        ks = [_key(v) for v in tri]
        for k in ks:
            parent.setdefault(k, k)
        union(ks[0], ks[1])
        union(ks[1], ks[2])
    return len({find(k) for k in parent}) if parent else 0


def centroid_offset(m):
    """How far the solid's centre of mass sits from the centre of its bounding
    box, in mm."""
    (lo, hi), c = (m["bbox"][0], m["bbox"][1]), m["centroid"]
    box_centre = tuple((lo[i] + hi[i]) / 2 for i in range(3))
    return math.sqrt(sum((c[i] - box_centre[i]) ** 2 for i in range(3)))


def implied_hole_shift(m):
    """How far the hole itself has drifted, in mm.

    The centroid offset is **not** the hole's displacement, and reading it as
    one would set the tolerance roughly twenty times too tight. Removing a
    cut of volume `k` from a symmetric blank of volume `V`, displaced by `d`,
    moves the centre of mass by only `d * k / V`. A 10mm hole 4mm off-centre in
    a 40mm cube shifts the centroid by 0.2mm.

    So invert it, and the number this returns is the one to put in front of a
    teenager: "your hole is 4mm off", not "0.2".
    """
    cut = m["cut_volume"]
    if cut <= 0:
        return 0.0
    return centroid_offset(m) * m["volume"] / cut
