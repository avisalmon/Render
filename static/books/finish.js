/* "I finished the book!" (Avi, 2026-10-21): the clock stops, fireworks and
   confetti go up, and there is room for a summary and thoughts (it can be
   skipped). Saving or skipping ends the session as a finished book and goes
   home; "not yet" closes it and the clock runs again. */
(function () {
  "use strict";
  var dialog = document.querySelector("[data-finish]");
  var openBtn = document.querySelector("[data-finish-open]");
  if (!dialog || !openBtn) return;
  var form = dialog.querySelector("[data-finish-form]");
  var pageField = form.querySelector("[data-finish-page]");
  var canvas = dialog.querySelector("[data-sky]");
  var ctx = canvas.getContext && canvas.getContext("2d");
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var raf = 0, parts = [], startedAt = 0, lastBurst = 0;

  var palette = function () {
    var css = getComputedStyle(document.documentElement);
    var pick = function (n, d) { return (css.getPropertyValue(n) || "").trim() || d; };
    return [pick("--bk-flame", "#E8590C"), pick("--bk-flame-core", "#FFB020"), pick("--bk-brass", "#7A5518"),
            pick("--bk-ok", "#2E6B45"), pick("--bk-on-brass", "#FFF8EA"), "#C2453A", "#3F6FB5"];
  };
  var colors = [];

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
    // Fireworks for the first five seconds, then one now and then.
    if (t - lastBurst > (age < 5000 ? 420 : 2200)) {
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
    raf = requestAnimationFrame(frame);
  };

  var celebrate = function () {
    if (!ctx || reduce) return;
    colors = palette();
    size();
    parts = [];
    confetti(canvas.clientWidth, 140);
    startedAt = performance.now(); lastBurst = 0;
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(frame);
  };
  var calm = function () { cancelAnimationFrame(raf); parts = []; if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height); };

  openBtn.addEventListener("click", function () {
    if (window.bkReading) window.bkReading.pause();  // the clock stops when the book is done
    var flip = document.querySelector("[data-flip-input]");
    var reached = flip ? parseInt(flip.value, 10) || 0 : 0;
    var pages = parseInt(pageField.getAttribute("data-pages"), 10) || 0;
    pageField.value = String(Math.max(reached, pages));
    if (dialog.showModal) dialog.showModal(); else dialog.setAttribute("open", "");
    dialog.querySelector(".bk-finish-card").focus({preventScroll: true});
    celebrate();
    if (navigator.vibrate) { try { navigator.vibrate([30, 60, 30]); } catch (e) { /* ignore */ } }
  });
  window.addEventListener("resize", function () { if (dialog.open) size(); });

  dialog.querySelector("[data-finish-cancel]").addEventListener("click", function () {
    if (window.bkStopRecording) window.bkStopRecording();
    calm();
    dialog.close();
    if (window.bkReading) window.bkReading.resume();
  });
  dialog.addEventListener("cancel", function () { calm(); if (window.bkReading) window.bkReading.resume(); });
  form.querySelector("[data-finish-skip]").addEventListener("click", function () {
    form.querySelector("[data-voice-text]").value = "";
  });
  form.addEventListener("submit", function () { if (window.bkReading) window.bkReading.end(); });
})();
