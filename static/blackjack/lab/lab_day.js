/* The lab's day viewer (REQ-B.11.28): one day at the casino, hand by hand, with
   the points where winnings were frozen, and a zoom.

   Everything drawn here was worked out in this page a moment ago from the run's
   seed; nothing is stored and nothing is sent anywhere. Closing the page, or
   choosing another day, throws it away.

   The pure helpers at the top (the window arithmetic and the envelope) are
   exported so a test can hold them to account without a browser. */

(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory(null);
  else root.LabDay = factory(root.LabCharts);
})(typeof self !== "undefined" ? self : this, function (Charts) {
  "use strict";

  var W = 360, H = 230, HB = 74, PAD = { l: 52, r: 10, t: 14, b: 22 };

  /* ---------- the window: which hands are on screen ---------- */

  function minSpan(n) { return Math.min(n, 10); }

  /* Keep a window inside 0..n and no narrower than minSpan(n). */
  function clampWindow(a, b, n) {
    var span = Math.max(minSpan(n), b - a);
    span = Math.min(span, n);
    if (a < 0) a = 0;
    if (a + span > n) a = n - span;
    if (a < 0) a = 0;
    return [a, a + span];
  }

  /* Zoom by `factor` (>1 shows more hands) keeping the hand at `focus` still. */
  function zoomWindow(a, b, n, factor, focus) {
    var span = (b - a) * factor;
    var ratio = b > a ? (focus - a) / (b - a) : 0.5;
    var na = focus - ratio * span;
    return clampWindow(na, na + span, n);
  }

  function panWindow(a, b, n, delta) { return clampWindow(a + delta, b + delta, n); }

  /* Per column of `columns`, the smallest and largest of values[a..b]. */
  function envelope(values, a, b, columns) {
    var from = Math.max(0, Math.floor(a)), to = Math.min(values.length - 1, Math.ceil(b));
    var lo = [], hi = [], i, c;
    for (c = 0; c < columns; c++) { lo.push(Infinity); hi.push(-Infinity); }
    var span = Math.max(1e-9, b - a);
    for (i = from; i <= to; i++) {
      c = Math.min(columns - 1, Math.max(0, Math.floor((i - a) / span * columns)));
      if (values[i] < lo[c]) lo[c] = values[i];
      if (values[i] > hi[c]) hi[c] = values[i];
    }
    return { lo: lo, hi: hi };
  }

  function rangeOf(series, a, b) {
    var lo = Infinity, hi = -Infinity;
    series.forEach(function (values) {
      if (!values) return;
      var from = Math.max(0, Math.floor(a)), to = Math.min(values.length - 1, Math.ceil(b));
      for (var i = from; i <= to; i++) {
        if (values[i] < lo) lo = values[i];
        if (values[i] > hi) hi = values[i];
      }
    });
    if (!isFinite(lo)) { lo = 0; hi = 1; }
    var pad = (hi - lo) * 0.08 || 1;
    // Money is never below nothing, so the axis does not go there either.
    return [lo >= 0 ? Math.max(0, lo - pad) : lo - pad, hi + pad];
  }

  function exported() {
    return { clampWindow: clampWindow, zoomWindow: zoomWindow, panWindow: panWindow, envelope: envelope, rangeOf: rangeOf, minSpan: minSpan };
  }
  if (!Charts) return exported();

  /* ---------- drawing ---------- */

  var fmt = Charts.fmt, esc = Charts.esc;

  function add(a, b) { var out = new Array(a.length), i; for (i = 0; i < a.length; i++) out[i] = a[i] + b[i]; return out; }

  function mount(box, data) {
    var trace = data.trace, result = data.result;
    var n = result.rounds;
    var total = add(trace.playing, trace.frozen);
    var classic = data.classicTrace ? add(data.classicTrace.playing, data.classicTrace.frozen) : null;
    var win = [0, Math.max(n, 1)];
    var pending = false, hover = null;

    box.innerHTML =
      '<p class="bj-day-readout" id="dayReadout" aria-live="polite"></p>' +
      '<div class="bj-day-plot" id="dayPlot" tabindex="0" role="group" aria-label="גרף היום. גרירה זזה, גלגלת או צביטה מקרבות, חצים ו-פלוס ומינוס במקלדת."></div>' +
      '<div class="bj-day-plot bj-day-plot-bets" id="dayBets"></div>' +
      '<div class="bj-day-tools">' +
      '<button type="button" class="bj-btn bj-btn-small" id="dayIn" aria-label="זום פנימה">+</button>' +
      '<button type="button" class="bj-btn bj-btn-small" id="dayOut" aria-label="זום החוצה">&minus;</button>' +
      '<button type="button" class="bj-btn bj-btn-small bj-btn-quiet" id="dayReset">כל היום</button>' +
      '<span class="bj-muted bj-small" id="dayRange"></span></div>' +
      '<ul class="bj-day-freezes" id="dayFreezes"></ul>';

    var plot = box.querySelector("#dayPlot"), bets = box.querySelector("#dayBets");
    var readout = box.querySelector("#dayReadout"), rangeLabel = box.querySelector("#dayRange");

    function xOf(i) { return PAD.l + (i - win[0]) / (win[1] - win[0]) * (W - PAD.l - PAD.r); }
    function indexAt(clientX) {
      var r = plot.getBoundingClientRect();
      var x = (clientX - r.left) / r.width * W;
      return win[0] + (x - PAD.l) / (W - PAD.l - PAD.r) * (win[1] - win[0]);
    }

    function pathFor(values, y) {
      var a = win[0], b = win[1], d = "", i;
      var cols = W - PAD.l - PAD.r;
      if (b - a <= cols) {
        var from = Math.max(0, Math.floor(a)), to = Math.min(values.length - 1, Math.ceil(b));
        for (i = from; i <= to; i++) d += (d ? "L" : "M") + xOf(i).toFixed(1) + " " + y(values[i]).toFixed(1);
        return d;
      }
      var env = envelope(values, a, b, cols);
      for (i = 0; i < cols; i++) {
        if (env.lo[i] === Infinity) continue;
        var x = (PAD.l + i + 0.5).toFixed(1);
        d += "M" + x + " " + y(env.lo[i]).toFixed(1) + "L" + x + " " + y(env.hi[i]).toFixed(1);
      }
      return d;
    }

    function drawMain() {
      var series = [total, trace.playing, trace.frozen];
      if (classic) series.push(classic);
      var r = rangeOf(series, win[0], win[1]);
      var lo = r[0], hi = r[1];
      var y = function (v) { return H - PAD.b - (v - lo) / (hi - lo) * (H - PAD.b - PAD.t); };
      var out = "", i;
      for (i = 0; i <= 4; i++) {
        var v = lo + (hi - lo) * i / 4;
        out += '<line class="bj-lab-grid" x1="' + PAD.l + '" x2="' + (W - PAD.r) + '" y1="' + y(v).toFixed(1) + '" y2="' + y(v).toFixed(1) + '"/>' +
          '<text class="bj-lab-tick" x="' + (PAD.l - 6) + '" y="' + (y(v) + 3).toFixed(1) + '" text-anchor="end">' + fmt(v) + "</text>";
      }
      var startLevel = trace.playing[0];
      if (startLevel >= lo && startLevel <= hi) {
        out += '<line class="bj-lab-mark" x1="' + PAD.l + '" x2="' + (W - PAD.r) + '" y1="' + y(startLevel).toFixed(1) + '" y2="' + y(startLevel).toFixed(1) + '"/>';
      }
      if (classic) out += '<path class="bj-lab-line bj-lab-line-classic" d="' + pathFor(classic, y) + '"/>';
      out += '<path class="bj-day-frozen" d="' + pathFor(trace.frozen, y) + '"/>';
      out += '<path class="bj-day-playing" d="' + pathFor(trace.playing, y) + '"/>';
      out += '<path class="bj-lab-line bj-lab-line-run" d="' + pathFor(total, y) + '"/>';

      // The points where winnings were set aside.
      var visible = trace.freezes.filter(function (f) { return f.round >= win[0] - 1 && f.round <= win[1] + 1; });
      var lastLabel = -1000, row = 0;
      visible.forEach(function (f) {
        var x = xOf(f.round);
        if (x < PAD.l - 1 || x > W - PAD.r + 1) return;
        out += '<line class="bj-day-freeze-line" x1="' + x.toFixed(1) + '" x2="' + x.toFixed(1) + '" y1="' + PAD.t + '" y2="' + (H - PAD.b) + '"/>';
        out += '<circle class="bj-day-freeze-dot" cx="' + x.toFixed(1) + '" cy="' + y(total[f.round]).toFixed(1) + '" r="4.5"/>';
        // A label only where there is room for it; zoom in to read the rest.
        if (x - lastLabel >= 64) {
          out += '<text class="bj-day-freeze-text" x="' + x.toFixed(1) + '" y="' + (PAD.t + 9 + (row++ % 2) * 11) + '" text-anchor="middle">הוקפאו ' + fmt(f.amount) + "</text>";
          lastLabel = x;
        }
      });

      if (result.ended !== "limit" && n >= win[0] && n <= win[1]) {
        var ex = xOf(n);
        out += '<line class="bj-day-end-line" x1="' + ex.toFixed(1) + '" x2="' + ex.toFixed(1) + '" y1="' + PAD.t + '" y2="' + (H - PAD.b) + '"/>' +
          '<text class="bj-day-end-text" x="' + Math.min(W - PAD.r - 2, ex).toFixed(1) + '" y="' + (H - PAD.b - 6) + '" text-anchor="end">' +
          (result.ended === "bust" ? "נגמר הכסף" : "הפסקה לפי המדיניות") + "</text>";
      }

      if (hover != null && hover >= win[0] && hover <= win[1]) {
        var hx = xOf(hover);
        out += '<line class="bj-day-cursor" x1="' + hx.toFixed(1) + '" x2="' + hx.toFixed(1) + '" y1="' + PAD.t + '" y2="' + (H - PAD.b) + '"/>' +
          '<circle class="bj-day-cursor-dot" cx="' + hx.toFixed(1) + '" cy="' + y(total[hover]).toFixed(1) + '" r="4"/>';
      }
      out += '<text class="bj-lab-tick" x="' + PAD.l + '" y="' + (H - 6) + '" text-anchor="start">' + fmt(Math.round(win[0])) + "</text>" +
        '<text class="bj-lab-tick" x="' + (W - PAD.r) + '" y="' + (H - 6) + '" text-anchor="end">יד ' + fmt(Math.round(win[1])) + "</text>";
      plot.innerHTML = '<svg class="bj-lab-svg" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="הכסף בכל יד של היום">' + out + "</svg>";
    }

    function drawBets() {
      var a = Math.max(1, Math.floor(win[0]) + 1), b = Math.min(n, Math.ceil(win[1]));
      var out = "", top = 1, i;
      for (i = a; i <= b; i++) if (trace.bets[i - 1] > top) top = trace.bets[i - 1];
      var y = function (v) { return HB - 14 - v / top * (HB - 24); };
      var cols = W - PAD.l - PAD.r, span = win[1] - win[0];
      out += '<text class="bj-lab-tick" x="' + (PAD.l - 6) + '" y="' + (y(top) + 3).toFixed(1) + '" text-anchor="end">' + fmt(top) + "</text>" +
        '<text class="bj-lab-tick" x="' + (PAD.l - 6) + '" y="' + (HB - 12) + '" text-anchor="end">0</text>' +
        '<text class="bj-lab-tick" x="' + (W - PAD.r) + '" y="' + (HB - 2) + '" text-anchor="end">הימור בכל יד</text>';
      if (span <= 300) {
        var bw = Math.max(1.2, cols / Math.max(span, 1) * 0.78);
        for (i = a; i <= b; i++) {
          var net = trace.nets[i - 1], cls = net > 0 ? "bj-day-bar-win" : net < 0 ? "bj-day-bar-loss" : "bj-day-bar-push";
          var x = xOf(i - 0.5) - bw / 2;
          out += '<rect class="' + cls + '" x="' + x.toFixed(1) + '" y="' + y(trace.bets[i - 1]).toFixed(1) + '" width="' + bw.toFixed(1) +
            '" height="' + (HB - 14 - y(trace.bets[i - 1])).toFixed(1) + '"/>';
        }
      } else {
        var env = envelope(trace.bets, a - 1, b - 1, cols);
        for (i = 0; i < cols; i++) {
          if (env.hi[i] === -Infinity) continue;
          out += '<rect class="bj-day-bar-push" x="' + (PAD.l + i) + '" y="' + y(env.hi[i]).toFixed(1) + '" width="1" height="' + (HB - 14 - y(env.hi[i])).toFixed(1) + '"/>';
        }
      }
      bets.innerHTML = '<svg class="bj-lab-svg" viewBox="0 0 ' + W + " " + HB + '" role="img" aria-label="ההימור בכל יד">' + out + "</svg>";
    }

    function describe(i) {
      i = Math.max(0, Math.min(n, Math.round(i)));
      if (i === 0) return "לפני היד הראשונה · משחק " + fmt(trace.playing[0]) + " · מוקפא 0";
      var net = trace.nets[i - 1];
      var what = net > 0 ? "ניצחון +" + fmt(net) : net < 0 ? "הפסד " + fmt(net) : "תיקו";
      return "יד " + fmt(i) + " · הימור " + fmt(trace.bets[i - 1]) + " · " + what +
        " · משחק " + fmt(trace.playing[i]) + " · מוקפא " + fmt(trace.frozen[i]) + " · ביחד " + fmt(total[i]);
    }

    function draw() {
      pending = false;
      drawMain();
      drawBets();
      rangeLabel.textContent = "ידיים " + fmt(Math.round(win[0])) + " עד " + fmt(Math.round(win[1])) + " מתוך " + fmt(n);
      plot.setAttribute("data-from", String(Math.round(win[0])));
      plot.setAttribute("data-to", String(Math.round(win[1])));
      readout.textContent = hover != null ? describe(hover) : readout.getAttribute("data-idle");
    }
    function later() { if (!pending) { pending = true; requestAnimationFrame(draw); } }

    var idle = n === 0
      ? "היום הזה נגמר לפני שהתחיל."
      : "נגעו בגרף כדי לראות יד, גררו כדי לזוז, צבטו או השתמשו ב-פלוס כדי להתקרב.";
    readout.setAttribute("data-idle", idle);

    function set(w) { win = w; later(); }
    function zoom(factor, focus) { set(zoomWindow(win[0], win[1], Math.max(n, 1), factor, focus == null ? (win[0] + win[1]) / 2 : focus)); }

    box.querySelector("#dayIn").addEventListener("click", function () { zoom(0.5); });
    box.querySelector("#dayOut").addEventListener("click", function () { zoom(2); });
    box.querySelector("#dayReset").addEventListener("click", function () { set([0, Math.max(n, 1)]); });

    // Freeze points, as a list too: tap one to go and look at it.
    var list = box.querySelector("#dayFreezes");
    if (!trace.freezes.length) {
      var none = document.createElement("li");
      none.className = "bj-muted bj-small";
      none.textContent = "ביום הזה לא הוקפא כסף.";
      list.appendChild(none);
    }
    trace.freezes.forEach(function (f) {
      var li = document.createElement("li");
      var b = document.createElement("button");
      b.type = "button"; b.className = "bj-day-freeze-go";
      b.textContent = "יד " + fmt(f.round) + ": הוקפאו " + fmt(f.amount) + " (מוקפא עד עכשיו " + fmt(f.frozen) + ")";
      b.addEventListener("click", function () {
        var span = Math.max(minSpan(n), Math.min(n, 40));
        hover = f.round;
        set(clampWindow(f.round - span / 2, f.round + span / 2, Math.max(n, 1)));
      });
      li.appendChild(b);
      list.appendChild(li);
    });

    // Gestures: drag to move, pinch or wheel to zoom, tap to read a hand.
    var pointers = {}, last = null, moved = false;
    plot.addEventListener("pointerdown", function (e) {
      pointers[e.pointerId] = { x: e.clientX, y: e.clientY };
      try { plot.setPointerCapture(e.pointerId); } catch (err) { /* not needed */ }
      moved = false;
      last = null;
    });
    plot.addEventListener("pointermove", function (e) {
      var ids = Object.keys(pointers);
      if (!pointers[e.pointerId]) {
        if (e.pointerType === "mouse") { hover = Math.max(0, Math.min(n, Math.round(indexAt(e.clientX)))); later(); }
        return;
      }
      var p = pointers[e.pointerId];
      if (ids.length === 2) {
        var other = pointers[ids.filter(function (k) { return String(k) !== String(e.pointerId); })[0]];
        var before = Math.abs(p.x - other.x) || 1;
        p.x = e.clientX; p.y = e.clientY;
        var after = Math.abs(p.x - other.x) || 1;
        zoom(before / after, indexAt((p.x + other.x) / 2));
        moved = true;
        return;
      }
      var dx = e.clientX - p.x;
      if (Math.abs(dx) > 3) moved = true;
      p.x = e.clientX; p.y = e.clientY;
      if (moved) {
        var r = plot.getBoundingClientRect();
        var perPx = (win[1] - win[0]) / ((W - PAD.l - PAD.r) * r.width / W);
        set(panWindow(win[0], win[1], Math.max(n, 1), -dx * perPx));
      }
    });
    function lift(e) {
      if (pointers[e.pointerId] && !moved) {
        hover = Math.max(0, Math.min(n, Math.round(indexAt(e.clientX))));
        later();
      }
      delete pointers[e.pointerId];
    }
    plot.addEventListener("pointerup", lift);
    plot.addEventListener("pointercancel", function (e) { delete pointers[e.pointerId]; });
    plot.addEventListener("pointerleave", function (e) { if (e.pointerType === "mouse" && !pointers[e.pointerId]) { hover = null; later(); } });
    plot.addEventListener("wheel", function (e) {
      e.preventDefault();
      zoom(e.deltaY > 0 ? 1.25 : 0.8, indexAt(e.clientX));
    }, { passive: false });
    plot.addEventListener("dblclick", function () { set([0, Math.max(n, 1)]); });
    plot.addEventListener("keydown", function (e) {
      var span = win[1] - win[0];
      if (e.key === "+" || e.key === "=") zoom(0.5);
      else if (e.key === "-" || e.key === "_") zoom(2);
      else if (e.key === "0") set([0, Math.max(n, 1)]);
      else if (e.key === "ArrowLeft") set(panWindow(win[0], win[1], Math.max(n, 1), -span / 5));
      else if (e.key === "ArrowRight") set(panWindow(win[0], win[1], Math.max(n, 1), span / 5));
      else return;
      e.preventDefault();
    });

    draw();
    return {
      window: function () { return win.slice(); },
      zoom: zoom,
      reset: function () { set([0, Math.max(n, 1)]); }
    };
  }

  var out = exported();
  out.mount = mount;
  return out;
});
