"""Phone photos of a book cover at an angle, made up with a real camera model,
with the book's true corners and proportion known (Avi, 2026-10-23: "I always
shoot at an angle"). Tables: wood with plank seams, plain, dark, cloth; a hand
on the bottom edge in every third. Used by the cover straightener's tests."""

import io
import math
import random

from PIL import Image, ImageDraw, ImageFilter


def solve8(A, b):
    A = [row[:] for row in A]
    b = b[:]
    n = len(b)
    for i in range(n):
        p = max(range(i, n), key=lambda k: abs(A[k][i]))
        A[i], A[p] = A[p], A[i]
        b[i], b[p] = b[p], b[i]
        for k in range(i + 1, n):
            m = A[k][i] / A[i][i]
            for j in range(i, n):
                A[k][j] -= m * A[i][j]
            b[k] -= m * b[i]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (b[i] - sum(A[i][j] * x[j] for j in range(i + 1, n))) / A[i][i]
    return x


def cover(w, h, rnd):
    base = tuple(rnd.randint(20, 235) for _ in range(3))
    im = Image.new("RGB", (w, h), base)
    d = ImageDraw.Draw(im)
    for _ in range(rnd.randint(2, 6)):  # art blocks
        x0, y0 = rnd.randint(0, w), rnd.randint(0, h)
        d.ellipse([x0 - rnd.randint(20, 160), y0 - rnd.randint(20, 160), x0 + rnd.randint(20, 160), y0 + rnd.randint(20, 160)],
                  fill=tuple(rnd.randint(0, 255) for _ in range(3)))
    band = rnd.randint(int(h * .1), int(h * .3))
    d.rectangle([0, band, w, band + h // 8], fill=tuple(rnd.randint(0, 255) for _ in range(3)))  # title band, full width
    for i in range(rnd.randint(3, 8)):  # text-ish bars
        y = rnd.randint(int(h * .5), int(h * .95))
        d.rectangle([w * .15, y, w * (.3 + rnd.random() * .55), y + 8], fill=(250, 250, 250) if sum(base) < 380 else (15, 15, 15))
    return im


def table(W, H, kind, rnd):
    if kind == "wood":
        im = Image.new("RGB", (W, H), (150, 105, 60))
        d = ImageDraw.Draw(im)
        for y in range(0, H, 3):
            c = 120 + int(30 * math.sin(y / 17.0 + rnd.random()))
            d.line([0, y, W, y + rnd.randint(-6, 6)], fill=(c + 20, c - 20, c - 60), width=2)
        for y in range(0, H, rnd.randint(90, 160)):  # plank seams: strong straight lines
            d.line([0, y, W, y], fill=(60, 40, 20), width=3)
        return im
    if kind == "plain":
        return Image.new("RGB", (W, H), (225, 222, 215))
    if kind == "dark":
        return Image.new("RGB", (W, H), (38, 36, 40))
    im = Image.effect_noise((W, H), 40).convert("RGB")  # cloth
    tint = Image.new("RGB", (W, H), tuple(rnd.randint(60, 200) for _ in range(3)))
    return Image.blend(im, tint, 0.6)


def scene(seed, kind):
    rnd = random.Random(seed)
    W, H = 1500, 2000
    bg = table(W, H, kind, rnd)
    cw, ch = 600, int(600 / rnd.choice([0.62, 0.66, 0.70, 0.75]))
    cv = cover(cw, ch, rnd)
    # A real camera: the book is a flat rectangle in 3D, turned and tilted, then projected.
    f = 0.78 * max(W, H)
    bw, bh = 1.0, ch / cw
    ax, ay, az = math.radians(rnd.uniform(-28, 28)), math.radians(rnd.uniform(-22, 22)), math.radians(rnd.uniform(-15, 15))
    dist = rnd.uniform(1.25, 2.1) * bh
    ox, oy = rnd.uniform(-0.15, 0.15) * bw, rnd.uniform(-0.15, 0.15) * bh

    def rotate(p):
        x, y, z = p
        y, z = y * math.cos(ax) - z * math.sin(ax), y * math.sin(ax) + z * math.cos(ax)
        x, z = x * math.cos(ay) + z * math.sin(ay), -x * math.sin(ay) + z * math.cos(ay)
        x, y = x * math.cos(az) - y * math.sin(az), x * math.sin(az) + y * math.cos(az)
        return x, y, z

    q = []
    for x, y in [(-bw / 2, -bh / 2), (bw / 2, -bh / 2), (bw / 2, bh / 2), (-bw / 2, bh / 2)]:
        X, Y, Z = rotate((x, y, 0.0))
        X, Y, Z = X + ox, Y + oy, Z + dist
        q.append((W / 2 + f * X / Z, H / 2 + f * Y / Z))
    # PIL perspective: coefficients mapping output -> input (cover)
    src = [(0, 0), (cw, 0), (cw, ch), (0, ch)]
    A, b = [], []
    for (X, Y), (x, y) in zip(q, src):
        A.append([X, Y, 1, 0, 0, 0, -x * X, -x * Y])
        b.append(x)
        A.append([0, 0, 0, X, Y, 1, -y * X, -y * Y])
        b.append(y)
    coef = solve8(A, b)
    warped = cv.transform((W, H), Image.PERSPECTIVE, tuple(coef), Image.BILINEAR)
    mask = Image.new("L", (cw, ch), 255).transform((W, H), Image.PERSPECTIVE, tuple(coef), Image.BILINEAR)
    shadow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shadow).polygon([(x + 18, y + 22) for x, y in q], fill=110)
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    bg = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), bg, shadow)
    im = Image.composite(warped, bg, mask)
    if seed % 3 == 0:  # a hand holding the bottom edge
        d = ImageDraw.Draw(im)
        hx, hy = (q[2][0] + q[3][0]) / 2 + rnd.uniform(-80, 80), (q[2][1] + q[3][1]) / 2
        d.ellipse([hx - 110, hy - 70, hx + 110, H + 50], fill=(222, 170, 140))
    im = im.filter(ImageFilter.GaussianBlur(1.2))
    out = io.BytesIO()
    im.save(out, "JPEG", quality=82)
    return out.getvalue(), q, cw / ch
