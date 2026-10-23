/* Fireworks and confetti on a canvas, in the site's own colours. Used by
   the finished book (finish.js) and by the five minutes that earn the day
   on the reading screen (Avi, 2026-10-23). Nothing moves for people who
   asked for less motion. */
(function () {
  "use strict";
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  window.bkSky = function (canvas) {
    var ctx = canvas && canvas.getContext && canvas.getContext("2d");
    var raf = 0, parts = [], startedAt = 0, lastBurst = 0, colors = [], opts = {};

    var palette = function () {
      var css = getComputedStyle(document.documentElement);
      var pick = function (n, d) { return (css.getPropertyValue(n) || "").trim() || d; };
      return [pick("--bk-flame", "#E8590C"), pick("--bk-flame-core", "#FFB020"), pick("--bk-brass", "#7A5518"),
              pick("--bk-ok", "#2E6B45"), pick("--bk-on-brass", "#FFF8EA"), "#C2453A", "#3F6FB5"];
    };
    var size = function () {
      var r = window.devicePixelRatio || 1;
      canvas.width = Math.round(canvas.clientWidth * r);
      canvas.height = Math.round(canvas.clientHeight * r);
      if (ctx) ctx.setTransform(r, 0, 0, r, 0, 0);
    };
    var burst = function (x, y) {
      var c = colors[Math.floor(Math.random() * colors.length)];
      var n = 46 + Math.floor(Math.random() * 20);
      for (var i = 0; i < n; i++) {
        var a = (Math.PI * 2 * i) / n + Math.random() * 0.2, v = 2.2 + Math.random() * 3.2;
        parts.push({kind: "spark", x: x, y: y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, life: 1, decay: 0.012 + Math.random() * 0.012, c: c});
      }
    };
    var confetti = function (w, n) {
      for (var i = 0; i < n; i++) {
        parts.push({kind: "paper", x: Math.random() * w, y: -20 - Math.random() * 200, vx: (Math.random() - 0.5) * 1.6,
          vy: 1.5 + Math.random() * 2.2, rot: Math.random() * 6.28, vr: (Math.random() - 0.5) * 0.3,
          w: 6 + Math.random() * 6, h: 3 + Math.random() * 4, life: 1, decay: 0, c: colors[i % colors.length]});
      }
    };
    var frame = function (t) {
      var w = canvas.clientWidth, h = canvas.clientHeight;
      ctx.clearRect(0, 0, w, h);
      var age = t - startedAt;
      // Busy for the first seconds, then one now and then (or none, when asked to settle).
      var gap = age < opts.busy ? 420 : opts.every;
      if (gap && t - lastBurst > gap) {
        burst(w * (0.15 + Math.random() * 0.7), h * (0.12 + Math.random() * 0.35));
        lastBurst = t;
      }
      for (var i = parts.length - 1; i >= 0; i--) {
        var p = parts[i];
        if (p.kind === "spark") {
          p.vy += 0.045; p.vx *= 0.985; p.vy *= 0.985;
          p.x += p.vx; p.y += p.vy; p.life -= p.decay;
          if (p.life <= 0) { parts.splice(i, 1); continue; }
          ctx.globalAlpha = Math.max(0, p.life);
          ctx.fillStyle = p.c;
          ctx.beginPath(); ctx.arc(p.x, p.y, 2.2, 0, 6.283); ctx.fill();
        } else {
          p.x += p.vx + Math.sin((t / 400) + i) * 0.4; p.y += p.vy; p.rot += p.vr;
          if (p.y > h + 20) { parts.splice(i, 1); continue; }
          ctx.globalAlpha = 1;
          ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.rot);
          ctx.fillStyle = p.c; ctx.fillRect(-p.w / 2, -p.h / 2, p.w, Math.abs(Math.cos(p.rot)) * p.h + 1);
          ctx.restore();
        }
      }
      ctx.globalAlpha = 1;
      if (!opts.every && age > opts.busy && !parts.length) { raf = 0; return; }  // settled: done
      raf = requestAnimationFrame(frame);
    };

    return {
      // {confetti: pieces, busy: ms of fireworks, every: ms between later bursts, 0 for none}
      start: function (o) {
        if (!ctx || reduce) return;
        opts = {confetti: 140, busy: 5000, every: 2200};
        for (var k in (o || {})) opts[k] = o[k];
        colors = palette();
        size();
        parts = [];
        confetti(canvas.clientWidth, opts.confetti);
        startedAt = performance.now(); lastBurst = 0;
        cancelAnimationFrame(raf);
        raf = requestAnimationFrame(frame);
      },
      stop: function () { cancelAnimationFrame(raf); raf = 0; parts = []; if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height); },
      size: size,
    };
  };
})();
