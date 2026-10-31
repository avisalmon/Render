"""Pictures of an STL, drawn with Pillow alone (no numpy on the server).

`sheet()` is three views on white, for the model's self-check (REQ-D3.21).
`preview()` is the part on the print bed, for cards and the gallery.
A flat-shaded painter's algorithm: plenty for a few tens of thousands of
triangles, and a part of that size draws in well under a second.
"""

import io
import math
import struct

from PIL import Image, ImageDraw, ImageFont


def read_stl(data):
    """Triangles as ((x, y, z), (x, y, z), (x, y, z)), ASCII or binary."""
    head = data[:512].lstrip().lower()
    if head.startswith(b"solid") and b"facet" in data[:4096]:
        tris, cur = [], []
        for line in data.decode("ascii", "replace").splitlines():
            parts = line.split()
            if parts and parts[0] == "vertex":
                cur.append(tuple(float(v) for v in parts[1:4]))
                if len(cur) == 3:
                    tris.append(tuple(cur))
                    cur = []
        return tris
    if len(data) < 84:
        return []
    (count,) = struct.unpack_from("<I", data, 80)
    tris = []
    for i in range(min(count, (len(data) - 84) // 50)):
        v = struct.unpack_from("<12f", data, 84 + i * 50)
        tris.append(((v[3], v[4], v[5]), (v[6], v[7], v[8]), (v[9], v[10], v[11])))
    return tris


def bounds(tris):
    if not tris:
        return (0, 0, 0), (0, 0, 0)
    xs = [p[0] for t in tris for p in t]
    ys = [p[1] for t in tris for p in t]
    zs = [p[2] for t in tris for p in t]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def size_mm(tris):
    lo, hi = bounds(tris)
    return " x ".join(f"{hi[i] - lo[i]:.1f}".rstrip("0").rstrip(".") for i in range(3))


_A, _B = math.radians(-45), math.radians(35.264)


def _iso(p):
    x, y, z = p
    x1 = x * math.cos(_A) - y * math.sin(_A)
    y1 = x * math.sin(_A) + y * math.cos(_A)
    y2 = y1 * math.cos(_B) - z * math.sin(_B)
    z2 = y1 * math.sin(_B) + z * math.cos(_B)
    return x1, z2, y2  # screen x, screen up, depth (larger is farther)


VIEWS = {
    "iso": _iso,
    "top": lambda p: (p[0], p[1], -p[2]),
    "front": lambda p: (p[0], p[2], p[1]),
}


def _normal(t):
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = t
    ux, uy, uz = bx - ax, by - ay, bz - az
    vx, vy, vz = cx - ax, cy - ay, cz - az
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    n = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    return nx / n, ny / n, nz / n


def _draw(tris, view, size, color, background, edge=None):
    """`color` is one (r, g, b), or a list with one per triangle."""
    w, h = size
    img = Image.new("RGBA", size, background)
    if not tris:
        return img
    project = VIEWS[view]
    pts = [[project(p) for p in t] for t in tris]
    xs = [q[0] for t in pts for q in t]
    ys = [q[1] for t in pts for q in t]
    span = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
    scale = 0.82 * min(w, h) / span
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    light = (0.35, -0.55, 0.76)
    order = sorted(range(len(tris)), key=lambda i: -sum(q[2] for q in pts[i]))
    d = ImageDraw.Draw(img)
    for i in order:
        n = _normal(tris[i])
        shade = 0.38 + 0.62 * abs(n[0] * light[0] + n[1] * light[1] + n[2] * light[2])
        fill = tuple(min(255, int(c * shade)) for c in (color[i] if isinstance(color, list) else color)) + (255,)
        poly = [(w / 2 + (q[0] - cx) * scale, h / 2 - (q[1] - cy) * scale) for q in pts[i]]
        d.polygon(poly, fill=fill, outline=edge)
    return img


def sheet(stl_bytes, pieces=None):
    """Three labelled views on white, as PNG bytes, for the model to see.
    `pieces` [(stl bytes, "#rrggbb")] draws each part in its own colour, so
    red letters on a white tag can be told apart from above."""
    color = (40, 110, 210)
    if pieces:
        tris, color = [], []
        for data, hexa in pieces:
            t = read_stl(data)
            rgb = tuple(int(hexa[k:k + 2], 16) for k in (1, 3, 5)) if len(hexa or "") == 7 else (40, 110, 210)
            tris += t
            color += [rgb] * len(t)
    else:
        tris = read_stl(stl_bytes)
    out = Image.new("RGB", (1200, 420), "white")
    d = ImageDraw.Draw(out)
    font = ImageFont.load_default()
    for i, view in enumerate(("iso", "top", "front")):
        out.paste(_draw(tris, view, (390, 390), color, (255, 255, 255, 255)), (i * 400 + 5, 25))
        d.text((i * 400 + 12, 6), view, fill="black", font=font)
    d.text((12, 402), f"size {size_mm(tris)} mm, {len(tris)} triangles", fill="black", font=font)
    buf = io.BytesIO()
    out.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def preview(stl_bytes, size=(640, 480)):
    """The part in filament orange on the dark print bed, as PNG bytes."""
    tris = read_stl(stl_bytes)
    img = _draw(tris, "iso", size, (255, 122, 26), (42, 36, 24, 255))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "PNG", optimize=True)
    return buf.getvalue()
