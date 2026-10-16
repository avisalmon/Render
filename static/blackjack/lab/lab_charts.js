/* The strategy lab's graphs, as SVG markup (REQ-B.11.6).

   Pure functions that turn numbers into a string, so the live result and a
   saved run are drawn by the same code and cannot drift apart. Every graph
   prints the numbers it draws: the end of each line, and the range of each
   axis, are text on the graph and not only shape. */

(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.LabCharts = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var W = 360, H = 190, PAD = { l: 52, r: 10, t: 12, b: 26 };

  function fmt(n) {
    return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function scale(lo, hi, from, to) {
    var span = hi - lo || 1;
    return function (v) { return from + (v - lo) / span * (to - from); };
  }

  function niceRange(values) {
    var lo = Infinity, hi = -Infinity;
    values.forEach(function (v) { if (v < lo) lo = v; if (v > hi) hi = v; });
    if (!isFinite(lo)) { lo = 0; hi = 1; }
    var pad = (hi - lo) * 0.06 || 1;
    return [lo - pad, hi + pad];
  }

  function frame(label, inner) {
    return '<svg class="bj-lab-svg" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="' + esc(label) + '">' + inner + "</svg>";
  }

  function axisY(y, lo, hi) {
    var out = "", ticks = 4, i;
    for (i = 0; i <= ticks; i++) {
      var v = lo + (hi - lo) * i / ticks;
      var py = y(v);
      out += '<line class="bj-lab-grid" x1="' + PAD.l + '" x2="' + (W - PAD.r) + '" y1="' + py.toFixed(1) + '" y2="' + py.toFixed(1) + '"/>';
      out += '<text class="bj-lab-tick" x="' + (PAD.l - 6) + '" y="' + (py + 3).toFixed(1) + '" text-anchor="end">' + fmt(v) + "</text>";
    }
    return out;
  }

  function path(values, x, y) {
    var d = "";
    values.forEach(function (v, i) {
      d += (i ? "L" : "M") + x(i).toFixed(1) + " " + y(v).toFixed(1);
    });
    return d;
  }

  /* series: [{values: [...], cls: "run"|"classic"}], mark: a level to draw as a
     dashed line (the starting money), xEnd: the label at the right edge. */
  function lineChart(opts) {
    var all = [];
    opts.series.forEach(function (s) { all = all.concat(s.values); });
    if (opts.mark != null) all.push(opts.mark);
    var range = niceRange(all), lo = range[0], hi = range[1];
    var n = Math.max.apply(null, opts.series.map(function (s) { return s.values.length; }));
    var x = scale(0, Math.max(1, n - 1), PAD.l, W - PAD.r);
    var y = scale(lo, hi, H - PAD.b, PAD.t);
    var out = axisY(y, lo, hi);
    if (opts.mark != null) {
      out += '<line class="bj-lab-mark" x1="' + PAD.l + '" x2="' + (W - PAD.r) + '" y1="' + y(opts.mark).toFixed(1) + '" y2="' + y(opts.mark).toFixed(1) + '"/>';
    }
    opts.series.forEach(function (s) {
      var cls = s.cls === "day" ? "bj-lab-day" : "bj-lab-line bj-lab-line-" + s.cls;
      out += '<path class="' + cls + '" d="' + path(s.values, x, y) + '"/>';
    });
    out += '<text class="bj-lab-tick" x="' + PAD.l + '" y="' + (H - 8) + '" text-anchor="start">0</text>';
    out += '<text class="bj-lab-tick" x="' + (W - PAD.r) + '" y="' + (H - 8) + '" text-anchor="end">' + esc(opts.xEnd || "") + "</text>";
    return frame(opts.label, out);
  }

  /* counts and classicCounts share lo..hi; start draws a vertical line. */
  function histogram(opts) {
    var h = opts.hist, bins = h.counts.length;
    var top = Math.max.apply(null, h.counts.concat(h.classicCounts, [1]));
    var x = scale(0, bins, PAD.l, W - PAD.r);
    var y = scale(0, top, H - PAD.b, PAD.t);
    var bw = (W - PAD.l - PAD.r) / bins, out = "", i;
    out += axisY(y, 0, top);
    for (i = 0; i < bins; i++) {
      if (opts.showClassic && h.classicCounts[i]) {
        out += '<rect class="bj-lab-bar-classic" x="' + x(i).toFixed(1) + '" y="' + y(h.classicCounts[i]).toFixed(1) +
          '" width="' + Math.max(1, bw - 1).toFixed(1) + '" height="' + (H - PAD.b - y(h.classicCounts[i])).toFixed(1) + '"/>';
      }
      if (h.counts[i]) {
        out += '<rect class="bj-lab-bar" x="' + (x(i) + bw * 0.18).toFixed(1) + '" y="' + y(h.counts[i]).toFixed(1) +
          '" width="' + Math.max(1, bw * 0.64).toFixed(1) + '" height="' + (H - PAD.b - y(h.counts[i])).toFixed(1) + '"/>';
      }
    }
    if (opts.mark != null && h.hi > h.lo) {
      var mx = PAD.l + (opts.mark - h.lo) / (h.hi - h.lo) * (W - PAD.l - PAD.r);
      if (mx >= PAD.l && mx <= W - PAD.r) {
        out += '<line class="bj-lab-mark" x1="' + mx.toFixed(1) + '" x2="' + mx.toFixed(1) + '" y1="' + PAD.t + '" y2="' + (H - PAD.b) + '"/>';
      }
    }
    out += '<text class="bj-lab-tick" x="' + PAD.l + '" y="' + (H - 8) + '" text-anchor="start">' + fmt(h.lo) + "</text>";
    out += '<text class="bj-lab-tick" x="' + (W - PAD.r) + '" y="' + (H - 8) + '" text-anchor="end">' + fmt(h.hi) + "</text>";
    return frame(opts.label, out);
  }

  /* ---- a finished run, as words, tiles and graphs. The live result and a
     saved run are shown by these same functions. ---- */

  function tile(title, value, note) {
    return '<div class="bj-lab-tile"><span class="bj-muted bj-small">' + esc(title) + "</span>" +
      '<strong class="bj-lab-big">' + esc(value) + "</strong>" +
      (note ? '<span class="bj-muted bj-small">' + esc(note) + "</span>" : "") + "</div>";
  }

  function pct(a, b) { return b ? Math.round(100 * a / b) : 0; }

  function baseName(s) { return s.chart === "calculated" ? "הטבלה המחושבת" : "הטבלה הקלאסית"; }

  function daysTop(s) {
    var changedLine = s.changed
      ? "לעומת " + baseName(s) + " על אותם קלפים בדיוק, השינוי שלכם עזר ב-" + s.helped + " ימים והזיק ב-" + s.hurt + "."
      : "לא שיניתם את הטבלה, ולכן הקו של " + baseName(s) + " זהה לשלכם.";
    var out = '<h2 class="bj-lab-h2">התוצאה</h2>';
    out += '<p class="bj-lab-sentence">ב-' + s.ahead + " מתוך " + s.days + " ימים (" + pct(s.ahead, s.days) +
      "%) חזרתם הביתה עם יותר ממה שהגעתם איתו. " + esc(changedLine) + "</p>";
    out += '<div class="bj-lab-tiles">';
    out += tile("ימים ברווח", s.ahead + " מתוך " + s.days, s.changed ? "בסיס: " + s.classicAhead : "");
    out += tile("תוצאה ממוצעת ליום", fmt(s.avg), "התחלתם עם " + fmt(s.start) + (s.changed ? " · בסיס: " + fmt(s.classicAvg) : ""));
    out += tile("היום הכי טוב", fmt(s.best), "הכי גרוע: " + fmt(s.worst));
    out += tile("ימים שבהם נגמר הכסף", s.bust + " מתוך " + s.days, s.changed ? "בסיס: " + s.classicBust : "");
    out += tile("ידיים עד שנגמר הכסף", fmt(s.medianRounds), "החציון" + (s.changed ? " · בסיס: " + fmt(s.classicMedianRounds) : ""));
    out += tile("כסף מוקפא בממוצע", fmt(s.frozenAvg), s.changed ? "בסיס: " + fmt(s.classicFrozenAvg) : "");
    out += "</div>";
    if (s.overrideFallbacks) {
      out += '<p class="bj-muted bj-small">שינוי שהשולחן לא מאפשר באותו רגע שוחק כמו שהטבלה הקלאסית עושה במקרה כזה. זה קרה ' +
        fmt(s.overrideFallbacks) + " פעמים.</p>";
    }
    return out;
  }

  function trendFigure(s) {
    var series = [{ values: s.curve, cls: "run" }];
    if (s.changed) series.unshift({ values: s.classicCurve, cls: "classic" });
    return '<figure class="bj-lab-fig"><figcaption>הכסף הכולל לאורך היום, בממוצע (משחק ומוקפא ביחד)</figcaption>' +
      lineChart({ series: series, mark: s.start, xEnd: fmt(s.handsPerDay) + " ידיים", label: "ממוצע הכסף הכולל לפי מספר הידיים" }) +
      '<p class="bj-lab-legend"><span class="bj-lab-key bj-lab-key-run"></span> הריצה שלכם' +
      (s.changed ? ' <span class="bj-lab-key bj-lab-key-classic"></span> ' + baseName(s) : "") +
      ' <span class="bj-lab-key bj-lab-key-mark"></span> הכסף שהתחלתם איתו</p></figure>';
  }

  function daysFigure(s, curves) {
    return '<figure class="bj-lab-fig"><figcaption>כל יום בקו משלו</figcaption>' +
      lineChart({
        series: curves.slice(0, 120).map(function (c) { return { values: c, cls: "day" }; }),
        mark: s.start, xEnd: fmt(s.handsPerDay) + " ידיים", label: "הכסף הכולל בכל יום"
      }) + "</figure>";
  }

  function histFigure(s) {
    return '<figure class="bj-lab-fig"><figcaption>איך הסתיימו הימים</figcaption>' +
      histogram({ hist: s.hist, mark: s.start, showClassic: s.changed, label: "התפלגות התוצאות בסוף היום" }) +
      "</figure>";
  }

  function score(sc) {
    return Math.round(sc.ahead * 100) + "% ימים ברווח · ממוצע " + fmt(sc.avg) + " · " + fmt(sc.survive) + " ידיים";
  }

  function policyLine(p) {
    return "סולם: " + p.ladder.join(", ") + " · הקפאה: " + (p.freeze.length ? p.freeze.join(", ") : "אין");
  }

  function searchBody(r) {
    var html = '<h2 class="bj-lab-h2">מה נמצא</h2>';
    html += '<p class="bj-lab-sentence">' + (r.improved
      ? "נוסו " + fmt(r.tries) + " מדיניות. הטובה ביותר שנמצאה מוצגת למטה, עם הציון שלה על קלפים שהחיפוש לא ראה."
      : "נוסו " + fmt(r.tries) + " מדיניות ואף אחת לא ניצחה את המדיניות שלכם על הקלפים שהחיפוש אימן עליהם.") + "</p>";
    html += '<div class="bj-lab-tiles">';
    html += tile("המדיניות שלכם", score(r.baseline.holdout), r.baseline.policy ? policyLine(r.baseline.policy) : "");
    html += tile(r.improved ? "הטובה ביותר שנמצאה" : "אותה מדיניות", score(r.best.holdout), policyLine(r.best.policy));
    html += tile("על קלפים שהחיפוש אימן עליהם", score(r.best.train), "במדיניות שלכם: " + score(r.baseline.train));
    html += "</div>";
    html += '<p class="bj-muted bj-small">המספר שחשוב הוא של הקלפים החדשים. אם הוא נמוך בהרבה מזה של האימון, המדיניות פשוט התאימה את עצמה למזל של הקלפים שאימנו עליה.</p>';
    html += '<p class="bj-muted bj-small">שום מדיניות לא משנה את היתרון של הקזינו על כל יד. מה שמשתנה הוא הסיכוי לחזור עם רווח מול גודל ההפסד כשזה לא עובד.</p>';
    return html;
  }

  return {
    fmt: fmt, esc: esc, lineChart: lineChart, histogram: histogram,
    tile: tile, daysTop: daysTop, trendFigure: trendFigure, daysFigure: daysFigure,
    histFigure: histFigure, searchBody: searchBody, policyLine: policyLine
  };
});
