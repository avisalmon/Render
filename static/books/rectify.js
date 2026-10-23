/* A photographed book cover, straightened (Avi, 2026-10-23): "I always shoot
   at an angle and it doesn't fill the photo; find the book and square it, in
   proportion." All on the phone, nothing sent anywhere, nothing spent.

   1. A small copy of the photo (320px) and its edges, in colour, so a cover
      the same brightness as the table still shows its edge.
   2. Straight lines by a Hough vote, each edge pixel voting only near its
      own direction. The strongest few, split into "across" and "up".
   3. Every two across with every two up make a four-sided shape; the one
      whose four sides are best covered by edges, and big enough, is the book.
   4. The book's true width to height from the shape and the camera
      (Zhang and He's whiteboard formula), kept within a book's range.
   5. The full photo is warped into that rectangle.

   bkRectify(img) returns {canvas, found, quad, ratio}. When no book is found
   it returns the middle of the photo cut to 2 by 3, as before. */
(function () {
  "use strict";
  var WORK = 320, OUT = 1400, SRC_MAX = 2000, EDGE_T = 36;

  var toCanvas = function (img, max) {
    var w = img.naturalWidth || img.width, h = img.naturalHeight || img.height;
    var k = Math.min(1, max / Math.max(w, h));
    var c = document.createElement("canvas");
    c.width = Math.max(1, Math.round(w * k)); c.height = Math.max(1, Math.round(h * k));
    c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
    return c;
  };

  var middle = function (img) {
    var w = img.naturalWidth || img.width, h = img.naturalHeight || img.height, cw = w, ch = h;
    if (w / h > 2 / 3) cw = Math.round(h * 2 / 3); else ch = Math.round(w * 3 / 2);
    var scale = Math.min(1, OUT / Math.max(cw, ch));
    var c = document.createElement("canvas");
    c.width = Math.round(cw * scale); c.height = Math.round(ch * scale);
    c.getContext("2d").drawImage(img, (w - cw) / 2, (h - ch) / 2, cw, ch, 0, 0, c.width, c.height);
    return c;
  };

  // ---- 1. edges -------------------------------------------------------------------------
  var edges = function (c) {
    var w = c.width, h = c.height, d = c.getContext("2d").getImageData(0, 0, w, h).data;
    var ch = [new Float32Array(w * h), new Float32Array(w * h), new Float32Array(w * h)];
    for (var i = 0, p = 0; i < w * h; i++, p += 4) { ch[0][i] = d[p]; ch[1][i] = d[p + 1]; ch[2][i] = d[p + 2]; }
    var blur = function (a) {  // two box passes, 3 wide: a soft blur that keeps edges straight
      var t = new Float32Array(w * h), x, y;
      for (var pass = 0; pass < 2; pass++) {
        for (y = 0; y < h; y++) for (x = 0; x < w; x++) {
          var l = x > 0 ? x - 1 : x, r = x < w - 1 ? x + 1 : x;
          t[y * w + x] = (a[y * w + l] + a[y * w + x] + a[y * w + r]) / 3;
        }
        for (y = 0; y < h; y++) for (x = 0; x < w; x++) {
          var u = y > 0 ? y - 1 : y, dn = y < h - 1 ? y + 1 : y;
          a[y * w + x] = (t[u * w + x] + t[y * w + x] + t[dn * w + x]) / 3;
        }
      }
    };
    ch.forEach(blur);
    var mag = new Float32Array(w * h), gx = new Float32Array(w * h), gy = new Float32Array(w * h);
    for (var y = 1; y < h - 1; y++) for (var x = 1; x < w - 1; x++) {
      var i0 = y * w + x, best = 0, bx = 0, by = 0;
      for (var k = 0; k < 3; k++) {
        var a = ch[k];
        var sx = (a[i0 - w + 1] + 2 * a[i0 + 1] + a[i0 + w + 1]) - (a[i0 - w - 1] + 2 * a[i0 - 1] + a[i0 + w - 1]);
        var sy = (a[i0 + w - 1] + 2 * a[i0 + w] + a[i0 + w + 1]) - (a[i0 - w - 1] + 2 * a[i0 - w] + a[i0 - w + 1]);
        var m = sx * sx + sy * sy;
        if (m > best) { best = m; bx = sx; by = sy; }  // the channel with the strongest edge speaks
      }
      mag[i0] = Math.sqrt(best); gx[i0] = bx; gy[i0] = by;
    }
    // A low, fixed threshold: a pale cover on a pale table has a soft edge, and the
    // straight-line vote below ignores the scattered noise a low threshold lets in.
    var t = EDGE_T;
    return {w: w, h: h, mag: mag, gx: gx, gy: gy, t: t, rgb: ch};
  };

  // ---- 2. lines -------------------------------------------------------------------------
  var NT = 180;
  var lines = function (e) {
    var w = e.w, h = e.h, diag = Math.ceil(Math.hypot(w, h)), nr = 2 * diag + 1;
    var acc = new Float32Array(NT * nr), cos = [], sin = [];
    for (var t = 0; t < NT; t++) { cos[t] = Math.cos(t * Math.PI / NT); sin[t] = Math.sin(t * Math.PI / NT); }
    for (var y = 1; y < h - 1; y++) for (var x = 1; x < w - 1; x++) {
      var i = y * w + x;
      if (e.mag[i] < e.t) continue;
      var th = Math.atan2(e.gy[i], e.gx[i]);  // the normal of the edge
      // A step votes, a stroke hardly: four pixels to either side of a book's border
      // are cover and table; on both sides of a plank seam, a grain line or a printed
      // letter they are the same colour (Avi's wooden table).
      var gl = Math.hypot(e.gx[i], e.gy[i]), ux = e.gx[i] / gl, uy = e.gy[i] / gl;
      var xa = Math.min(w - 1, Math.max(0, Math.round(x + ux * 4))), ya = Math.min(h - 1, Math.max(0, Math.round(y + uy * 4)));
      var xb = Math.min(w - 1, Math.max(0, Math.round(x - ux * 4))), yb = Math.min(h - 1, Math.max(0, Math.round(y - uy * 4)));
      var step = 0;
      for (var k = 0; k < 3; k++) step += Math.abs(e.rgb[k][ya * w + xa] - e.rgb[k][yb * w + xb]);
      var vote = Math.min(1, step / 60);
      if (vote < 0.1) continue;
      if (th < 0) th += Math.PI;
      var c0 = Math.round(th * NT / Math.PI);
      for (var dt = -6; dt <= 6; dt++) {
        var tt = ((c0 + dt) % NT + NT) % NT;
        var r = Math.round(x * cos[tt] + y * sin[tt]) + diag;
        acc[tt * nr + r] += vote;
      }
    }
    var peaks = [];
    for (var n = 0; n < 60; n++) {
      var best = 0, bi = -1;
      for (var j = 0; j < acc.length; j++) if (acc[j] > best) { best = acc[j]; bi = j; }
      if (bi < 0 || best < Math.min(w, h) * 0.1) break;
      var bt = Math.floor(bi / nr), br = bi % nr;
      peaks.push({t: bt * Math.PI / NT, r: br - diag, votes: best});
      for (var u = -8; u <= 8; u++) for (var v = -10; v <= 10; v++) {  // clear the neighbourhood
        var t2 = bt + u, r2 = br + v;
        if (t2 < 0) { t2 += NT; r2 = 2 * diag - r2; } else if (t2 >= NT) { t2 -= NT; r2 = 2 * diag - r2; }
        if (r2 >= 0 && r2 < nr) acc[t2 * nr + r2] = 0;
      }
    }
    return peaks;
  };

  var meet = function (a, b) {
    var d = Math.cos(a.t) * Math.sin(b.t) - Math.sin(a.t) * Math.cos(b.t);
    if (Math.abs(d) < 1e-6) return null;
    return [(a.r * Math.sin(b.t) - b.r * Math.sin(a.t)) / d, (b.r * Math.cos(a.t) - a.r * Math.cos(b.t)) / d];
  };

  // ---- 3. the book among the shapes -----------------------------------------------------
  var BINS = 8;
  var support = function (e, p, q) {
    var n = 48, hit = 0;
    var th = Math.atan2(q[0] - p[0], -(q[1] - p[1])); if (th < 0) th += Math.PI;  // the side's normal
    var near = e.near[Math.round(th / Math.PI * BINS) % BINS];
    for (var s = 0; s < n; s++) {
      var f = (s + 0.5) / n, x = Math.round(p[0] + (q[0] - p[0]) * f), y = Math.round(p[1] + (q[1] - p[1]) * f);
      if (x >= 0 && y >= 0 && x < e.w && y < e.h && near[y * e.w + x]) hit++;
    }
    return hit / n;
  };
  // Across a book's edge the colour changes: inside is the cover, outside the table.
  // Across a plank seam or a line drawn on the cover it does not (Avi's wooden table).
  var contrast = function (e, p, q, c) {
    var n = 24, dx = q[0] - p[0], dy = q[1] - p[1], len = Math.hypot(dx, dy) || 1;
    var nx = -dy / len, ny = dx / len, mx = (p[0] + q[0]) / 2, my = (p[1] + q[1]) / 2;
    if ((c[0] - mx) * nx + (c[1] - my) * ny > 0) { nx = -nx; ny = -ny; }  // pointing out of the book
    // The mean colour of a band just inside against a band just outside, along the whole side.
    var sin = [0, 0, 0], sout = [0, 0, 0], nin = 0, nout = 0;
    for (var s = 0; s < n; s++) {
      var f = (s + 0.5) / n, x = p[0] + dx * f, y = p[1] + dy * f;
      for (var d = 3; d <= 8; d++) {
        var xi = Math.round(x - nx * d), yi = Math.round(y - ny * d), xo = Math.round(x + nx * d), yo = Math.round(y + ny * d);
        if (xi >= 0 && yi >= 0 && xi < e.w && yi < e.h) { for (var k = 0; k < 3; k++) sin[k] += e.rgb[k][yi * e.w + xi]; nin++; }
        if (xo >= 0 && yo >= 0 && xo < e.w && yo < e.h) { for (k = 0; k < 3; k++) sout[k] += e.rgb[k][yo * e.w + xo]; nout++; }
      }
    }
    if (nin < n || nout < n) return 20;  // a side on the photo's border: no outside to compare with
    var sum = 0;
    for (k = 0; k < 3; k++) sum += Math.abs(sin[k] / nin - sout[k] / nout);
    return sum;
  };
  var area = function (q) {
    var a = 0;
    for (var i = 0; i < 4; i++) { var p = q[i], r = q[(i + 1) % 4]; a += p[0] * r[1] - r[0] * p[1]; }
    return Math.abs(a) / 2;
  };
  var convex = function (q) {
    var sign = 0;
    for (var i = 0; i < 4; i++) {
      var a = q[i], b = q[(i + 1) % 4], c = q[(i + 2) % 4];
      var z = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]);
      if (Math.abs(z) < 1e-6) return false;
      if (!sign) sign = z > 0 ? 1 : -1; else if ((z > 0 ? 1 : -1) !== sign) return false;
    }
    return true;
  };
  var angleOk = function (q) {
    for (var i = 0; i < 4; i++) {
      var a = q[(i + 3) % 4], b = q[i], c = q[(i + 1) % 4];
      var v1 = [a[0] - b[0], a[1] - b[1]], v2 = [c[0] - b[0], c[1] - b[1]];
      var cs = (v1[0] * v2[0] + v1[1] * v2[1]) / (Math.hypot(v1[0], v1[1]) * Math.hypot(v2[0], v2[1]));
      if (Math.abs(cs) > 0.6) return false;  // corners between about 53 and 127 degrees
    }
    return true;
  };
  // Corners in order: top-left, top-right, bottom-right, bottom-left.
  var order = function (q) {
    var cx = 0, cy = 0;
    q.forEach(function (p) { cx += p[0] / 4; cy += p[1] / 4; });
    q = q.slice().sort(function (a, b) { return Math.atan2(a[1] - cy, a[0] - cx) - Math.atan2(b[1] - cy, b[0] - cx); });
    var k = 0, best = Infinity;
    q.forEach(function (p, i) { if (p[0] + p[1] < best) { best = p[0] + p[1]; k = i; } });
    return [q[k], q[(k + 1) % 4], q[(k + 2) % 4], q[(k + 3) % 4]];
  };

  var findBook = function (e) {
    var ls = lines(e);
    // At most four lines at nearly one angle: the planks of a table are many parallel
    // lines, and they must not crowd the book's own edges out of the list.
    var varied = function (g) {
      var seen = {}, out = [];
      g.forEach(function (l) {
        var key = Math.round(l.t / (Math.PI / 60));
        seen[key] = (seen[key] || 0) + 1;
        if (seen[key] <= 4 && out.length < 16) out.push(l);
      });
      return out;
    };
    var across = varied(ls.filter(function (l) { return Math.abs(Math.cos(l.t)) < Math.SQRT1_2; }));
    var up = varied(ls.filter(function (l) { return Math.abs(Math.cos(l.t)) >= Math.SQRT1_2; }));
    if (!e.near) {
      // Edge pixels by the way they run (8 directions), widened by two: "is there an edge
      // running this way near here" in one look. Wood grain runs across, so it never
      // holds up an upright side of a book.
      e.near = [];
      for (var k = 0; k < BINS; k++) e.near.push(new Uint8Array(e.w * e.h));
      for (var y = 0; y < e.h; y++) for (var x = 0; x < e.w; x++) {
        var i = y * e.w + x;
        if (e.mag[i] < e.t * 0.6) continue;
        var th = Math.atan2(e.gy[i], e.gx[i]); if (th < 0) th += Math.PI;
        var b0 = Math.round(th / Math.PI * BINS) % BINS;
        for (var db = -1; db <= 1; db++) {
          var map = e.near[(b0 + db + BINS) % BINS];
          for (var dy = -2; dy <= 2; dy++) for (var dx = -2; dx <= 2; dx++) {
            var xx = x + dx, yy = y + dy;
            if (xx >= 0 && yy >= 0 && xx < e.w && yy < e.h) map[yy * e.w + xx] = 1;
          }
        }
      }
    }
    var W = e.w, H = e.h, full = W * H, pad = 0.04 * Math.max(W, H);
    var judge = function (q) {
      if (q.some(function (p) { return !p || p[0] < -pad || p[1] < -pad || p[0] > W + pad || p[1] > H + pad; })) return null;
      q = order(q);
      if (!convex(q) || !angleOk(q)) return null;
      var af = area(q) / full;
      if (af < 0.05 || af > 0.995) return null;
      var c = [(q[0][0] + q[1][0] + q[2][0] + q[3][0]) / 4, (q[0][1] + q[1][1] + q[2][1] + q[3][1]) / 4];
      var s = [0, 1, 2, 3].map(function (i) {
        var a = q[i], b = q[(i + 1) % 4];
        return support(e, a, b) * Math.min(1, Math.max(0.05, contrast(e, a, b, c) / 30));
      });
      var mean = (s[0] + s[1] + s[2] + s[3]) / 4, low = Math.min.apply(null, s);
      if (mean < 0.45 || low < 0.2) return null;
      return {q: q, score: (0.6 * mean + 0.4 * low) * Math.pow(af, 0.3), mean: mean, low: low};
    };
    var pairs = function (g) {
      var out = [];
      for (var i = 0; i < g.length; i++) for (var j = i + 1; j < g.length; j++) {
        var da = Math.abs(g[i].t - g[j].t); da = Math.min(da, Math.PI - da);
        if (da < 0.6) out.push([g[i], g[j]]);
      }
      return out;
    };
    var found = [];
    pairs(across).forEach(function (A) {
      pairs(up).forEach(function (U) {
        var j = judge([meet(A[0], U[0]), meet(A[0], U[1]), meet(A[1], U[1]), meet(A[1], U[0])]);
        if (j) found.push(j);
      });
    });
    found.sort(function (x, y) { return y.score - x.score; });
    // The best few, each side fitted to its own edge pixels, judged again.
    var best = null;
    found.slice(0, 12).forEach(function (f) {
      var q = f.q;
      for (var round = 0; round < 2; round++) {
        var ls2 = [0, 1, 2, 3].map(function (i) { return refine(e, q[i], q[(i + 1) % 4]); });
        if (ls2.some(function (l) { return !l; })) break;
        q = [0, 1, 2, 3].map(function (i) { return cut(ls2[(i + 3) % 4], ls2[i]); });
        if (q.some(function (p) { return !p; })) { q = f.q; break; }
      }
      var j = judge(q) || f;
      if (!best || j.score > best.score) best = j;
    });
    return best;
  };

  // One side, fitted through the edge pixels along it whose edge runs the same way.
  var refine = function (e, a, b) {
    var dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy);
    if (len < 8) return null;
    var ux = dx / len, uy = dy / len, nx = -uy, ny = ux, pts = [];
    for (var s = len * 0.08; s < len * 0.92; s += 1) {
      var bx = a[0] + ux * s, by = a[1] + uy * s, top = 0, px = 0, py = 0;
      for (var o = -4; o <= 4; o++) {
        var x = Math.round(bx + nx * o), y = Math.round(by + ny * o);
        if (x < 1 || y < 1 || x >= e.w - 1 || y >= e.h - 1) continue;
        var i = y * e.w + x, m = e.mag[i];
        if (m < e.t * 0.6 || m <= top) continue;
        if (Math.abs(e.gx[i] * nx + e.gy[i] * ny) < 0.9 * Math.hypot(e.gx[i], e.gy[i])) continue;  // within ~25 degrees
        top = m; px = x; py = y;
      }
      if (top) pts.push([px, py, top]);
    }
    if (pts.length < len * 0.3) return null;
    var sw = 0, mx = 0, my = 0;
    pts.forEach(function (p) { sw += p[2]; mx += p[0] * p[2]; my += p[1] * p[2]; });
    mx /= sw; my /= sw;
    var sxx = 0, syy = 0, sxy = 0;
    pts.forEach(function (p) {
      var X = p[0] - mx, Y = p[1] - my;
      sxx += p[2] * X * X; syy += p[2] * Y * Y; sxy += p[2] * X * Y;
    });
    var th = 0.5 * Math.atan2(2 * sxy, sxx - syy), lx = -Math.sin(th), ly = Math.cos(th);
    return {nx: lx, ny: ly, c: lx * mx + ly * my};
  };
  var cut = function (l1, l2) {
    var d = l1.nx * l2.ny - l1.ny * l2.nx;
    if (Math.abs(d) < 1e-6) return null;
    return [(l1.c * l2.ny - l2.c * l1.ny) / d, (l1.nx * l2.c - l2.nx * l1.c) / d];
  };

  // ---- 4. its true proportion -----------------------------------------------------------
  var cross = function (a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; };
  var dot = function (a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; };
  var ratioOf = function (q, w, h) {
    // Zhang & He: m1 top-left, m2 top-right, m3 bottom-left, m4 bottom-right.
    var m1 = [q[0][0], q[0][1], 1], m2 = [q[1][0], q[1][1], 1], m3 = [q[3][0], q[3][1], 1], m4 = [q[2][0], q[2][1], 1];
    var u0 = w / 2, v0 = h / 2;
    var k2 = dot(cross(m1, m4), m3) / dot(cross(m2, m4), m3);
    var k3 = dot(cross(m1, m4), m2) / dot(cross(m3, m4), m2);
    var n2 = [k2 * m2[0] - m1[0], k2 * m2[1] - m1[1], k2 * m2[2] - m1[2]];
    var n3 = [k3 * m3[0] - m1[0], k3 * m3[1] - m1[1], k3 * m3[2] - m1[2]];
    var sides = function () {  // plain: the mean of opposite sides
      var d = function (a, b) { return Math.hypot(a[0] - b[0], a[1] - b[1]); };
      return (d(q[0], q[1]) + d(q[3], q[2])) / (d(q[0], q[3]) + d(q[1], q[2]));
    };
    var r = null;
    if (Math.abs(n2[2]) > 1e-9 && Math.abs(n3[2]) > 1e-9) {
      var f2 = -((n2[0] * n3[0] - (n2[0] * n3[2] + n2[2] * n3[0]) * u0 + n2[2] * n3[2] * u0 * u0) +
                 (n2[1] * n3[1] - (n2[1] * n3[2] + n2[2] * n3[1]) * v0 + n2[2] * n3[2] * v0 * v0)) / (n2[2] * n3[2]);
      var f = f2 > 0 ? Math.sqrt(f2) : 0;
      // A phone's lens: a focal length between about half and twice the photo's long side.
      if (f > 0.5 * Math.max(w, h) && f < 2.5 * Math.max(w, h)) {
        var g = function (n) {
          var a = (n[0] - u0 * n[2]) / f, b = (n[1] - v0 * n[2]) / f;
          return a * a + b * b + n[2] * n[2];
        };
        r = Math.sqrt(g(n2) / g(n3));
      }
    }
    if (!r || !isFinite(r)) r = sides();
    return r;
  };

  // ---- 5. the warp ----------------------------------------------------------------------
  var solve = function (A, b) {  // Gaussian elimination, 8 by 8
    var n = b.length;
    for (var i = 0; i < n; i++) {
      var p = i;
      for (var k = i + 1; k < n; k++) if (Math.abs(A[k][i]) > Math.abs(A[p][i])) p = k;
      var tA = A[i]; A[i] = A[p]; A[p] = tA; var tb = b[i]; b[i] = b[p]; b[p] = tb;
      for (k = i + 1; k < n; k++) {
        var m = A[k][i] / A[i][i];
        for (var j = i; j < n; j++) A[k][j] -= m * A[i][j];
        b[k] -= m * b[i];
      }
    }
    var x = new Array(n);
    for (i = n - 1; i >= 0; i--) {
      var s = b[i];
      for (j = i + 1; j < n; j++) s -= A[i][j] * x[j];
      x[i] = s / A[i][i];
    }
    return x;
  };
  var homography = function (from, to) {  // maps points of `from` onto `to`
    var A = [], b = [];
    for (var i = 0; i < 4; i++) {
      var x = from[i][0], y = from[i][1], X = to[i][0], Y = to[i][1];
      A.push([x, y, 1, 0, 0, 0, -x * X, -y * X]); b.push(X);
      A.push([0, 0, 0, x, y, 1, -x * Y, -y * Y]); b.push(Y);
    }
    var h = solve(A, b);
    return [h[0], h[1], h[2], h[3], h[4], h[5], h[6], h[7], 1];
  };
  var warp = function (src, quad, ratio) {
    var d = function (a, b) { return Math.hypot(a[0] - b[0], a[1] - b[1]); };
    var tall = Math.max(d(quad[0], quad[3]), d(quad[1], quad[2]));
    var H = Math.round(Math.min(OUT, Math.max(200, tall))), W = Math.max(1, Math.round(H * ratio));
    if (W > OUT) { H = Math.round(H * OUT / W); W = OUT; }
    var M = homography([[0, 0], [W - 1, 0], [W - 1, H - 1], [0, H - 1]], quad);
    var sw = src.width, sh = src.height, s = src.getContext("2d").getImageData(0, 0, sw, sh).data;
    var out = document.createElement("canvas");
    out.width = W; out.height = H;
    var octx = out.getContext("2d"), o = octx.createImageData(W, H), od = o.data;
    for (var y = 0; y < H; y++) for (var x = 0; x < W; x++) {
      var z = M[6] * x + M[7] * y + 1;
      var u = (M[0] * x + M[1] * y + M[2]) / z, v = (M[3] * x + M[4] * y + M[5]) / z;
      var x0 = Math.floor(u), y0 = Math.floor(v), fx = u - x0, fy = v - y0;
      if (x0 < 0) { x0 = 0; fx = 0; } else if (x0 >= sw - 1) { x0 = sw - 2; fx = 1; }
      if (y0 < 0) { y0 = 0; fy = 0; } else if (y0 >= sh - 1) { y0 = sh - 2; fy = 1; }
      var p00 = (y0 * sw + x0) * 4, p10 = p00 + 4, p01 = p00 + sw * 4, p11 = p01 + 4, q = (y * W + x) * 4;
      for (var c = 0; c < 3; c++) {
        od[q + c] = (s[p00 + c] * (1 - fx) + s[p10 + c] * fx) * (1 - fy) + (s[p01 + c] * (1 - fx) + s[p11 + c] * fx) * fy;
      }
      od[q + 3] = 255;
    }
    octx.putImageData(o, 0, 0);
    return out;
  };

  window.bkRectify = function (img) {
    try {
      var small = toCanvas(img, WORK);
      var e = edges(small);
      var book = findBook(e);
      if (book) {
        var src = toCanvas(img, SRC_MAX), k = src.width / small.width;
        var quad = book.q.map(function (p) {
          return [Math.min(src.width - 1, Math.max(0, p[0] * k)), Math.min(src.height - 1, Math.max(0, p[1] * k))];
        });
        var ratio = Math.min(1.1, Math.max(0.45, ratioOf(book.q, small.width, small.height)));
        return {canvas: warp(src, quad, ratio), found: true, quad: quad, ratio: ratio, score: book.score};
      }
    } catch (err) { /* any surprise: the plain cut below */ }
    return {canvas: middle(img), found: false, quad: null, ratio: 2 / 3};
  };
  // For the tests: what the detector saw.
  window.bkRectify.debug = function (img) {
    var small = toCanvas(img, WORK), e = edges(small);
    var best = findBook(e), sides = function (q) {
      if (!q) return null;
      var c = [(q[0][0] + q[1][0] + q[2][0] + q[3][0]) / 4, (q[0][1] + q[1][1] + q[2][1] + q[3][1]) / 4];
      return [0, 1, 2, 3].map(function (i) {
        var a = q[i], b = q[(i + 1) % 4];
        return [Math.round(support(e, a, b) * 100) / 100, Math.round(contrast(e, a, b, c))];
      });
    };
    return {w: e.w, h: e.h, t: e.t, lines: lines(e), best: best, bestSides: sides(best && best.q),
            trueSides: sides(window.__trueQuad && window.__trueQuad.map(function (p) { return [p[0] * e.w, p[1] * e.h]; }))};
  };
})();
